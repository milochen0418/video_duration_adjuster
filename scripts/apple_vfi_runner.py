#!/usr/bin/env python3
"""RIFE-based video frame interpolation runner for Apple MPS GPU.

This script processes a directory of input PNG frames and generates
interpolated output frames using the RIFE deep learning model,
running on Apple's Metal Performance Shaders (MPS) GPU backend.

Usage:
    python apple_vfi_runner.py \\
        --input_dir /path/to/input_frames \\
        --output_dir /path/to/output_frames \\
        --multi 2 \\
        [--scale 1.0]

Output protocol (stdout):
    DEVICE:<device_name>
    INPUT_FRAMES:<count>
    MULTI:<multiplier>
    PROGRESS:<0-100>
    TOTAL_FRAMES:<count>
    DONE
"""
import argparse
import os
import sys


def setup_rife_path():
    """Add Practical-RIFE to Python path and return the repo directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rife_dir = os.path.join(script_dir, "Practical-RIFE")

    if not os.path.isdir(rife_dir):
        print(
            "ERROR: Practical-RIFE not found. "
            "Run 'python scripts/setup_rife_model.py' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    train_log = os.path.join(rife_dir, "train_log")
    if not os.path.exists(os.path.join(train_log, "flownet.pkl")):
        print(
            "ERROR: Model weights not found. "
            "Run 'python scripts/setup_rife_model.py' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Add RIFE directory to Python path for imports
    sys.path.insert(0, rife_dir)
    return rife_dir


def detect_device():
    """Detect the best available compute device, preferring Apple MPS."""
    import torch

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps"), "Apple MPS GPU"
    elif torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return torch.device("cuda"), f"CUDA GPU ({name})"
    else:
        return torch.device("cpu"), "CPU"


def load_rife_model(rife_dir, device):
    """Load the RIFE model and move it to the target device."""
    import torch

    # Patch warplayer device before importing model
    try:
        import model.warplayer as warplayer

        warplayer.device = device
    except ImportError:
        pass

    # Save and change CWD for relative imports in RIFE code
    original_cwd = os.getcwd()
    os.chdir(rife_dir)

    try:
        from train_log.RIFE_HDv3 import Model
    except ImportError as e:
        os.chdir(original_cwd)
        raise RuntimeError(
            f"Failed to import RIFE model. "
            f"Ensure train_log/ has RIFE_HDv3.py and IFNet_HDv3.py: {e}"
        )

    os.chdir(original_cwd)

    model = Model()
    if not hasattr(model, "version"):
        model.version = 0

    train_log_dir = os.path.join(rife_dir, "train_log")

    # Load weights with device mapping
    model.load_model(train_log_dir, -1)
    model.eval()

    # Ensure model is on the correct device
    try:
        model.device()
    except Exception:
        pass

    try:
        model.flownet.to(device)
    except Exception:
        pass

    torch.set_grad_enabled(False)
    return model


def make_inference(model, I0, I1, n, scale=1.0):
    """Generate n intermediate frames between I0 and I1.

    For RIFE v3.9+, uses arbitrary timestep interpolation.
    For older versions, uses recursive bisection.
    """
    if n <= 0:
        return []

    if model.version >= 3.9:
        results = []
        for i in range(n):
            timestep = (i + 1) / (n + 1)
            mid = model.inference(I0, I1, timestep, scale)
            results.append(mid)
        return results
    else:
        # Recursive bisection for older models
        middle = model.inference(I0, I1, scale)
        if n == 1:
            return [middle]
        first_half = make_inference(model, I0, middle, n // 2, scale)
        second_half = make_inference(model, middle, I1, n // 2, scale)
        if n % 2:
            return [*first_half, middle, *second_half]
        else:
            return [*first_half, *second_half]


def process_frames(input_dir, output_dir, multi, scale, model, device):
    """Process input frames with RIFE interpolation."""
    import cv2
    import numpy as np
    import torch
    from torch.nn import functional as F

    # List and sort input frames
    frame_files = sorted(
        f for f in os.listdir(input_dir) if f.lower().endswith(".png")
    )
    if not frame_files:
        print("ERROR: No PNG frames found in input directory", file=sys.stderr)
        sys.exit(1)

    total_input = len(frame_files)
    n_intermediate = multi - 1  # Number of frames to generate per pair

    print(f"INPUT_FRAMES:{total_input}")
    print(f"MULTI:{multi}")
    sys.stdout.flush()

    # Read first frame for dimensions
    first_frame = cv2.imread(os.path.join(input_dir, frame_files[0]))
    if first_frame is None:
        print("ERROR: Failed to read first frame", file=sys.stderr)
        sys.exit(1)
    h, w, _ = first_frame.shape

    # Calculate padding (RIFE requires dimensions divisible by certain factor)
    tmp = max(128, int(128 / scale))
    ph = ((h - 1) // tmp + 1) * tmp
    pw = ((w - 1) // tmp + 1) * tmp
    padding = (0, pw - w, 0, ph - h)

    os.makedirs(output_dir, exist_ok=True)
    output_count = 0
    last_reported_progress = -1

    def write_frame(img_np):
        nonlocal output_count
        path = os.path.join(output_dir, f"{output_count:07d}.png")
        cv2.imwrite(path, img_np)
        output_count += 1

    def to_tensor(frame_bgr):
        """Convert BGR numpy frame to normalized torch tensor."""
        return (
            torch.from_numpy(np.transpose(frame_bgr, (2, 0, 1)))
            .to(device, non_blocking=True)
            .unsqueeze(0)
            .float()
            / 255.0
        )

    # Write first frame
    prev_frame = first_frame
    write_frame(prev_frame)

    # Process frame pairs
    for idx in range(1, total_input):
        curr_frame = cv2.imread(os.path.join(input_dir, frame_files[idx]))
        if curr_frame is None:
            # Skip unreadable frames
            continue

        if n_intermediate > 0:
            # Prepare tensors with padding
            I0 = F.pad(to_tensor(prev_frame), padding)
            I1 = F.pad(to_tensor(curr_frame), padding)

            # Generate intermediate frames
            try:
                midframes = make_inference(model, I0, I1, n_intermediate, scale)

                for mid in midframes:
                    mid_np = (
                        (mid[0] * 255.0)
                        .byte()
                        .cpu()
                        .numpy()
                        .transpose(1, 2, 0)[:h, :w]
                    )
                    write_frame(mid_np)
            except Exception as e:
                # On inference failure, fill with blended frames
                print(f"WARN: Inference failed for pair {idx}: {e}", file=sys.stderr)
                for k in range(n_intermediate):
                    alpha = (k + 1) / (n_intermediate + 1)
                    blended = cv2.addWeighted(
                        prev_frame, 1 - alpha, curr_frame, alpha, 0
                    )
                    write_frame(blended)

        # Write current frame
        write_frame(curr_frame)
        prev_frame = curr_frame

        # Report progress
        progress = int(idx / max(total_input - 1, 1) * 100)
        if progress > last_reported_progress:
            last_reported_progress = progress
            print(f"PROGRESS:{progress}")
            sys.stdout.flush()

    print(f"TOTAL_FRAMES:{output_count}")
    print("DONE")
    sys.stdout.flush()
    return output_count


def main():
    parser = argparse.ArgumentParser(
        description="RIFE AI frame interpolation on Apple MPS GPU"
    )
    parser.add_argument(
        "--input_dir",
        required=True,
        help="Directory containing input PNG frames (numbered sequentially)",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory for output frames with interpolated frames inserted",
    )
    parser.add_argument(
        "--multi",
        type=int,
        default=2,
        help="Frame multiplier: 2=2x frames, 3=3x frames, etc. (default: 2)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Resolution scale for processing. Use 0.5 for 4K content (default: 1.0)",
    )
    args = parser.parse_args()

    if args.multi < 2:
        print("ERROR: --multi must be >= 2", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.input_dir):
        print(f"ERROR: Input directory not found: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    # Setup imports
    rife_dir = setup_rife_path()

    # Detect device
    device, device_name = detect_device()
    print(f"DEVICE:{device_name}")
    sys.stdout.flush()

    # Load model
    model = load_rife_model(rife_dir, device)

    # Process frames
    process_frames(args.input_dir, args.output_dir, args.multi, args.scale, model, device)


if __name__ == "__main__":
    main()
