# tests/test_layouts.py —— 布局接口：注册表 / 尺寸公式 / slots 校验
import itertools

import pytest

import layouts
import textdraw
from tests.helpers import make_photo

family = textdraw.default_family()


def _photos(n, w=400, h=300):
    return [make_photo(w, h, i) for i in range(n)]


def _assert_slots_valid(slots, img_w, img_h):
    for s in slots:
        assert 0 <= s.x and 0 <= s.y
        assert s.x + s.w <= img_w and s.y + s.h <= img_h
        assert s.w > 0 and s.h > 0
    for a, b in itertools.combinations(slots, 2):
        no_overlap = (
            a.x + a.w <= b.x or b.x + b.w <= a.x
            or a.y + a.h <= b.y or b.y + b.h <= a.y
        )
        assert no_overlap, f"slots 重叠：{a} 与 {b}"


def test_registry_and_unknown_layout():
    assert "电影竖排" in layouts.LAYOUTS
    assert "单张海报" in layouts.LAYOUTS
    with pytest.raises(ValueError):
        layouts.get("不存在的布局")


def test_film_strip_size_formula_scale1_gap():
    photos = _photos(3)  # 400x300 → 600 宽时高 450
    r = layouts.get("电影竖排").render(photos, ["一", "二", "三"], family, scale=1.0, style="保留间隙")
    assert r.image.size == (60 * 2 + 600, 450 * 3 + 25 * 2)
    assert [ (s.x, s.w) for s in r.slots ] == [(60, 600)] * 3
    assert r.slots[0].y == 0
    assert r.slots[1].y == 450 + 25
    _assert_slots_valid(r.slots, *r.image.size)


def test_film_strip_seamless():
    photos = _photos(3)
    r = layouts.get("电影竖排").render(photos, None, family, scale=1.0, style="无缝拼接")
    assert r.image.size == (720, 450 * 3)
    assert r.slots[1].y == 450
    _assert_slots_valid(r.slots, *r.image.size)


def test_film_strip_scale2():
    photos = _photos(3)
    r = layouts.get("电影竖排").render(photos, ["a", "b", "c"], family, scale=2.0, style="保留间隙")
    # 2×：照片宽 1200 高 900，边条 120，间隙 50
    assert r.image.size == (120 * 2 + 1200, 900 * 3 + 50 * 2)
    _assert_slots_valid(r.slots, *r.image.size)


def test_film_strip_accepts_2_to_6_photos():
    strip = layouts.get("电影竖排")
    for n in (2, 5, 6):
        r = strip.render(_photos(n), None, family, scale=1.0)
        assert len(r.slots) == n
    for n in (1, 7):
        with pytest.raises(ValueError):
            strip.render(_photos(n), None, family, scale=1.0)


def test_film_strip_upscales_narrow_photo():
    photos = [make_photo(300, 200, 0), make_photo(500, 400, 1)]
    r = layouts.get("电影竖排").render(photos, None, family, scale=1.0)
    assert all(s.w == 600 for s in r.slots)
    assert r.slots[0].h == 400  # 300x200 → 600 宽等比到 400 高


def test_film_strip_text_drawn_changes_pixels():
    photos = _photos(2)
    plain = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0).image
    with_text = layouts.get("电影竖排").render(
        photos, ["山风穿过旧巷", "夏天的最后一页"], family, scale=1.0).image
    assert plain.size == with_text.size
    # 有字的图与无字图必然不同
    import numpy as np
    assert not np.array_equal(np.asarray(plain), np.asarray(with_text))


def test_poster_size_and_slot_without_text():
    photo = make_photo(1000, 800)  # 800 宽上限 → 缩到 800x640
    r = layouts.get("单张海报").render([photo], [], family, scale=1.0)
    assert r.image.size == (50 * 2 + 800, 50 + 640 + 180)
    s = r.slots[0]
    assert (s.x, s.y, s.w, s.h) == (50, 50, 800, 640)
    _assert_slots_valid(r.slots, *r.image.size)


def test_poster_text_expands_bottom_padding():
    photo = make_photo(1000, 800)
    empty = layouts.get("单张海报").render([photo], [""], family, scale=1.0).image
    long_text = "夜色温柔，灯火渐暗，风停了，雨还会来吗？她说再见然后转身，走了很久很久，故事还很长，长到足够把整个夏天重新讲一遍。"
    filled = layouts.get("单张海报").render([photo], [long_text], family, scale=1.0).image
    assert filled.height > empty.height  # 文字撑高了底部留白
    assert filled.width == empty.width


def test_poster_narrow_photo_not_upscaled():
    photo = make_photo(500, 400)
    r = layouts.get("单张海报").render([photo], ["短文案"], family, scale=1.0)
    assert r.image.width == 50 * 2 + 500


def test_poster_requires_exactly_one_photo():
    poster = layouts.get("单张海报")
    with pytest.raises(ValueError):
        poster.render(_photos(2), None, family, scale=1.0)


def test_extra_texts_are_ignored():
    photos = _photos(2)
    r = layouts.get("电影竖排").render(
        photos, ["一", "二", "三", "四"], family, scale=1.0)
    assert len(r.slots) == 2  # 多余文字被忽略，不崩溃
