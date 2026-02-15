#!/bin/bash

if [ "$(uname -s)" = "Darwin" ] && [ -z "$APPLE_VFI_REQUIRE_GPU" ]; then
  export APPLE_VFI_REQUIRE_GPU=1
  echo "Configured APPLE_VFI_REQUIRE_GPU=1 (default on macOS)."
fi

if [ "$(uname -s)" = "Darwin" ] && [ -z "$APPLE_VFI_BACKEND_CMD" ]; then
  if command -v vtframeprocessor-vfi >/dev/null 2>&1; then
    export APPLE_VFI_BACKEND_CMD='vtframeprocessor-vfi --input {input} --output {output} --factor {factor} --fps {fps} --preview-seconds {preview_seconds}'
    echo "Configured APPLE_VFI_BACKEND_CMD from vtframeprocessor-vfi (auto)."
  elif [ -n "$APPLE_COREML_MODEL_PATH" ] && [ -f "./scripts/apple_ai_metal_vfi.py" ]; then
    echo "Info: using built-in Core ML Metal backend (scripts/apple_ai_metal_vfi.py)." >&2
  elif command -v xcrun >/dev/null 2>&1 && [ -f "./scripts/apple_vfi_backend.swift" ]; then
    echo "Info: vtframeprocessor-vfi not found; built-in Swift Apple backend will be used (scripts/apple_vfi_backend.swift)." >&2
  else
    echo "Info: vtframeprocessor-vfi not found and built-in Swift backend unavailable; app will fallback to FFmpeg optical-flow." >&2
  fi
fi

echo "Checking for processes on ports 3000 and 8000..."

# Find PIDs using ports 3000 and 8000
PIDS=$(lsof -ti:3000,8000)

if [ -n "$PIDS" ]; then
  echo "Killing processes: $PIDS"
  kill -9 $PIDS
  echo "Processes killed."
else
  echo "No processes found on ports 3000 or 8000."
fi

echo "Starting Reflex app with args: $@"
poetry run reflex run "$@"
