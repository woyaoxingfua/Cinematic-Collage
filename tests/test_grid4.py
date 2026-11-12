# tests/test_grid4.py —— 四宫格布局：注册表 / 尺寸公式 / 裁切 / 文案
import numpy as np
import pytest

import layouts
import textdraw
from tests.helpers import make_photo
from tests.test_layouts import _assert_slots_valid

family = textdraw.default_family()


def test_grid4_registered():
    assert "四宫格" in layouts.LAYOUTS
    layout = layouts.get("四宫格")
    assert (layout.min_photos, layout.max_photos) == (4, 4)
    assert "4 张" in layout.count_hint()


def test_grid4_size_formula_scale1():
    photos = [make_photo(400, 300, i) for i in range(4)]
    r = layouts.get("四宫格").render(photos, ["一", "二", "三", "四"], family, scale=1.0)
    assert r.image.size == (25 * 2 + 600 * 2 + 25, 25 * 2 + 450 * 2 + 25)  # (1275, 975)
    assert len(r.slots) == 4
    _assert_slots_valid(r.slots, *r.image.size)


def test_grid4_slots_scale2():
    photos = [make_photo(800, 600, i) for i in range(4)]
    r = layouts.get("四宫格").render(photos, None, family, scale=2.0)
    assert r.image.size == (50 * 2 + 1200 * 2 + 50, 50 * 2 + 900 * 2 + 50)
    _assert_slots_valid(r.slots, *r.image.size)


def test_grid4_crops_photos_to_fill_cells():
    """不同画幅的照片都被居中裁切铺满 600×450 格子。"""
    photos = [make_photo(900, 500, 0), make_photo(500, 900, 1),
              make_photo(300, 300, 2), make_photo(1000, 400, 3)]
    r = layouts.get("四宫格").render(photos, ["", "", "", ""], family, scale=1.0)
    assert all((s.w, s.h) == (600, 450) for s in r.slots)


def test_grid4_requires_exactly_four():
    grid = layouts.get("四宫格")
    for n in (3, 5):
        with pytest.raises(ValueError):
            grid.render([make_photo(300, 200) for _ in range(n)], None, family, scale=1.0)


def test_grid4_text_drawn_changes_pixels():
    photos = [make_photo(400, 300, i) for i in range(4)]
    plain = layouts.get("四宫格").render(photos, ["", "", "", ""], family, scale=1.0).image
    with_text = layouts.get("四宫格").render(
        photos, ["山风", "夜色", "灯火", "长街"], family, scale=1.0).image
    assert plain.size == with_text.size
    assert not np.array_equal(np.asarray(plain), np.asarray(with_text))
