#!/usr/bin/env python3
"""
tools/heightmap_converter.py
Converts 2D map images into Godot 4 compatible 16-bit heightmaps and normalmaps.
"""

import os
import sys
import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# Safe encoding for Windows consoles (e.g. CP949)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def convert_image(
    input_path: Path,
    output_dir: Path,
    blur_radius: int = 5,
    normal_strength: float = 2.0
) -> tuple[Path, Path]:
    """
    Converts a 2D image into 16-bit heightmap and 8-bit normalmap.
    """
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    heightmap_path = output_dir / f"{stem}_heightmap.png"
    normalmap_path = output_dir / f"{stem}_normalmap.png"

    # 1. Load image (handle Unicode paths safely via cv2.imdecode or PIL)
    pil_img = Image.open(input_path).convert("RGB")
    rgb_arr = np.array(pil_img)
    gray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)

    # 2. Gaussian Blur to eliminate stepping artifacts and smooth terrain
    ksize = blur_radius if blur_radius % 2 != 0 else blur_radius + 1
    if ksize < 3:
        ksize = 3
    blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)

    # 3. Normalize to 16-bit uint16 (0 to 65535)
    norm_float = blurred.astype(np.float32)
    min_val, max_val = norm_float.min(), norm_float.max()
    if max_val > min_val:
        normalized = (norm_float - min_val) / (max_val - min_val)
    else:
        normalized = np.zeros_like(norm_float)

    height_16bit = (normalized * 65535.0).clip(0, 65535).astype(np.uint16)

    # Save 16-bit heightmap
    Image.fromarray(height_16bit).save(heightmap_path)

    # 4. Generate Normal Map using Sobel filters
    # Godot uses standard OpenGL normal map (+X right, +Y up, +Z out)
    sobel_x = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)

    # Note: in image coordinates, Y points down. For OpenGL normal map Y is up,
    # so we negate dy to map image gradient to OpenGL coordinates.
    dx = -sobel_x * normal_strength
    dy = sobel_y * normal_strength
    dz = np.ones_like(normalized, dtype=np.float32)

    norm = np.sqrt(dx * dx + dy * dy + dz * dz)
    norm[norm == 0] = 1.0

    nx = dx / norm
    ny = dy / norm
    nz = dz / norm

    # Map [-1, 1] to [0, 255]
    r = ((nx * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    g = ((ny * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)

    normal_rgb = np.stack([r, g, b], axis=-1)
    Image.fromarray(normal_rgb, mode="RGB").save(normalmap_path)

    return heightmap_path, normalmap_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert 2D map textures to Godot 4 16-bit Heightmap and 3D Normalmap"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=str,
        help="Path to input 2D image file or directory"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="godot_project/assets/terrain_3d",
        help="Destination directory for heightmap and normalmap"
    )
    parser.add_argument(
        "--blur-radius", "-b",
        type=int,
        default=5,
        help="Gaussian blur kernel radius (odd integer, default: 5)"
    )
    parser.add_argument(
        "--normal-strength", "-s",
        type=float,
        default=2.5,
        help="Intensity scale for normal map gradient (default: 2.5)"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    targets = []
    if input_path.is_file():
        targets.append(input_path)
    elif input_path.is_dir():
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            targets.extend(input_path.glob(ext))

    if not targets:
        print(f"No image files found at '{input_path}'.")
        return

    print(f"Processing {len(targets)} file(s)...")
    for target in targets:
        # Ignore already generated height/normal maps
        if target.name.endswith(("_heightmap.png", "_normalmap.png")):
            continue
        h_path, n_path = convert_image(
            target,
            output_dir,
            blur_radius=args.blur_radius,
            normal_strength=args.normal_strength
        )
        print(f"-> Generated: {h_path.name} & {n_path.name}")


if __name__ == "__main__":
    main()
