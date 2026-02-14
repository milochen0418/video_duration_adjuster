import reflex as rx
import random
import string
import os
from typing import Optional
import logging


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
            import subprocess
            import json

            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(file_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
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
                self.has_audio = any(
                    s.get("codec_type") == "audio"
                    for s in metadata.get("streams", [])
                )
            except Exception as e:
                logging.exception("Unexpected error")
                logging.warning(f"FFprobe failed, falling back to mock data: {e}")
                self.duration_seconds = random.uniform(30.0, 300.0)
                self.width = 1920
                self.height = 1080
                self.has_audio = True
            hours = int(self.duration_seconds // 3600)
            minutes = int(self.duration_seconds % 3600 // 60)
            seconds = int(self.duration_seconds % 60)
            self.duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.is_uploaded = True
        except Exception as e:
            logging.exception(f"Error saving video: {e}")
            yield rx.toast("Failed to process video file.", variant="error")
        self.is_uploading = False

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
            video_speed_factor = 1.0 / ratio
            tempo = ratio
            output_filename = (
                f"preview_{self.uploaded_file}"
                if is_preview
                else f"processed_{self.uploaded_file}"
            )
            output_path = upload_dir / output_filename
            if output_path.exists():
                output_path.unlink()
            video_filter = f"[0:v]setpts=PTS*{video_speed_factor}[v]"
            has_audio = self.has_audio
            filter_complex = video_filter
            if has_audio:
                atempo_chain = self._build_atempo_chain(tempo)
                filter_complex = (
                    f"{video_filter};[0:a]{atempo_chain}[a]"
                )
            cmd = [
                "ffmpeg",
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
                self.processing_status = "Generating preview..."
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
                logging.error(f"FFmpeg error: {error_log}")
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
            logging.exception(f"Processing error: {e}")
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
        self.is_processing = False
        self.processing_progress = 0
        self.processing_status = ""
        self.preview_ready = False
        self.preview_file = ""
        self.processed_file = ""
        self.is_processed = False
        self.error_message = ""
        self.target_hours = "0"
        self.target_minutes = "0"
        self.target_seconds = "0"
        self.target_total_seconds = "0"