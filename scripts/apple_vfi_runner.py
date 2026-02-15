#!/usr/bin/env python3
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path


def _auto_prepare_coreml_model() -> None:
    existing = os.getenv("APPLE_COREML_MODEL_PATH", "").strip()
    if existing and os.path.exists(existing):
        return

    model_url = os.getenv("APPLE_COREML_MODEL_URL", "").strip()
    if not model_url:
        return

    parsed = urllib.parse.urlparse(model_url)
    file_name = os.path.basename(parsed.path) or "model.mlpackage"
    repo_root = Path(__file__).resolve().parents[1]
    model_root = repo_root / "assets" / "models"
    model_root.mkdir(parents=True, exist_ok=True)

    download_path = model_root / file_name
    if not download_path.exists():
        print(f"APPLE_VFI_INFO=Downloading Core ML model from {model_url}", flush=True)
        urllib.request.urlretrieve(model_url, str(download_path))
        print(f"APPLE_VFI_INFO=Model downloaded to {download_path}", flush=True)

    prepared_path: Path | None = None

    if download_path.suffix.lower() == ".zip":
        extract_dir = model_root / f"{download_path.stem}_extracted"
        if not extract_dir.exists():
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(download_path, "r") as archive:
                archive.extractall(extract_dir)
        for candidate in extract_dir.rglob("*.mlmodelc"):
            prepared_path = candidate
            break
        if prepared_path is None:
            for candidate in extract_dir.rglob("*.mlpackage"):
                prepared_path = candidate
                break
        if prepared_path is None:
            for candidate in extract_dir.rglob("*.mlmodel"):
                prepared_path = candidate
                break
    else:
        prepared_path = download_path

    if prepared_path is None:
        raise RuntimeError("Downloaded model archive does not contain .mlmodel/.mlpackage/.mlmodelc")

    final_path = prepared_path
    if prepared_path.suffix.lower() == ".mlmodel":
        xcrun_bin = shutil.which("xcrun")
        if not xcrun_bin:
            raise RuntimeError("xcrun is required to compile .mlmodel to .mlmodelc")
        compile_root = model_root / "compiled"
        compile_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [xcrun_bin, "coremlcompiler", "compile", str(prepared_path), str(compile_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        compiled_dir = compile_root / f"{prepared_path.stem}.mlmodelc"
        if not compiled_dir.exists():
            found = list(compile_root.glob("*.mlmodelc"))
            if found:
                compiled_dir = found[0]
        final_path = compiled_dir

    os.environ["APPLE_COREML_MODEL_PATH"] = str(final_path)
    print(f"APPLE_VFI_INFO=Using Core ML model path: {final_path}", flush=True)


def _build_backend_command(args: argparse.Namespace) -> tuple[list[str], str] | None:
    script_dir = os.path.dirname(os.path.abspath(__file__))

    coreml_model_path = os.getenv("APPLE_COREML_MODEL_PATH", "").strip()
    coreml_backend_script = os.path.join(script_dir, "apple_ai_metal_vfi.py")
    if coreml_model_path and os.path.exists(coreml_backend_script):
        python_bin = shutil.which("python3") or sys.executable
        return [
            python_bin,
            coreml_backend_script,
            "--input",
            args.input,
            "--output",
            args.output,
            "--factor",
            f"{args.factor:.6f}",
            "--fps",
            f"{args.fps:.3f}",
            "--preview-seconds",
            str(args.preview_seconds),
            "--model-path",
            coreml_model_path,
        ], "coreml-metal"

    custom_template = os.getenv("APPLE_VFI_BACKEND_CMD", "").strip()
    if custom_template:
        rendered = custom_template.format(
            input=shlex.quote(args.input),
            output=shlex.quote(args.output),
            factor=f"{args.factor:.6f}",
            fps=f"{args.fps:.3f}",
            preview_seconds=str(args.preview_seconds),
        )
        return ["/bin/sh", "-lc", rendered], "custom-env"

    backend_bin = shutil.which("vtframeprocessor-vfi")
    if backend_bin:
        return [
            backend_bin,
            "--input",
            args.input,
            "--output",
            args.output,
            "--factor",
            f"{args.factor:.6f}",
            "--fps",
            f"{args.fps:.3f}",
            "--preview-seconds",
            str(args.preview_seconds),
        ], "vtframeprocessor"

    swift_backend = os.path.join(script_dir, "apple_vfi_backend.swift")
    xcrun_bin = shutil.which("xcrun")
    if xcrun_bin and os.path.exists(swift_backend):
        return [
            xcrun_bin,
            "swift",
            swift_backend,
            "--input",
            args.input,
            "--output",
            args.output,
            "--factor",
            f"{args.factor:.6f}",
            "--fps",
            f"{args.fps:.3f}",
            "--preview-seconds",
            str(args.preview_seconds),
        ], "swift-built-in"

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apple-native VFI runner adapter for video_duration_adjuster"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--factor", required=True, type=float)
    parser.add_argument("--fps", required=True, type=float)
    parser.add_argument("--preview-seconds", required=True, type=int)
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("apple_vfi_runner is intended for macOS only.", flush=True)
        return 2

    try:
        _auto_prepare_coreml_model()
    except Exception as error:
        print(f"APPLE_VFI_WARNING=Auto model prepare failed: {error}", flush=True)

    backend = _build_backend_command(args)
    if backend is None:
        print(
            "No Apple VFI backend found. Set APPLE_VFI_BACKEND_CMD, install vtframeprocessor-vfi, or install Xcode command line tools for the built-in Swift backend.",
            flush=True,
        )
        return 2

    cmd, backend_name = backend
    require_gpu = os.getenv("APPLE_VFI_REQUIRE_GPU", "0").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }

    if backend_name == "swift-built-in":
        print("APPLE_VFI_BACKEND=swift-built-in", flush=True)
        print("APPLE_VFI_GPU_CAPABLE=0", flush=True)
        print(
            "APPLE_VFI_WARNING=Built-in Swift backend is Apple-native but not AI GPU frame interpolation. Configure APPLE_VFI_BACKEND_CMD for a GPU-capable backend.",
            flush=True,
        )
        if require_gpu:
            print(
                "APPLE_VFI_ERROR=APPLE_VFI_REQUIRE_GPU is enabled but no GPU-capable Apple VFI backend is available.",
                flush=True,
            )
            return 2
    elif backend_name == "coreml-metal":
        print("APPLE_VFI_BACKEND=coreml-metal", flush=True)
        print("APPLE_VFI_GPU_CAPABLE=1", flush=True)
    elif backend_name == "vtframeprocessor":
        print("APPLE_VFI_BACKEND=vtframeprocessor", flush=True)
        print("APPLE_VFI_GPU_CAPABLE=1", flush=True)
    else:
        print("APPLE_VFI_BACKEND=custom-env", flush=True)
        print("APPLE_VFI_GPU_CAPABLE=1", flush=True)

    print("APPLE_VFI_PROGRESS=5", flush=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n")
        if line:
            print(line, flush=True)

    return_code = process.wait()
    if return_code != 0:
        return return_code

    print("APPLE_VFI_PROGRESS=70", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
