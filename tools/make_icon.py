# -*- coding: utf-8 -*-
"""生成 ``assets/study_timer.ico`` —— 仅开发期使用的图标生成脚本。

运行时（打包后的 exe）**不需要** Pillow：图标是入库的静态资源，
本脚本只在修改图标时手动跑一次。

用法：

    python tools/make_icon.py
    python tools/make_icon.py --preview

设计约束（为什么这么做）：

- 品牌色 ``#4f6df5`` 圆角方块 + 白色粗对勾（打卡语义）。
- 尺寸 >= 64 时在对勾外围加一圈细白时钟环；更小的尺寸只保留对勾，
  保证 16x16 下依然可辨识（细节在 16px 上只会变成噪点）。
- 每个尺寸**单独按比例重绘**（超采样后 LANCZOS 缩放），而不是把一张
  1024 主图整体缩小：小尺寸可以用更粗的笔画与更大的占比，避免糊成一团。

只依赖 Pillow（开发期）。
"""

from __future__ import annotations

import argparse
import struct
import sys
from io import BytesIO
from pathlib import Path
from typing import List, Sequence, Tuple

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - 开发期工具的友好提示
    print("缺少 Pillow，请先安装：pip install pillow", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------- 设计常量
#: 品牌蓝 #4f6df5 的上下渐变端点（顶部略亮，底部略深）
GRADIENT_TOP: Tuple[int, int, int] = (106, 133, 247)
GRADIENT_BOTTOM: Tuple[int, int, int] = (63, 92, 230)
WHITE: Tuple[int, int, int, int] = (255, 255, 255, 255)

#: 圆角半径占画布比例（1024 下约 220）
RADIUS_RATIO: float = 220 / 1024
#: 方块内缩占比，留一点透明边让图标显得不贴边
INSET_RATIO: float = 0.015

#: 时钟环：中心 0.5，半径 / 线宽占画布比例
RING_RADIUS_RATIO: float = 0.325
RING_WIDTH_RATIO: float = 0.030
#: 小于该尺寸时不画时钟环（画了也看不清）
RING_MIN_SIZE: int = 64

#: 对勾折线（比例坐标）：起点 → 拐点 → 终点
CHECK_POINTS_RING: Sequence[Tuple[float, float]] = (
    (0.300, 0.510),
    (0.440, 0.650),
    (0.700, 0.370),
)
CHECK_WIDTH_RING: float = 0.098

CHECK_POINTS_SOLID: Sequence[Tuple[float, float]] = (
    (0.255, 0.530),
    (0.425, 0.700),
    (0.755, 0.315),
)
CHECK_WIDTH_SOLID: float = 0.155

#: 生成的 ico 包含的全部尺寸（Windows 会按场景挑最合适的一档）
ICON_SIZES: Tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
ICON_PATH: Path = PROJECT_ROOT / "assets" / "study_timer.ico"
PREVIEW_PATH: Path = PROJECT_ROOT / "build" / "icon_preview.png"


# ---------------------------------------------------------------- 绘图
def _supersample(size: int) -> int:
    """超采样倍率：小图放大倍数更高，保证 16px 的边缘也干净。"""
    return 8 if size <= 64 else 4


def _brand_gradient(canvas: int) -> Image.Image:
    """垂直线性渐变（顶亮底深），用作圆角方块的底色。"""
    strip = Image.new("RGBA", (1, canvas))
    pixels = strip.load()
    span = max(1, canvas - 1)
    for y in range(canvas):
        ratio = y / span
        color = tuple(
            int(round(GRADIENT_TOP[i] + (GRADIENT_BOTTOM[i] - GRADIENT_TOP[i]) * ratio))
            for i in range(3)
        )
        pixels[0, y] = (color[0], color[1], color[2], 255)
    return strip.resize((canvas, canvas), Image.Resampling.NEAREST)


def _rounded_mask(canvas: int) -> Image.Image:
    """圆角方块遮罩（L 模式），用于把渐变裁成 App 图标的轮廓。"""
    inset = int(round(canvas * INSET_RATIO))
    mask = Image.new("L", (canvas, canvas), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (inset, inset, canvas - 1 - inset, canvas - 1 - inset),
        radius=int(round(canvas * RADIUS_RATIO)),
        fill=255,
    )
    return mask


def _scale_points(points: Sequence[Tuple[float, float]], canvas: int) -> List[Tuple[float, float]]:
    """比例坐标 → 像素坐标。"""
    return [(x * canvas, y * canvas) for x, y in points]


def _stroke_polyline(draw: ImageDraw.ImageDraw,
                     points: Sequence[Tuple[float, float]],
                     width: float,
                     fill: Tuple[int, int, int, int]) -> None:
    """画一条带圆角拐点与圆头端点的折线（模拟“粗笔对勾”）。"""
    line_width = max(1, int(round(width)))
    draw.line(list(points), fill=fill, width=line_width, joint="curve")
    radius = line_width / 2
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _draw_ring(draw: ImageDraw.ImageDraw, canvas: int) -> None:
    """对勾外围的细白时钟环。"""
    radius = canvas * RING_RADIUS_RATIO
    center = canvas / 2
    width = max(1, int(round(canvas * RING_WIDTH_RATIO)))
    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        outline=WHITE,
        width=width,
    )


def render(size: int) -> Image.Image:
    """按目标尺寸单独绘制一枚图标（返回 RGBA 图）。"""
    scale = _supersample(size)
    canvas = size * scale

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    image.paste(_brand_gradient(canvas), (0, 0), _rounded_mask(canvas))

    draw = ImageDraw.Draw(image)
    if size >= RING_MIN_SIZE:
        _draw_ring(draw, canvas)
        points = _scale_points(CHECK_POINTS_RING, canvas)
        width = canvas * CHECK_WIDTH_RING
    else:
        points = _scale_points(CHECK_POINTS_SOLID, canvas)
        width = canvas * CHECK_WIDTH_SOLID
    _stroke_polyline(draw, points, width, WHITE)

    return image.resize((size, size), Image.Resampling.LANCZOS)


# ---------------------------------------------------------------- ICO 封装
def _png_payload(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def write_ico(path: Path, images: Sequence[Image.Image]) -> None:
    """手写 ICO 容器：每个尺寸一帧 PNG（与 Pillow 自身写入行为一致）。

    ICONDIR(6) + N * ICONDIRENTRY(16) + N * PNG 数据。
    """
    payloads = [_png_payload(image) for image in images]
    count = len(images)
    offset = 6 + 16 * count

    header = struct.pack("<HHH", 0, 1, count)  # reserved / type=1(icon) / count
    entries = bytearray()
    for image, payload in zip(images, payloads):
        width, height = image.size
        entries += struct.pack(
            "<BBBBHHII",
            width % 256,      # 256 在 ICO 里记为 0
            height % 256,
            0,                # 调色板颜色数（真彩为 0）
            0,                # reserved
            1,                # color planes
            32,               # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(entries) + b"".join(payloads))


# ---------------------------------------------------------------- 预览
def write_preview(images: Sequence[Image.Image], path: Path) -> Path:
    """拼一张预览图：浅色 / 深色背景下各尺寸原大 + 小尺寸 4 倍放大。"""
    gap = 18
    row_height = 150
    light = (244, 245, 247, 255)
    dark = (30, 31, 36, 255)

    zooms = [image for image in images if image.size[0] <= 48]
    zoom_width = sum(image.size[0] * 4 + gap for image in zooms) + gap
    width = max(sum(image.size[0] + gap for image in images) + gap, zoom_width)
    height = row_height * 3

    sheet = Image.new("RGBA", (width, height), light)
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, row_height, width, row_height * 2), fill=dark)

    for row, background in ((0, light), (1, dark)):
        x = gap
        top = row * row_height + (row_height - max(i.size[1] for i in images)) // 2
        for image in images:
            sheet.paste(image, (x, top + (max(i.size[1] for i in images) - image.size[1]) // 2), image)
            x += image.size[0] + gap

    x = gap
    top = row_height * 2 + 12
    for image in zooms:
        zoomed = image.resize((image.size[0] * 4, image.size[1] * 4), Image.Resampling.NEAREST)
        sheet.paste(zoomed, (x, top), zoomed)
        x += zoomed.size[0] + gap

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(path, format="PNG")
    return path


# ---------------------------------------------------------------- 入口
def build_icon(sizes: Sequence[int] = ICON_SIZES) -> List[Image.Image]:
    """渲染全部尺寸并返回图像列表（供测试 / 预览复用）。"""
    return [render(size) for size in sizes]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 StudyTimer 应用图标")
    parser.add_argument("--output", default=str(ICON_PATH), help="ico 输出路径")
    parser.add_argument("--preview", action="store_true", help="额外生成预览图")
    args = parser.parse_args(argv)

    images = build_icon()
    output = Path(args.output)
    write_ico(output, images)

    total = output.stat().st_size
    print(f"已生成 {output}（{len(images)} 个尺寸，共 {total} 字节）")
    print("尺寸：" + ", ".join(f"{image.size[0]}x{image.size[1]}" for image in images))

    if args.preview:
        preview = write_preview(images, PREVIEW_PATH)
        print(f"预览图 {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
