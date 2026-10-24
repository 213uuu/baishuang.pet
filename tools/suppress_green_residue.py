#!/usr/bin/env python3
"""Neutralize green-biased sprite residue without changing alpha or key pixels."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


def suppress_green_residue(
    image: Image.Image,
    darken_factor: float,
    minimum_spill: int,
) -> tuple[Image.Image, int]:
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA")

    source = np.asarray(image, dtype=np.uint8)
    if image.mode == "RGB":
        output = source.copy()
        alpha = np.full(source.shape[:2], 255, dtype=np.uint8)
    else:
        output = source.copy()
        alpha = source[..., 3]

    r = source[..., 0].astype(np.int16)
    g = source[..., 1].astype(np.int16)
    b = source[..., 2].astype(np.int16)
    max_red_or_blue = np.maximum(r, b)
    spill = g - max_red_or_blue
    exact_chroma = (r == 0) & (g == 255) & (b == 0)

    candidate = (
        (alpha >= 8)
        & ~exact_chroma
        & (g >= minimum_spill)
        & (spill >= minimum_spill)
        & ((spill >= 12) | (spill * 32 >= max_red_or_blue))
    )

    strength = np.clip((spill - 3.0) / 9.0, 0.0, 1.0)
    capped_green = np.minimum(g, max_red_or_blue)
    luma = (
        0.2126 * r
        + 0.7152 * capped_green
        + 0.0722 * b
    )
    target = np.minimum(64.0, np.rint(luma * darken_factor))
    target = np.minimum(target, np.minimum(r, np.minimum(capped_green, b)))
    darken = candidate & (luma < 180.0)
    neutralize_highlight_green = candidate & ~darken

    for channel in range(3):
        mixed = np.rint(
            source[..., channel]
            + (target - source[..., channel]) * strength
        )
        output[..., channel] = np.where(
            darken,
            np.clip(mixed, 0, 255),
            source[..., channel],
        ).astype(np.uint8)
    output[..., 1] = np.where(
        neutralize_highlight_green,
        max_red_or_blue,
        output[..., 1],
    ).astype(np.uint8)
    candidate_max_red_or_blue = np.maximum(output[..., 0], output[..., 2])
    output[..., 1] = np.where(
        candidate & (output[..., 1] > candidate_max_red_or_blue),
        candidate_max_red_or_blue,
        output[..., 1],
    ).astype(np.uint8)

    background = (alpha <= 8) | exact_chroma
    if np.any(background):
        padded_background = np.pad(background, 1, constant_values=True)
        near_background = np.zeros_like(background)
        for row_offset in range(3):
            for column_offset in range(3):
                if row_offset == 1 and column_offset == 1:
                    continue
                near_background |= padded_background[
                    row_offset:row_offset + background.shape[0],
                    column_offset:column_offset + background.shape[1],
                ]
        boundary = ~background & near_background
    else:
        boundary = np.zeros_like(background)
    output_max_red_or_blue = np.maximum(output[..., 0], output[..., 2])
    edge_green_cast = boundary & (output[..., 1] > output_max_red_or_blue)
    output[..., 1] = np.where(
        edge_green_cast,
        output_max_red_or_blue,
        output[..., 1],
    ).astype(np.uint8)

    changed = int(
        np.count_nonzero(
            np.any(output[..., :3] != source[..., :3], axis=2)
        )
    )
    if not changed:
        return image.copy(), 0
    return Image.fromarray(output, mode=image.mode), changed


def process_tree(
    input_root: Path,
    output_root: Path,
    darken_factor: float,
    minimum_spill: int,
) -> dict[str, int]:
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")

    files = sorted(input_root.rglob("*.png"))
    if not files:
        raise FileNotFoundError(f"no PNG frames found under: {input_root}")

    counts: dict[str, int] = defaultdict(int)
    output_root.mkdir(parents=True)
    for source_path in files:
        relative = source_path.relative_to(input_root)
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            processed, changed = suppress_green_residue(
                image,
                darken_factor,
                minimum_spill,
            )
        processed.save(destination, format="PNG")
        group = relative.parts[0] if len(relative.parts) > 1 else "<root>"
        counts[group] += changed
    return dict(counts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Darken green-biased residue in chroma-keyed sprite frames."
    )
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--darken-factor", type=float, default=0.32)
    parser.add_argument("--minimum-spill", type=int, default=4)
    args = parser.parse_args()
    if not 0.05 <= args.darken_factor <= 1.0:
        parser.error("--darken-factor must be between 0.05 and 1.0")
    if not 1 <= args.minimum_spill <= 64:
        parser.error("--minimum-spill must be between 1 and 64")
    return args


def main() -> None:
    args = parse_args()
    counts = process_tree(
        args.input_root.resolve(),
        args.output_root.resolve(),
        args.darken_factor,
        args.minimum_spill,
    )
    for name, changed in sorted(counts.items()):
        print(f"{name:<25} {changed:>8} green-biased pixels neutralized")
    print(f"total frames: {sum(1 for _ in args.input_root.rglob('*.png'))}")


if __name__ == "__main__":
    main()
