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

### Clean Rebuild & Run

To fully clean the environment, reinstall all dependencies, and start the app in one step:

```bash
./proj_reinstall.sh --with-rerun
```

This will remove existing Poetry virtual environments and Reflex artifacts, recreate the environment from scratch, and automatically launch the app afterwards.

## Frame Interpolation Approach

This project uses **CPU-based Optical Flow Interpolation** to generate intermediate frames when adjusting video duration.

An alternative approach leveraging **Apple GPU (Metal / Core ML) deep learning** for frame interpolation was explored in [PR #1](https://github.com/milochen0418/video_duration_adjuster/pull/1). After experimentation, the GPU-accelerated deep learning method did not outperform the current CPU-based optical flow approach in terms of output quality. Therefore, the Optical Flow Interpolation method remains the default and recommended approach.

