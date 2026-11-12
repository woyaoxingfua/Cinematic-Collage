# tests/test_textstyle.py —— 「电影字幕」文字样式：渐变遮罩 + 居中白字
import numpy as np

import layouts
import pipeline
import textdraw
from tests.helpers import make_photo

family = textdraw.default_family()


def _brightness(img, box):
    """区域平均亮度（0-255）。"""
    x0, y0, x1, y1 = box
    return float(np.asarray(img.crop(box).convert("L")).mean())


def test_film_strip_subtitle_same_size_different_pixels():
    photos = [make_photo(400, 300, i) for i in range(3)]
    classic = layouts.get("电影竖排").render(
        photos, ["山风", "夜色", "灯火"], family, scale=1.0, text_style="经典底部").image
    subtitle = layouts.get("电影竖排").render(
        photos, ["山风", "夜色", "灯火"], family, scale=1.0, text_style="电影字幕").image
    assert classic.size == subtitle.size
    assert not np.array_equal(np.asarray(classic), np.asarray(subtitle))


def test_subtitle_gradient_darkens_bottom():
    """字幕样式下，照片底部因遮罩变暗（比无字幕版本低）。"""
    photos = [make_photo(400, 300, i) for i in range(2)]
    plain = layouts.get("电影竖排").render(
        photos, ["", ""], family, scale=1.0).image
    with_sub = layouts.get("电影竖排").render(
        photos, ["山风穿过旧巷", "夏天的最后一页"], family, scale=1.0, text_style="电影字幕").image
    for s in layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0).slots:
        # 取照片底部 15 像素条带对比
        box = (s.x + 10, s.bottom - 15, s.right - 10, s.bottom - 1)
        assert _brightness(with_sub, box) < _brightness(plain, box)


def test_grid4_subtitle_supported():
    photos = [make_photo(400, 300, i) for i in range(4)]
    classic = layouts.get("四宫格").render(
        photos, ["一", "二", "三", "四"], family, scale=1.0, text_style="经典底部").image
    subtitle = layouts.get("四宫格").render(
        photos, ["一", "二", "三", "四"], family, scale=1.0, text_style="电影字幕").image
    assert classic.size == subtitle.size
    assert not np.array_equal(np.asarray(classic), np.asarray(subtitle))


def test_subtitle_text_is_light_on_dark():
    """字幕文字为纯白（255），画在遮罩上：照片底部区域应存在接近纯白的像素。"""
    photo = make_photo(400, 300, 0)
    r = layouts.get("电影竖排").render(
        [photo, make_photo(400, 300, 1)], ["山风", "夜色"], family, scale=1.0, text_style="电影字幕")
    s = r.slots[0]
    region = np.asarray(r.image.crop((s.x, s.bottom - 80, s.right, s.bottom)))
    assert (region >= 250).any()  # 存在纯白文字像素


def test_pipeline_passes_text_style(tmp_path):
    from pathlib import Path

    paths = []
    for i in range(2):
        p = tmp_path / f"p{i}.png"
        make_photo(300, 200, i).save(p)
        paths.append(Path(p))
    common = dict(layout="电影竖排", scale=1.0, ai_enabled=False, filter_name="无")
    r1 = pipeline.build(paths, pipeline.BuildOptions(**common, text_style="经典底部"), texts=["一", "二"])
    r2 = pipeline.build(paths, pipeline.BuildOptions(**common, text_style="电影字幕"), texts=["一", "二"])
    assert r1.image.size == r2.image.size
    assert not np.array_equal(np.asarray(r1.image), np.asarray(r2.image))
