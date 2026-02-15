#!/usr/bin/env python3
import argparse
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def _run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_text = (result.stderr or "").strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{stderr_text}")


def _get_video_fps(input_path: str, ffprobe_bin: str) -> float:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        input_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return 30.0
    raw = (result.stdout or "").strip()
    if "/" in raw:
        numerator, denominator = raw.split("/", 1)
        try:
            numerator_value = float(numerator)
            denominator_value = float(denominator)
            if denominator_value > 0:
                return numerator_value / denominator_value
        except ValueError:
            pass
    try:
        value = float(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    return 30.0


def _load_coreml_model(model_path: str):
    try:
        import coremltools as ct
    except Exception as error:
        raise RuntimeError(
            "coremltools is not installed. Install it first: poetry run pip install coremltools"
        ) from error

    compute_units_name = os.getenv("APPLE_COREML_COMPUTE_UNITS", "CPU_AND_GPU").upper()
    compute_units_map = {
        "ALL": ct.ComputeUnit.ALL,
        "CPU_ONLY": ct.ComputeUnit.CPU_ONLY,
        "CPU_AND_GPU": ct.ComputeUnit.CPU_AND_GPU,
        "CPU_AND_NE": ct.ComputeUnit.CPU_AND_NE,
    }
    compute_units = compute_units_map.get(compute_units_name, ct.ComputeUnit.CPU_AND_GPU)

    model = ct.models.MLModel(model_path, compute_units=compute_units)
    return model, compute_units_name


def _coreml_predict_intermediate(
    model,
    frame0: Image.Image,
    frame1: Image.Image,
    blend_time: float,
) -> Image.Image:
    input0_name = os.getenv("APPLE_COREML_INPUT0", "frame0")
    input1_name = os.getenv("APPLE_COREML_INPUT1", "frame1")
    input_time_name = os.getenv("APPLE_COREML_INPUT_TIME", "time")
    output_name = os.getenv("APPLE_COREML_OUTPUT", "output")

    prediction = model.predict(
        {
            input0_name: frame0,
            input1_name: frame1,
            input_time_name: np.array([blend_time], dtype=np.float32),
        }
    )

    if output_name not in prediction:
        available_keys = ", ".join(prediction.keys())
        raise RuntimeError(
            f"Core ML output key '{output_name}' not found. Available outputs: {available_keys}"
        )

    output_value = prediction[output_name]
    if isinstance(output_value, Image.Image):
        return output_value.convert("RGB")

    output_array = np.asarray(output_value)
    if output_array.dtype != np.uint8:
        output_array = np.clip(output_array, 0, 255).astype(np.uint8)

    if output_array.ndim == 4:
        output_array = output_array[0]
    if output_array.ndim == 3 and output_array.shape[0] in (1, 3, 4):
        output_array = np.transpose(output_array, (1, 2, 0))

    if output_array.ndim != 3:
        raise RuntimeError(f"Unsupported Core ML output shape: {output_array.shape}")

    if output_array.shape[2] == 1:
        output_array = np.repeat(output_array, 3, axis=2)
    elif output_array.shape[2] == 4:
        output_array = output_array[:, :, :3]

    return Image.fromarray(output_array, mode="RGB")


def _build_interpolated_frames(
    source_frames_dir: Path,
    output_frames_dir: Path,
    model,
    slowdown_factor: float,
) -> None:
    frame_paths = sorted(source_frames_dir.glob("frame_*.png"))
    if len(frame_paths) < 2:
        raise RuntimeError("Not enough frames to interpolate.")

    output_frames_dir.mkdir(parents=True, exist_ok=True)
    intermediate_count = max(1, int(math.ceil(slowdown_factor)) - 1)
    write_index = 0

    pair_total = len(frame_paths) - 1

    for pair_index in range(pair_total):
        frame0 = Image.open(frame_paths[pair_index]).convert("RGB")
        frame1 = Image.open(frame_paths[pair_index + 1]).convert("RGB")

        frame0.save(output_frames_dir / f"frame_{write_index:08d}.png")
        write_index += 1

        for intermediate_index in range(intermediate_count):
            blend_time = (intermediate_index + 1) / (intermediate_count + 1)
            interpolated = _coreml_predict_intermediate(model, frame0, frame1, blend_time)
            interpolated.save(output_frames_dir / f"frame_{write_index:08d}.png")
            write_index += 1

        progress_ratio = (pair_index + 1) / pair_total
        progress = 10 + int(progress_ratio * 50)
        print(f"APPLE_VFI_PROGRESS={progress}", flush=True)

    Image.open(frame_paths[-1]).convert("RGB").save(
        output_frames_dir / f"frame_{write_index:08d}.png"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Core ML Metal-accelerated frame interpolation backend")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--factor", required=True, type=float)
    parser.add_argument("--fps", required=True, type=float)
    parser.add_argument("--preview-seconds", required=True, type=int)
    parser.add_argument("--model-path", default=os.getenv("APPLE_COREML_MODEL_PATH", ""))
    args = parser.parse_args()

    if not args.model_path:
        print("APPLE_VFI_ERROR=APPLE_COREML_MODEL_PATH is not set.", flush=True)
        return 2

    if not os.path.exists(args.model_path):
        print(f"APPLE_VFI_ERROR=Core ML model not found: {args.model_path}", flush=True)
        return 2

    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    ffprobe_bin = shutil.which("ffprobe") or "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
    if not shutil.which("ffmpeg") and not Path(ffmpeg_bin).exists():
        print("APPLE_VFI_ERROR=ffmpeg not found in PATH.", flush=True)
        return 2
    if not shutil.which("ffprobe") and not Path(ffprobe_bin).exists():
        print("APPLE_VFI_ERROR=ffprobe not found in PATH.", flush=True)
        return 2

    try:
        model, compute_units_name = _load_coreml_model(args.model_path)
        print("APPLE_VFI_BACKEND=coreml-metal", flush=True)
        print("APPLE_VFI_GPU_CAPABLE=1", flush=True)
        print(f"APPLE_VFI_INFO=Core ML compute units: {compute_units_name}", flush=True)

        with tempfile.TemporaryDirectory(prefix="apple_ai_vfi_") as temp_dir:
            temp_path = Path(temp_dir)
            source_frames_dir = temp_path / "source_frames"
            output_frames_dir = temp_path / "output_frames"
            source_frames_dir.mkdir(parents=True, exist_ok=True)

            source_fps = _get_video_fps(args.input, ffprobe_bin)

            extract_command = [
                ffmpeg_bin,
                "-y",
                "-i",
                args.input,
                "-vsync",
                "0",
                str(source_frames_dir / "frame_%08d.png"),
            ]
            _run_command(extract_command)
            print("APPLE_VFI_PROGRESS=10", flush=True)

            _build_interpolated_frames(
                source_frames_dir=source_frames_dir,
                output_frames_dir=output_frames_dir,
                model=model,
                slowdown_factor=args.factor,
            )

            encode_fps = max(args.fps, source_fps)
            encode_command = [
                ffmpeg_bin,
                "-y",
                "-framerate",
                f"{encode_fps:.3f}",
                "-i",
                str(output_frames_dir / "frame_%08d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                args.output,
            ]

            if args.preview_seconds > 0:
                encode_command.extend(["-t", str(args.preview_seconds)])

            _run_command(encode_command)
            print("APPLE_VFI_PROGRESS=70", flush=True)

        return 0
    except Exception as error:
        print(f"APPLE_VFI_ERROR={error}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
