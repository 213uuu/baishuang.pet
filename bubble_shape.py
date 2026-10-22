"""云朵形对话气泡的几何与配色。

运行时只依赖标准库。几何做法：把若干椭圆求并集，再从中心按角度做径向采样，
得到一条没有内部接缝的云朵轮廓；最后归一化到 [-0.5, 0.5] 并缓存，
桌面端按气泡尺寸缩放即可。
"""

from __future__ import annotations

import math

BUBBLE_FILL = "#ffffff"
BUBBLE_STROKE = "#c9a9ee"
BUBBLE_TEXT = "#9678cf"

# (中心 x, 中心 y, 半径 x, 半径 y)，坐标以气泡宽高为 1。
_ELLIPSES = [
    (0.00, 0.02, 0.30, 0.30),
    (-0.24, 0.06, 0.20, 0.25),
    (0.24, 0.06, 0.20, 0.25),
    (-0.20, -0.17, 0.15, 0.22),
    (-0.02, -0.20, 0.19, 0.24),
    (0.16, -0.17, 0.15, 0.21),
    (-0.22, 0.24, 0.15, 0.14),
    (0.02, 0.26, 0.18, 0.13),
    (0.22, 0.24, 0.14, 0.12),
]
_OUTLINE_CENTER = (0.0, 0.0)
_OUTLINE_SPAN = (1.0, 1.0)


def _inside(x: float, y: float) -> bool:
    # 中央安全内腔：不改变云朵外轮廓，只填平多行文字会碰到的浅凹口。
    if abs(x) <= 0.40 and abs(y) <= 0.30:
        return True
    for ex, ey, rx, ry in _ELLIPSES:
        dx = (x - ex) / rx
        dy = (y - ey) / ry
        if dx * dx + dy * dy <= 1.0:
            return True
    return False


def _build_outline(samples: int = 220) -> list[tuple[float, float]]:
    global _OUTLINE_CENTER, _OUTLINE_SPAN
    raw: list[tuple[float, float]] = []
    for i in range(samples):
        theta = 2 * math.pi * i / samples
        dx, dy = math.cos(theta), math.sin(theta)
        lo, hi = 0.0, 1.6
        for _ in range(26):
            mid = (lo + hi) / 2
            if _inside(mid * dx, mid * dy):
                lo = mid
            else:
                hi = mid
        raw.append((lo * dx, lo * dy))

    min_x = min(p[0] for p in raw)
    max_x = max(p[0] for p in raw)
    min_y = min(p[1] for p in raw)
    max_y = max(p[1] for p in raw)
    span_x = max_x - min_x
    span_y = max_y - min_y
    _OUTLINE_CENTER = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    _OUTLINE_SPAN = (span_x, span_y)
    return [
        ((x - _OUTLINE_CENTER[0]) / span_x, (y - _OUTLINE_CENTER[1]) / span_y)
        for x, y in raw
    ]


_OUTLINE = _build_outline()


def cloud_points(cx: float, cy: float, width: float, height: float) -> list[tuple[float, float]]:
    """返回闭合云朵轮廓点，坐标已按气泡中心与尺寸缩放。"""
    return [(cx + nx * width, cy + ny * height) for nx, ny in _OUTLINE]


def cloud_contains_normalized(x: float, y: float) -> bool:
    """判断以气泡中心为原点的归一化坐标是否位于云朵内部。"""
    raw_x = x * _OUTLINE_SPAN[0] + _OUTLINE_CENTER[0]
    raw_y = y * _OUTLINE_SPAN[1] + _OUTLINE_CENTER[1]
    return _inside(raw_x, raw_y)
