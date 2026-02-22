import reflex as rx
import random
import string
import os
import sys
from typing import Optional
import subprocess
from fractions import Fraction


class VideoState(rx.State):
    uploaded_file: str = ""
    file_name: str = ""
    is_uploaded: bool = False
    is_uploading: bool = False
    duration_seconds: float = 0.0
    duration_formatted: str = "00:00:00"
    width: int = 0
    height: int = 0
    file_size_mb: float = 0.0
    has_audio: bool = False
    target_hours: str = "0"
    target_minutes: str = "0"
    target_seconds: str = "0"
    target_total_seconds: str = "0"
    input_mode: str = "time"
    is_processing: bool = False
    processing_progress: int = 0
    processing_status: str = ""
    preview_ready: bool = False
    preview_file: str = ""
    processed_file: str = ""
    is_processed: bool = False
    error_message: str = ""
    using_rubberband: bool = False
    using_optical_flow: bool = False
    using_rife: bool = False
    source_fps: float = 0.0

    @staticmethod
    def _ffmpeg_has_filter(ffmpeg_bin: str, filter_name: str) -> bool:
        try:
            result = subprocess.run(
                [ffmpeg_bin, "-hide_banner", "-filters"],
                capture_output=True,
                text=True,
                check=False,
            )
            combined = f"{result.stdout}\n{result.stderr}".lower()
            return filter_name.lower() in combined
        except Exception:
            return False

    @classmethod
    def _ffmpeg_has_rubberband(cls, ffmpeg_bin: str) -> bool:
        return cls._ffmpeg_has_filter(ffmpeg_bin, "rubberband")

    @classmethod
    def _ffmpeg_has_minterpolate(cls, ffmpeg_bin: str) -> bool:
        return cls._ffmpeg_has_filter(ffmpeg_bin, "minterpolate")

    @staticmethod
    def _parse_fps(raw_fps: str | None) -> float:
        if not raw_fps:
            return 0.0
        try:
            fps = float(Fraction(raw_fps))
            if fps <= 0:
                return 0.0
            return fps
        except Exception:
            return 0.0

    @classmethod
    def _resolve_ffmpeg_binary(cls) -> tuple[str, bool]:
        ffmpeg_full_path = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
        if os.path.exists(ffmpeg_full_path):
            if cls._ffmpeg_has_rubberband(ffmpeg_full_path):
                return ffmpeg_full_path, True
            return ffmpeg_full_path, False

        default_ffmpeg = "ffmpeg"
        return default_ffmpeg, cls._ffmpeg_has_rubberband(default_ffmpeg)

    @staticmethod
    def _resolve_ffprobe_binary() -> str:
        ffprobe_full_path = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
        if os.path.exists(ffprobe_full_path):
            return ffprobe_full_path
        return "ffprobe"

    @staticmethod
    def _build_atempo_chain(tempo: float) -> str:
        factors = []
        remaining = tempo
        while remaining > 2.0:
            factors.append(2.0)
            remaining /= 2.0
        while 0 < remaining < 0.5:
            factors.append(0.5)
            remaining /= 0.5
        remaining = max(0.5, min(2.0, remaining))
        factors.append(remaining)
        return ",".join(f"atempo={factor:.6f}" for factor in factors)

    @classmethod
    def _is_rife_available(cls) -> bool:
        """Check if RIFE AI frame interpolation is set up and ready."""
        # __file__ = .../video_duration_adjuster/video_duration_adjuster/states/video_state.py
        # We need to go up 3 levels to reach the project root (where scripts/ lives)
        scripts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "scripts",
        )
        runner = os.path.join(scripts_dir, "apple_vfi_runner.py")
        rife_dir = os.path.join(scripts_dir, "Practical-RIFE")
        flownet = os.path.join(rife_dir, "train_log", "flownet.pkl")
        runner_ok = os.path.exists(runner)
        flownet_ok = os.path.exists(flownet)
        print(f"[RIFE-CHECK] __file__={__file__}", flush=True)
        print(f"[RIFE-CHECK] scripts_dir={scripts_dir}", flush=True)
        print(f"[RIFE-CHECK] runner={runner}  exists={runner_ok}", flush=True)
        print(f"[RIFE-CHECK] flownet={flownet}  exists={flownet_ok}", flush=True)
        return runner_ok and flownet_ok

    @staticmethod
    def _build_rubberband_filter(tempo: float) -> str:
        safe_tempo = max(0.01, tempo)
        return (
            "rubberband="
            f"tempo={safe_tempo:.6f}:"
            "transients=crisp:"
            "detector=compound:"
            "phase=laminar:"
            "window=standard:"
            "smoothing=on:"
            "formant=preserved:"
            "pitchq=quality"
        )

    @rx.var
    def calculated_target_total(self) -> float:
        try:
            if self.input_mode == "time":
                h = float(self.target_hours) if self.target_hours else 0.0
                m = float(self.target_minutes) if self.target_minutes else 0.0
                s = float(self.target_seconds) if self.target_seconds else 0.0
                return h * 3600 + m * 60 + s
            else:
                return (
                    float(self.target_total_seconds)
                    if self.target_total_seconds
                    else 0.0
                )
        except ValueError:
            return 0.0

    @rx.var
    def speed_ratio(self) -> float:
        target = self.calculated_target_total
        if target <= 0 or self.duration_seconds <= 0:
            return 1.0
        return round(self.duration_seconds / target, 3)

    @rx.var
    def speed_description(self) -> str:
        ratio = self.speed_ratio
        if ratio == 1.0:
            return "No change"
        elif ratio > 1.0:
            return f"{ratio:.2f}x faster"
        else:
            return f"{ratio:.2f}x slower"

    @rx.var
    def is_input_valid(self) -> bool:
        target = self.calculated_target_total
        return target > 0 and target != self.duration_seconds

    @rx.var
    def speed_warning(self) -> str:
        ratio = self.speed_ratio
        if ratio > 4.0:
            return "Extremely fast playback may cause visual artifacts."
        if ratio < 0.25:
            return "Extremely slow playback requires heavy interpolation."
        return ""

    @rx.event
    def set_input_mode(self, mode: str):
        self.input_mode = mode
        total = self.calculated_target_total
        if mode == "seconds":
            self.target_total_seconds = str(int(total))
        else:
            self.target_hours = str(int(total // 3600))
            self.target_minutes = str(int(total % 3600 // 60))
            self.target_seconds = str(int(total % 60))

    @rx.event
    def set_uploading(self, uploading: bool):
        self.is_uploading = uploading

    @staticmethod
    def _normalize_numeric_input(value: str | int | float | None) -> str:
        if value is None:
            return ""
        return str(value)

    @rx.event
    def update_target_hours(self, value: str | int | float | None):
        self.target_hours = self._normalize_numeric_input(value)

    @rx.event
    def update_target_minutes(self, value: str | int | float | None):
        self.target_minutes = self._normalize_numeric_input(value)

    @rx.event
    def update_target_seconds(self, value: str | int | float | None):
        self.target_seconds = self._normalize_numeric_input(value)

    @rx.event
    def update_target_total_seconds(self, value: str | int | float | None):
        self.target_total_seconds = self._normalize_numeric_input(value)

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        self.is_uploading = True
        yield
        file = files[0]
        upload_data = await file.read()
        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        unique_id = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        safe_name = "".join((c for c in file.name if c.isalnum() or c in "._-")).strip()
        filename = f"{unique_id}_{safe_name}"
        file_path = upload_dir / filename
        try:
            with file_path.open("wb") as f:
                f.write(upload_data)
            self.uploaded_file = filename
            self.file_name = file.name
            self.file_size_mb = round(len(upload_data) / (1024 * 1024), 2)
            import json

            try:
                ffprobe_bin = self._resolve_ffprobe_binary()
                cmd = [
                    ffprobe_bin,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(file_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    stderr_text = (result.stderr or "").strip()
                    raise RuntimeError(
                        f"ffprobe failed with code {result.returncode}: {stderr_text}"
                    )
                if not (result.stdout or "").strip():
                    raise RuntimeError("ffprobe returned empty metadata output")
                metadata = json.loads(result.stdout)
                format_info = metadata.get("format", {})
                self.duration_seconds = float(format_info.get("duration", 0))
                video_stream = next(
                    (
                        s
                        for s in metadata.get("streams", [])
                        if s["codec_type"] == "video"
                    ),
                    {},
                )
                self.width = int(video_stream.get("width", 0))
                self.height = int(video_stream.get("height", 0))
                self.source_fps = self._parse_fps(
                    video_stream.get("avg_frame_rate")
                    or video_stream.get("r_frame_rate")
                )
                self.has_audio = any(
                    s.get("codec_type") == "audio"
                    for s in metadata.get("streams", [])
                )
                if self.duration_seconds <= 0:
                    raise RuntimeError("Unable to parse valid duration from ffprobe output")
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"[WARN] FFprobe failed, metadata set to safe defaults: {e}", flush=True)
                self.duration_seconds = 0.0
                self.width = 0
                self.height = 0
                self.source_fps = 0.0
                self.has_audio = False
                self.error_message = "Could not read video metadata. Please verify ffprobe/ffmpeg setup."
            hours = int(self.duration_seconds // 3600)
            minutes = int(self.duration_seconds % 3600 // 60)
            seconds = int(self.duration_seconds % 60)
            self.duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.is_uploaded = True
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[ERROR] Error saving video: {e}", flush=True)
            yield rx.toast("Failed to process video file.", variant="error")
        self.is_uploading = False

    async def _process_with_rife(
        self, input_path, output_path, video_speed_factor, is_preview
    ):
        """Process video using RIFE AI frame interpolation on Apple MPS GPU.

        Pipeline:
        1. Extract frames from input video using ffmpeg
        2. Run RIFE model to generate interpolated frames (via subprocess)
        3. Assemble interpolated frames into output video
        4. Process audio separately (pitch-preserved)
        5. Merge video + audio tracks
        """
        import asyncio
        import shutil
        import tempfile

        ffmpeg_bin, ffmpeg_has_rubberband = self._resolve_ffmpeg_binary()
        tempo = self.speed_ratio  # original_duration / target_duration

        # Calculate RIFE multiplier (clamped to 2..8)
        multi = max(2, min(8, round(video_speed_factor)))

        print(f"[RIFE] Starting RIFE AI pipeline", flush=True)
        print(f"[RIFE] video_speed_factor={video_speed_factor:.3f}, multi={multi}x", flush=True)
        print(f"[RIFE] ffmpeg binary: {ffmpeg_bin}", flush=True)
        print(f"[RIFE] rubberband available: {ffmpeg_has_rubberband}", flush=True)

        tmpdir = tempfile.mkdtemp(prefix="rife_vfi_")
        try:
            input_frames_dir = os.path.join(tmpdir, "input_frames")
            output_frames_dir = os.path.join(tmpdir, "output_frames")
            os.makedirs(input_frames_dir)
            os.makedirs(output_frames_dir)

            # ── Step 1: Extract frames ──
            self.processing_status = (
                "Extracting video frames for AI processing..."
            )
            self.processing_progress = 3
            yield

            extract_cmd = [ffmpeg_bin, "-i", str(input_path)]
            if is_preview:
                extract_cmd.extend(["-t", "5"])
            extract_cmd.extend(
                ["-qscale:v", "2", "-y",
                 os.path.join(input_frames_dir, "%07d.png")]
            )

            proc = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await proc.wait()
            if proc.returncode != 0:
                raise RuntimeError("Failed to extract frames from video")

            input_frame_list = [
                f for f in os.listdir(input_frames_dir) if f.endswith(".png")
            ]
            if not input_frame_list:
                raise RuntimeError("No frames extracted from video")

            input_frame_count = len(input_frame_list)
            print(f"[RIFE] Step 1 done: extracted {input_frame_count} frames", flush=True)

            # ── Step 2: RIFE interpolation on MPS GPU ──
            scale = 1.0
            if self.width > 1920 or self.height > 1080:
                scale = 0.5  # Half resolution for HD+ content
                print(f"[RIFE] Using scale=0.5 for HD+ content ({self.width}x{self.height})", flush=True)

            self.processing_status = (
                f"Running RIFE AI frame interpolation on Apple Metal GPU "
                f"({multi}x, {input_frame_count} frames)..."
            )
            self.processing_progress = 8
            yield

            scripts_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "scripts",
            )
            runner = os.path.join(scripts_dir, "apple_vfi_runner.py")

            rife_cmd = [
                sys.executable,
                runner,
                "--input_dir", input_frames_dir,
                "--output_dir", output_frames_dir,
                "--multi", str(multi),
                "--scale", str(scale),
            ]
            print(f"[RIFE] Step 2: launching subprocess: {' '.join(rife_cmd)}", flush=True)

            rife_proc = await asyncio.create_subprocess_exec(
                *rife_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            total_output_frames = 0

            if rife_proc.stdout is not None:
                while True:
                    raw_line = await rife_proc.stdout.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode(errors="replace").strip()

                    if line.startswith("PROGRESS:"):
                        try:
                            rife_pct = int(line.split(":", 1)[1])
                            # Map RIFE 0-100 → overall 8-72
                            overall = 8 + int(rife_pct * 0.64)
                            if overall > self.processing_progress:
                                self.processing_progress = min(72, overall)
                                yield
                        except ValueError:
                            pass
                    elif line.startswith("TOTAL_FRAMES:"):
                        try:
                            total_output_frames = int(line.split(":", 1)[1])
                        except ValueError:
                            pass

            await rife_proc.wait()
            if rife_proc.returncode != 0:
                raise RuntimeError(
                    "RIFE frame interpolation subprocess failed "
                    f"(exit code {rife_proc.returncode})"
                )

            if total_output_frames == 0:
                total_output_frames = len(
                    [f for f in os.listdir(output_frames_dir)
                     if f.endswith(".png")]
                )
            if total_output_frames == 0:
                raise RuntimeError("No interpolated frames were generated")

            print(f"[RIFE] Step 2 done: generated {total_output_frames} interpolated frames", flush=True)

            # ── Step 3: Assemble video from interpolated frames ──
            self.processing_status = (
                "Assembling AI-interpolated frames into video..."
            )
            self.processing_progress = 75
            yield

            # Calculate output fps to match target duration
            if is_preview:
                # Preview: original 5s of input → 5s * speed_factor output
                target_duration = min(
                    5.0 * video_speed_factor, self.calculated_target_total
                )
            else:
                target_duration = self.calculated_target_total

            if target_duration <= 0:
                target_duration = total_output_frames / max(
                    self.source_fps, 24.0
                )

            output_fps = total_output_frames / target_duration
            print(f"[RIFE] Step 3: assembling video at {output_fps:.2f} fps "
                  f"(target_duration={target_duration:.2f}s, frames={total_output_frames})", flush=True)

            video_only = os.path.join(tmpdir, "video_only.mp4")
            assemble_cmd = [
                ffmpeg_bin,
                "-framerate", f"{output_fps:.4f}",
                "-i", os.path.join(output_frames_dir, "%07d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                "-preset", "medium",
                "-y", video_only,
            ]

            proc = await asyncio.create_subprocess_exec(
                *assemble_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await proc.wait()
            if proc.returncode != 0:
                raise RuntimeError("Failed to assemble interpolated video")

            # ── Step 4: Handle audio ──
            if self.has_audio:
                self.processing_status = (
                    "Processing audio with pitch preservation..."
                )
                self.processing_progress = 85
                yield

                audio_only = os.path.join(tmpdir, "audio_only.m4a")

                self.using_rubberband = False
                if ffmpeg_has_rubberband:
                    audio_filter = self._build_rubberband_filter(tempo)
                    self.using_rubberband = True
                    print(f"[RIFE] Step 4: audio via rubberband (pitch-preserved)", flush=True)
                else:
                    audio_filter = self._build_atempo_chain(tempo)
                    print(f"[RIFE] Step 4: audio via atempo chain (basic)", flush=True)

                audio_cmd = [
                    ffmpeg_bin, "-i", str(input_path),
                    "-vn", "-af", audio_filter,
                ]
                if is_preview:
                    audio_cmd.extend(["-t", f"{target_duration:.3f}"])
                audio_cmd.extend(["-y", audio_only])

                proc = await asyncio.create_subprocess_exec(
                    *audio_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                await proc.wait()

                if proc.returncode == 0:
                    # ── Step 5: Merge video + audio ──
                    self.processing_status = "Merging video and audio..."
                    self.processing_progress = 93
                    yield

                    merge_cmd = [
                        ffmpeg_bin,
                        "-i", video_only,
                        "-i", audio_only,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-shortest",
                        "-y", str(output_path),
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *merge_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    await proc.wait()
                    if proc.returncode != 0:
                        print("[WARN] Merge failed, using video-only output", flush=True)
                        shutil.copy2(video_only, str(output_path))
                else:
                    print("[WARN] Audio processing failed, using video-only output", flush=True)
                    shutil.copy2(video_only, str(output_path))
            else:
                shutil.copy2(video_only, str(output_path))

        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    async def _process_ffmpeg(self, is_preview: bool = False):
        """Helper to run ffmpeg command for processing or preview."""
        import asyncio
        from collections import deque

        self.is_processing = True
        self.error_message = ""
        self.processing_progress = 0
        yield
        try:
            upload_dir = rx.get_upload_dir()
            input_path = upload_dir / self.uploaded_file
            if not input_path.exists():
                raise FileNotFoundError("Source file not found")
            ratio = self.speed_ratio
            if ratio <= 0:
                raise ValueError("Invalid speed ratio")
            ffmpeg_bin, ffmpeg_has_rubberband = self._resolve_ffmpeg_binary()
            ffmpeg_has_minterpolate = self._ffmpeg_has_minterpolate(ffmpeg_bin)
            video_speed_factor = 1.0 / ratio
            tempo = ratio

            print("=" * 60, flush=True)
            print("[PROCESS] Starting video processing", flush=True)
            print(f"[PROCESS] Mode: {'preview (5s)' if is_preview else 'full video'}", flush=True)
            print(f"[PROCESS] Input: {self.uploaded_file}", flush=True)
            print(f"[PROCESS] Source FPS: {self.source_fps}", flush=True)
            print(f"[PROCESS] Resolution: {self.width}x{self.height}", flush=True)
            print(f"[PROCESS] Has audio: {self.has_audio}", flush=True)
            print(f"[PROCESS] Duration: {self.duration_seconds:.2f}s -> Target: {self.calculated_target_total:.2f}s", flush=True)
            print(f"[PROCESS] Speed ratio: {ratio:.4f} (video_speed_factor={video_speed_factor:.4f}, tempo={tempo:.4f})", flush=True)
            if video_speed_factor > 1.0:
                print(f"[PROCESS] Direction: SLOW DOWN (need frame interpolation)", flush=True)
            elif video_speed_factor < 1.0:
                print(f"[PROCESS] Direction: SPEED UP", flush=True)
            else:
                print(f"[PROCESS] Direction: NO CHANGE", flush=True)
            print(f"[PROCESS] ffmpeg binary: {ffmpeg_bin}", flush=True)
            print(f"[PROCESS] ffmpeg has rubberband: {ffmpeg_has_rubberband}", flush=True)
            print(f"[PROCESS] ffmpeg has minterpolate: {ffmpeg_has_minterpolate}", flush=True)
            print(f"[PROCESS] RIFE model available: {self._is_rife_available()}", flush=True)
            print("=" * 60, flush=True)
            output_filename = (
                f"preview_{self.uploaded_file}"
                if is_preview
                else f"processed_{self.uploaded_file}"
            )
            output_path = upload_dir / output_filename
            if output_path.exists():
                output_path.unlink()

            # --- RIFE AI frame interpolation for slow-down ---
            use_rife = (
                video_speed_factor > 1.0
                and self.source_fps > 0
                and self._is_rife_available()
            )
            print(f"[DECISION] Use RIFE? {use_rife} "
                  f"(slow_down={video_speed_factor > 1.0}, "
                  f"has_fps={self.source_fps > 0}, "
                  f"rife_ready={self._is_rife_available()})", flush=True)
            if use_rife:
                try:
                    print("[PATH] >>> Using PATH 1: RIFE AI deep learning on Apple MPS GPU", flush=True)
                    self.using_rife = True
                    async for _ in self._process_with_rife(
                        input_path, output_path, video_speed_factor, is_preview
                    ):
                        yield
                    self.processing_progress = 100
                    if is_preview:
                        self.preview_file = output_filename
                        self.preview_ready = True
                        self.processing_status = (
                            "Preview ready! "
                            "(RIFE AI frame interpolation on Apple Metal GPU)"
                        )
                    else:
                        self.processed_file = output_filename
                        self.is_processed = True
                        self.processing_status = (
                            "Processing complete! "
                            "(RIFE AI frame interpolation on Apple Metal GPU)"
                        )
                    yield
                    return
                except Exception as rife_err:
                    print(f"[WARN] [PATH] RIFE failed, falling back to ffmpeg: {rife_err}", flush=True)
                    self.using_rife = False
                    self.processing_progress = 0
                    if output_path.exists():
                        output_path.unlink()
            # --- End RIFE section, fall through to ffmpeg ---

            video_filter = f"[0:v]setpts=PTS*{video_speed_factor}[v]"
            self.using_optical_flow = False
            if (
                video_speed_factor > 1.0
                and ffmpeg_has_minterpolate
                and self.source_fps > 0
            ):
                target_fps = min(max(self.source_fps, 1.0), 120.0)
                video_filter = (
                    f"[0:v]setpts=PTS*{video_speed_factor},"
                    f"minterpolate=fps={target_fps:.3f}:"
                    "mi_mode=mci:mc_mode=aobmc:vsbmc=1[v]"
                )
                self.using_optical_flow = True
                print(f"[PATH] >>> Using PATH 2: ffmpeg minterpolate "
                      f"(traditional optical flow, NOT deep learning, CPU only)", flush=True)
                print(f"[PATH] minterpolate target_fps={target_fps:.3f}", flush=True)
            else:
                video_filter = f"[0:v]setpts=PTS*{video_speed_factor}[v]"
                print(f"[PATH] >>> Using PATH 3: ffmpeg setpts only "
                      f"(pure timestamp change, NO frame interpolation)", flush=True)
                if video_speed_factor > 1.0:
                    print(f"[PATH] WARNING: Slow-down without interpolation "
                          f"will look choppy/stuttery", flush=True)
            has_audio = self.has_audio
            filter_complex = video_filter
            self.using_rubberband = False
            if has_audio:
                if ffmpeg_has_rubberband:
                    audio_filter = self._build_rubberband_filter(tempo)
                    self.using_rubberband = True
                    print(f"[AUDIO] Using rubberband (pitch-preserved, high quality)", flush=True)
                else:
                    audio_filter = self._build_atempo_chain(tempo)
                    print(f"[AUDIO] Using atempo chain (basic, no pitch preservation)", flush=True)
                filter_complex = f"{video_filter};[0:a]{audio_filter}[a]"
            else:
                print(f"[AUDIO] No audio track detected", flush=True)
            print(f"[FFMPEG] filter_complex: {filter_complex}", flush=True)
            cmd = [
                ffmpeg_bin,
                "-progress",
                "pipe:1",
                "-nostats",
                "-i",
                str(input_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-y",
            ]
            if has_audio:
                cmd.extend(["-map", "[a]"])
            if is_preview:
                cmd.extend(["-t", "5"])
                if self.using_optical_flow and has_audio and self.using_rubberband:
                    self.processing_status = "Generating preview with optical-flow frame interpolation and Rubber Band audio optimization..."
                elif self.using_optical_flow and has_audio:
                    self.processing_status = "Generating preview with optical-flow frame interpolation and standard audio tempo processing..."
                elif self.using_optical_flow:
                    self.processing_status = (
                        "Generating preview with optical-flow frame interpolation..."
                    )
                elif has_audio and self.using_rubberband:
                    self.processing_status = "Generating preview with Rubber Band audio optimization..."
                elif has_audio:
                    self.processing_status = "Generating preview with standard audio tempo processing..."
                else:
                    self.processing_status = "Generating preview..."
            else:
                if self.using_optical_flow and has_audio and self.using_rubberband:
                    self.processing_status = (
                        "Processing full video with optical-flow frame interpolation and Rubber Band audio optimization... This may take a while."
                    )
                elif self.using_optical_flow and has_audio:
                    self.processing_status = (
                        "Processing full video with optical-flow frame interpolation and standard audio tempo processing... This may take a while."
                    )
                elif self.using_optical_flow:
                    self.processing_status = (
                        "Processing full video with optical-flow frame interpolation... This may take a while."
                    )
                elif has_audio and self.using_rubberband:
                    self.processing_status = (
                        "Processing full video with Rubber Band audio optimization... This may take a while."
                    )
                elif has_audio:
                    self.processing_status = (
                        "Processing full video with standard audio tempo processing... This may take a while."
                    )
                else:
                    self.processing_status = (
                        "Processing full video... This may take a while."
                    )
            cmd.append(str(output_path))

            expected_output_seconds = (
                5.0 if is_preview else max(0.001, self.calculated_target_total)
            )

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )

            if process.stdout is None:
                raise RuntimeError("FFmpeg output stream is unavailable")

            output_tail: deque[str] = deque(maxlen=80)

            while True:
                raw_line = await process.stdout.readline()
                if not raw_line:
                    break

                line = raw_line.decode(errors="replace").strip()
                if line:
                    output_tail.append(line)

                if line.startswith("out_time_ms="):
                    try:
                        out_time_ms = int(line.split("=", 1)[1])
                        out_seconds = out_time_ms / 1_000_000
                        percent = int((out_seconds / expected_output_seconds) * 100)
                        percent = max(1, min(99, percent))
                        if percent > self.processing_progress:
                            self.processing_progress = percent
                            yield
                    except ValueError:
                        pass

                if line == "progress=end" and self.processing_progress < 99:
                    self.processing_progress = 99
                    yield

            await process.wait()

            if process.returncode != 0:
                error_log = "\n".join(output_tail)
                print(f"[ERROR] FFmpeg error: {error_log}", flush=True)
                raise RuntimeError("FFmpeg processing failed. Check logs.")
            self.processing_progress = 100
            if is_preview:
                self.preview_file = output_filename
                self.preview_ready = True
                self.processing_status = "Preview ready!"
            else:
                self.processed_file = output_filename
                self.is_processed = True
                self.processing_status = "Processing complete!"
            yield
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[ERROR] Processing error: {e}", flush=True)
            self.error_message = f"Error: {str(e)}"
            self.processing_status = "Failed"
            yield
        finally:
            self.is_processing = False
            yield

    @rx.event
    async def generate_preview(self):
        if not self.is_input_valid:
            return
        self.preview_ready = False
        yield
        async for _ in self._process_ffmpeg(is_preview=True):
            yield

    @rx.event
    async def process_video(self):
        if not self.is_input_valid:
            return
        self.is_processed = False
        yield
        async for _ in self._process_ffmpeg(is_preview=False):
            yield

    @rx.event
    def reset_upload(self):
        self.uploaded_file = ""
        self.file_name = ""
        self.is_uploaded = False
        self.duration_seconds = 0.0
        self.duration_formatted = "00:00:00"
        self.width = 0
        self.height = 0
        self.file_size_mb = 0.0
        self.has_audio = False
        self.source_fps = 0.0
        self.is_processing = False
        self.processing_progress = 0
        self.processing_status = ""
        self.preview_ready = False
        self.preview_file = ""
        self.processed_file = ""
        self.is_processed = False
        self.error_message = ""
        self.using_optical_flow = False
        self.using_rife = False
        self.target_hours = "0"
        self.target_minutes = "0"
        self.target_seconds = "0"
        self.target_total_seconds = "0"