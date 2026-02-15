# Video Duration Adjuster

> Important: Before working on this project, read [AGENTS.md](AGENTS.md) for required workflows and tooling expectations.



## Getting Started

> Before making changes, read the project guidelines in [AGENTS.md](AGENTS.md).

This project is managed with [Poetry](https://python-poetry.org/).

### Prerequisites

Based on this project's dependencies, install the following system-level packages first via Homebrew (macOS):

```bash
brew install python@3.11 ffmpeg-full poetry
```

| Package | Reason |
|---------|--------|
| `python@3.11` | The project requires Python ~3.11 as specified in `pyproject.toml` |
| `ffmpeg-full` | Required for video processing and includes FFmpeg compiled with `--enable-librubberband` |
| `poetry` | Python dependency manager used to manage this project |

After installing Playwright (via `poetry install`), you also need to download browser binaries:

```bash
poetry run playwright install
```

This project currently uses `ffmpeg-full` on macOS for audio speed optimization.
Reason: the default `ffmpeg` formula may not include the `rubberband` filter, while `ffmpeg-full` is compiled with `--enable-librubberband`.
Because of this requirement, this project should use `ffmpeg-full` instead of the default `ffmpeg` formula.

```bash
brew install ffmpeg-full
```

### Installation

1. Ensure Poetry uses Python 3.11:

```bash
poetry env use python3.11
poetry env info
```

2. Install dependencies:

```bash
poetry install
```

### Running the App

Start the development server:

```bash
poetry run ./reflex_rerun.sh
```

The application will be available at `http://localhost:3000`.

### Apple Native Frame Interpolation (macOS)

This app now prioritizes Apple native interpolation for **slow-motion (duration stretch)** on macOS.

Set `APPLE_NATIVE_VFI_CMD` before running the app. The command should generate an interpolated **video-only** output file.

On macOS, if `APPLE_NATIVE_VFI_CMD` is not set, the app will auto-detect in this order:

1. `scripts/apple_vfi_runner.py` in this repository
2. `apple-vfi-runner` on PATH
3. `vtframeprocessor-vfi` on PATH

`scripts/apple_vfi_runner.py` is an adapter. Configure its real Apple backend with:

```bash
export APPLE_VFI_BACKEND_CMD='vtframeprocessor-vfi --input {input} --output {output} --factor {factor} --fps {fps} --preview-seconds {preview_seconds}'
```

For AI/Metal interpolation in this repository, set a Core ML model path:

```bash
export APPLE_COREML_MODEL_PATH='/absolute/path/to/your/frame_interpolation_model.mlmodelc'
```

Or enable automatic model download (first run downloads into `assets/models/`):

```bash
export APPLE_COREML_MODEL_URL='https://your-model-host/path/to/model.mlpackage'
```

In the UI, you can also choose built-in model presets (Community, Experimental):

- `SepConv 128 (Community, Experimental)`
- `SepConv 256 (Community, Experimental)`

These presets auto-fill URL and I/O mapping for convenience, but quality/compatibility can vary by model.

Supported auto-download formats: `.mlmodelc`, `.mlpackage`, `.mlmodel`, `.zip` (must contain one of those).
If `.mlmodel` is downloaded, the runner auto-compiles it to `.mlmodelc` using `xcrun coremlcompiler`.

When this variable is set, the adapter prioritizes the built-in Core ML Metal backend at `scripts/apple_ai_metal_vfi.py`.
Default model I/O names expected by this backend:

- Inputs: `frame0`, `frame1`, `time`
- Output: `output`

If your model uses different names, override with:

```bash
export APPLE_COREML_INPUT0='...'
export APPLE_COREML_INPUT1='...'
export APPLE_COREML_INPUT_TIME='...'
export APPLE_COREML_OUTPUT='...'
```

If `vtframeprocessor-vfi` is already on PATH, the adapter will call it automatically.
If not, the adapter will use the built-in Swift backend at `scripts/apple_vfi_backend.swift` (requires Xcode Command Line Tools and `xcrun`).
Also, `poetry run ./reflex_rerun.sh` now auto-exports `APPLE_VFI_BACKEND_CMD` on macOS when `vtframeprocessor-vfi` is available.

If you require a GPU-capable Apple interpolation backend (and do not want to use the built-in Swift fallback), enable strict mode:

```bash
export APPLE_VFI_REQUIRE_GPU=1
```

With strict mode on, processing fails fast when only the built-in Swift backend is available.
`poetry run ./reflex_rerun.sh` now enables `APPLE_VFI_REQUIRE_GPU=1` by default on macOS unless you explicitly set it.
To allow built-in Swift fallback, set `APPLE_VFI_REQUIRE_GPU=0` before launching.

Required template placeholders:

- `{input}`: input video path
- `{output}`: output video path
- `{factor}`: slow-down factor (e.g. `2.0` means 2x longer)
- `{fps}`: target FPS
- `{preview_seconds}`: `5` for preview mode, `0` for full processing

Example (replace with your real Apple pipeline command):

```bash
export APPLE_NATIVE_VFI_CMD='python /path/to/apple_vfi_runner.py --input {input} --output {output} --factor {factor} --fps {fps} --preview-seconds {preview_seconds}'
poetry run ./reflex_rerun.sh
```

Notes:

- On macOS slow-motion requests, if `APPLE_NATIVE_VFI_CMD` is set, Apple native interpolation is used.
- If no Apple-native command is discovered, the app falls back to FFmpeg optical-flow interpolation.
- If Apple-native execution fails at runtime, the app also falls back to FFmpeg optical-flow interpolation.
- Audio tempo/pitch processing still runs through FFmpeg/Rubber Band after Apple interpolation.
- Non-macOS platforms continue using the existing FFmpeg processing path.

### Clean Rebuild & Run

To fully clean the environment, reinstall all dependencies, and start the app in one step:

```bash
./proj_reinstall.sh --with-rerun
```

This will remove existing Poetry virtual environments and Reflex artifacts, recreate the environment from scratch, and automatically launch the app afterwards.

