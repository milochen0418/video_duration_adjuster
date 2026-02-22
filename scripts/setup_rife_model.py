#!/usr/bin/env python3
"""One-time setup script for RIFE AI frame interpolation on Apple MPS GPU.

This script:
1. Clones the Practical-RIFE repository
2. Patches device detection for Apple MPS support
3. Downloads model weights (v4.22 recommended)

Usage:
    poetry run python scripts/setup_rife_model.py
"""
import glob
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RIFE_DIR = os.path.join(SCRIPT_DIR, "Practical-RIFE")
TRAIN_LOG_DIR = os.path.join(RIFE_DIR, "train_log")

# Google Drive file ID for RIFE v4.22 model
MODEL_GDRIVE_ID = "1qh2DSA9a1eZUTtZG9U9RQKO7N7OaUJ0_"

CUDA_DEVICE_PATTERN = 'device = torch.device("cuda" if torch.cuda.is_available() else "cpu")'
MPS_DEVICE_REPLACEMENT = (
    'device = torch.device("mps" if hasattr(torch.backends, "mps") '
    "and torch.backends.mps.is_available() else "
    '("cuda" if torch.cuda.is_available() else "cpu"))'
)


def clone_repo():
    """Clone the Practical-RIFE repository."""
    if os.path.isdir(os.path.join(RIFE_DIR, ".git")):
        print(f"[OK] RIFE repo already cloned at {RIFE_DIR}")
        return

    print("Cloning Practical-RIFE repository...")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/hzwer/Practical-RIFE.git",
            RIFE_DIR,
        ],
        check=True,
    )
    print("[OK] Repository cloned.")


def patch_device_detection():
    """Patch all Python files in the repo to support Apple MPS GPU."""
    py_files = glob.glob(os.path.join(RIFE_DIR, "**", "*.py"), recursive=True)
    patched_count = 0

    for filepath in py_files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        if CUDA_DEVICE_PATTERN in content:
            content = content.replace(CUDA_DEVICE_PATTERN, MPS_DEVICE_REPLACEMENT)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            patched_count += 1
            rel = os.path.relpath(filepath, RIFE_DIR)
            print(f"  Patched: {rel}")

    print(f"[OK] Patched {patched_count} files for Apple MPS support.")


def download_model():
    """Download RIFE model weights."""
    os.makedirs(TRAIN_LOG_DIR, exist_ok=True)
    flownet_path = os.path.join(TRAIN_LOG_DIR, "flownet.pkl")

    if os.path.exists(flownet_path):
        print(f"[OK] Model weights already exist at {flownet_path}")
        return True

    # Try auto-download with gdown
    try:
        import gdown  # noqa: F811
    except ImportError:
        print("Installing gdown for model download...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "gdown"],
            check=True,
            capture_output=True,
        )
        import gdown

    print("Downloading RIFE v4.22 model weights from Google Drive...")
    zip_path = os.path.join(TRAIN_LOG_DIR, "model_v4.22.zip")

    try:
        gdown.download(id=MODEL_GDRIVE_ID, output=zip_path, quiet=False)

        if not os.path.exists(zip_path):
            raise RuntimeError("Download produced no file")

        import zipfile

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(TRAIN_LOG_DIR)
        os.remove(zip_path)

        # Move files from subdirectories to train_log root if needed
        import shutil

        for root, _dirs, files in os.walk(TRAIN_LOG_DIR):
            if root == TRAIN_LOG_DIR:
                continue
            for f in files:
                src = os.path.join(root, f)
                dst = os.path.join(TRAIN_LOG_DIR, f)
                if not os.path.exists(dst):
                    shutil.move(src, dst)

        # Clean up empty subdirectories
        for root, dirs, _files in os.walk(TRAIN_LOG_DIR, topdown=False):
            for d in dirs:
                dirpath = os.path.join(root, d)
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass

        print("[OK] Model weights downloaded and extracted.")
        return True

    except Exception as e:
        print(f"\n[WARN] Auto-download failed: {e}")
        print()
        _print_manual_instructions()
        return False


def _print_manual_instructions():
    """Print manual download instructions."""
    print("=" * 60)
    print("Please download the RIFE v4.22 model manually:")
    print("=" * 60)
    print()
    print("  Google Drive:")
    print(
        "  https://drive.google.com/file/d/"
        "1qh2DSA9a1eZUTtZG9U9RQKO7N7OaUJ0_/view"
    )
    print()
    print(f"  After downloading, unzip and place ALL files into:")
    print(f"    {TRAIN_LOG_DIR}/")
    print()
    print("  Expected files:")
    print("    - flownet.pkl")
    print("    - IFNet_HDv3.py")
    print("    - RIFE_HDv3.py")
    print()


def verify_setup():
    """Verify the RIFE setup is complete and functional."""
    print("\nVerifying setup...")
    required_files = ["flownet.pkl"]
    model_py_files = ["IFNet_HDv3.py", "RIFE_HDv3.py"]

    missing = []
    for f in required_files:
        if not os.path.exists(os.path.join(TRAIN_LOG_DIR, f)):
            missing.append(f)

    missing_py = []
    for f in model_py_files:
        if not os.path.exists(os.path.join(TRAIN_LOG_DIR, f)):
            missing_py.append(f)

    if missing:
        print(f"  [FAIL] Missing weight files: {missing}")
        return False

    if missing_py:
        print(f"  [WARN] Missing model .py files: {missing_py}")
        print("         These are usually included in the model download zip.")
        return False

    # Check warplayer.py exists (from repo)
    warplayer = os.path.join(RIFE_DIR, "model", "warplayer.py")
    if not os.path.exists(warplayer):
        print("  [FAIL] model/warplayer.py not found in repo")
        return False

    # Test PyTorch + MPS
    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print("  [OK] Apple MPS GPU: Available")
        elif torch.cuda.is_available():
            print(f"  [OK] CUDA GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("  [WARN] No GPU available, will use CPU (slower)")
    except ImportError:
        print("  [FAIL] PyTorch not installed!")
        print("         Run: poetry install --with ml")
        return False

    # Test OpenCV
    try:
        import cv2  # noqa: F401

        print("  [OK] OpenCV: Available")
    except ImportError:
        print("  [FAIL] OpenCV not installed!")
        print("         Run: poetry install --with ml")
        return False

    print("\n[OK] RIFE AI frame interpolation is ready!")
    return True


def main():
    print("=" * 60)
    print("  RIFE Model Setup for Apple MPS Frame Interpolation")
    print("=" * 60)
    print()

    clone_repo()
    print()
    patch_device_detection()
    print()
    download_model()

    # Also patch any newly downloaded .py files in train_log
    train_log_pys = glob.glob(os.path.join(TRAIN_LOG_DIR, "*.py"))
    for filepath in train_log_pys:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if CUDA_DEVICE_PATTERN in content:
                content = content.replace(CUDA_DEVICE_PATTERN, MPS_DEVICE_REPLACEMENT)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"  Patched: train_log/{os.path.basename(filepath)}")
        except Exception:
            pass

    success = verify_setup()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
