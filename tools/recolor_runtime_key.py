#!/usr/bin/env python3
"""Recolor exact source chroma pixels to the dark Tk runtime transparency key."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


DEFAULT_SOURCE_KEY = (0, 255, 0)
DEFAULT_RUNTIME_KEY = (17, 7, 3)


def recolor_runtime_key(
    image: Image.Image,
    source_key: tuple[int, int, int] = DEFAULT_SOURCE_KEY,
    runtime_key: tuple[int, int, int] = DEFAULT_RUNTIME_KEY,
) -> tuple[Image.Image, int]:
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA")

    source = np.asarray(image, dtype=np.uint8)
    output = source.copy()
    key_mask = (
        (source[..., 0] == source_key[0])
        & (source[..., 1] == source_key[1])
        & (source[..., 2] == source_key[2])
    )
    output[key_mask, :3] = runtime_key
    changed = int(np.count_nonzero(key_mask))
    return Image.fromarray(output, mode=image.mode), changed


def process_tree(
    input_root: Path,
    output_root: Path,
    source_key: tuple[int, int, int],
    runtime_key: tuple[int, int, int],
) -> int:
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")

    files = sorted(input_root.rglob("*.png"))
    if not files:
        raise FileNotFoundError(f"no PNG frames found under: {input_root}")

    changed = 0
    output_root.mkdir(parents=True)
    for source_path in files:
        destination = output_root / source_path.relative_to(input_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            processed, frame_changed = recolor_runtime_key(
                image,
                source_key,
                runtime_key,
            )
        processed.save(destination, format="PNG")
        changed += frame_changed
    return changed


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("expected six hexadecimal digits")
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("invalid hexadecimal color") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--source-key", type=parse_hex_color, default=DEFAULT_SOURCE_KEY)
    parser.add_argument("--runtime-key", type=parse_hex_color, default=DEFAULT_RUNTIME_KEY)
    args = parser.parse_args()

    changed = process_tree(
        args.input_root.resolve(),
        args.output_root.resolve(),
        args.source_key,
        args.runtime_key,
    )
    print(f"recolored key pixels: {changed}")


if __name__ == "__main__":
    main()
