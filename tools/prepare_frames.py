#!/usr/bin/env python3
"""把带 alpha 的动画帧处理成"纯绿底 + 硬边缘"的 PNG，供 tkinter 的 -transparentcolor 使用。

必须用带 Pillow 的 Python 运行；
运行时（desktop_pet.py）只需要标准库的 tkinter。

用法：python prepare_frames.py <带alpha的帧目录> <输出目录>
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    source = pathlib.Path(sys.argv[1]).resolve()
    target = pathlib.Path(sys.argv[2]).resolve()
    total = 0
    for state_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        out_dir = target / state_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for png in sorted(state_dir.glob("*.png")):
            image = Image.open(png).convert("RGBA")
            # 硬 alpha：避免半透明边缘在 -transparentcolor 下露绿边
            alpha = image.getchannel("A").point(lambda v: 255 if v > 128 else 0)
            flat = Image.new("RGBA", image.size, (0, 255, 0, 255))
            flat.paste(image, (0, 0), alpha)
            flat.convert("RGB").save(out_dir / png.name)
            total += 1
        print(f"  {state_dir.name}: {len(list(out_dir.glob('*.png')))} 帧")
    print(f"共处理 {total} 帧 -> {target}")


if __name__ == "__main__":
    main()
