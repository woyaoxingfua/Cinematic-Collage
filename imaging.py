# file: imaging.py
"""图片读取与规范化：EXIF 转正、统一 RGB（透明铺白底）、限制超大尺寸。"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# 长边超过该值先等比缩小，避免内存与后续处理耗时失控
MAX_LONG_EDGE = 3000


def load_image(path) -> Image.Image:
    """读取一张照片并规范化。

    - 按 EXIF orientation 转正（手机竖拍照片不再横躺）
    - RGBA / LA / P(带透明) / CMYK 等统一转 RGB，透明区域铺白底
    - 长边超过 MAX_LONG_EDGE 时等比缩小
    """
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im.load()  # 确保像素已读入内存，脱离文件句柄
    im = _to_rgb_white_bg(im)
    long_edge = max(im.size)
    if long_edge > MAX_LONG_EDGE:
        ratio = MAX_LONG_EDGE / long_edge
        size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
        im = im.resize(size, Image.Resampling.LANCZOS)
        logger.info(f"{Path(path).name} 长边超过 {MAX_LONG_EDGE}，已缩小到 {size}")
    return im


def _to_rgb_white_bg(im: Image.Image) -> Image.Image:
    """统一转 RGB；带透明的模式先铺白底再合成。"""
    if im.mode == "RGB":
        return im
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if has_alpha:
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return im.convert("RGB")


def resize_to_width(im: Image.Image, width: int) -> Image.Image:
    """等比缩放到目标宽度；只缩不放（避免小图被拉糊），宽度已一致则原样返回。"""
    if width <= 0 or im.width <= width:
        return im
    height = max(1, round(im.height * width / im.width))
    return im.resize((width, height), Image.Resampling.LANCZOS)


def resize_exact_width(im: Image.Image, width: int) -> Image.Image:
    """等比缩放到精确目标宽度（必要时放大；电影竖排等需要统一宽度的场景）。"""
    if width <= 0 or im.width == width:
        return im
    height = max(1, round(im.height * width / im.width))
    return im.resize((width, height), Image.Resampling.LANCZOS)


def crop_to_fill(im: Image.Image, width: int, height: int) -> Image.Image:
    """居中裁切并缩放，铺满目标宽高（不变形）。"""
    if im.width / im.height > width / height:
        # 原图更宽：按高度裁宽度
        crop_w = round(im.height * width / height)
        x0 = (im.width - crop_w) // 2
        im = im.crop((x0, 0, x0 + crop_w, im.height))
    else:
        # 原图更高：按宽度裁高度
        crop_h = round(im.width * height / width)
        y0 = (im.height - crop_h) // 2
        im = im.crop((0, y0, im.width, y0 + crop_h))
    if im.size != (width, height):
        im = im.resize((width, height), Image.Resampling.LANCZOS)
    return im


def crop_to_aspect(im: Image.Image, aspect_w: float, aspect_h: float) -> Image.Image:
    """居中裁切到指定宽高比（如 3:2 传 3, 2）。"""
    target = aspect_w / aspect_h
    if im.width / im.height > target:
        crop_w = round(im.height * target)
        x0 = (im.width - crop_w) // 2
        return im.crop((x0, 0, x0 + crop_w, im.height))
    crop_h = round(im.width / target)
    y0 = (im.height - crop_h) // 2
    return im.crop((0, y0, im.width, y0 + crop_h))
