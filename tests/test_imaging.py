# tests/test_imaging.py —— 读图规范化：EXIF 转正 / RGB 统一 / 尺寸限制
import numpy as np
from PIL import Image

import imaging


def test_exif_orientation_6_swaps_dimensions(tmp_path):
    """orientation=6 的 JPEG 读入后宽高互换（转正）。"""
    img = Image.new("RGB", (400, 300), (200, 30, 30))
    ex = Image.Exif()
    ex[274] = 6  # EXIF Orientation
    p = tmp_path / "o6.jpg"
    img.save(p, exif=ex)
    loaded = imaging.load_image(p)
    assert loaded.size == (300, 400)


def test_exif_orientation_1_keeps_dimensions(tmp_path):
    img = Image.new("RGB", (400, 300), (30, 200, 30))
    ex = Image.Exif()
    ex[274] = 1
    p = tmp_path / "o1.jpg"
    img.save(p, exif=ex)
    assert imaging.load_image(p).size == (400, 300)


def test_rgba_gets_white_background(tmp_path):
    """RGBA 透明区域铺白底，不透明区域保留原色。"""
    arr = np.zeros((50, 100, 4), dtype=np.uint8)
    arr[..., 0:3] = (255, 0, 0)
    arr[:50, :50, 3] = 255  # 左半透明红，右半全透明
    p = tmp_path / "alpha.png"
    Image.fromarray(arr).save(p)
    loaded = imaging.load_image(p)
    assert loaded.mode == "RGB"
    left = loaded.getpixel((5, 25))
    right = loaded.getpixel((95, 25))
    assert left == (255, 0, 0)
    assert right == (255, 255, 255)


def test_palette_with_transparency_becomes_rgb_white(tmp_path):
    img = Image.new("RGBA", (60, 60), (0, 0, 255, 0))  # 全透明蓝
    p = tmp_path / "pal.png"
    img.convert("P").save(p)  # 带 transparency 的 P 模式
    loaded = imaging.load_image(p)
    assert loaded.mode == "RGB"
    assert loaded.getpixel((30, 30)) == (255, 255, 255)


def test_cmyk_converted_to_rgb(tmp_path):
    p = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (80, 60), (0, 0, 0, 0)).save(p)
    loaded = imaging.load_image(p)
    assert loaded.mode == "RGB"


def test_long_edge_capped(tmp_path):
    arr = np.zeros((100, 3500, 3), dtype=np.uint8)
    p = tmp_path / "wide.png"
    Image.fromarray(arr).save(p)
    loaded = imaging.load_image(p)
    assert max(loaded.size) == imaging.MAX_LONG_EDGE
    # 短边按同一比例等比缩小（3500→3000 时 100→86）
    assert loaded.height == round(100 * 3000 / 3500)


def test_resize_to_width_only_downscales():
    im = Image.new("RGB", (800, 600), (10, 10, 10))
    small = imaging.resize_to_width(im, 400)
    assert small.size == (400, 300)
    same = imaging.resize_to_width(im, 1600)
    assert same is im  # 不放大


def test_resize_exact_width_upscales():
    im = Image.new("RGB", (300, 200), (10, 10, 10))
    out = imaging.resize_exact_width(im, 600)
    assert out.size == (600, 400)


def test_crop_to_fill_and_aspect():
    im = Image.new("RGB", (400, 200), (9, 9, 9))
    out = imaging.crop_to_fill(im, 100, 100)
    assert out.size == (100, 100)
    out2 = imaging.crop_to_aspect(im, 1, 1)  # 方形
    assert out2.size == (200, 200)
