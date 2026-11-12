# tests/test_aspect.py —— 电影竖排统一画幅（3:2 / 4:3 / 1:1 裁切）
import pytest

import layouts
import pipeline
import textdraw
from tests.helpers import make_photo
from tests.test_layouts import _assert_slots_valid

family = textdraw.default_family()


def test_aspect_32_all_slots_600x400():
    photos = [make_photo(400, 300, i) for i in range(3)]  # 4:3 原图
    r = layouts.get("电影竖排").render(photos, ["", "", ""], family, scale=1.0,
                                      style="保留间隙", aspect="3:2")
    # 600 宽 × 3:2 → 每张高 400；总高 = 400*3 + 25*2
    assert all((s.w, s.h) == (600, 400) for s in r.slots)
    assert r.image.size == (720, 400 * 3 + 25 * 2)
    _assert_slots_valid(r.slots, *r.image.size)


def test_aspect_11_square_slots():
    photos = [make_photo(400, 300, i) for i in range(2)]
    r = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0,
                                      aspect="1:1")
    assert all((s.w, s.h) == (600, 600) for s in r.slots)
    assert r.image.size == (720, 600 * 2 + 25)


def test_aspect_43_matches_original_ratio():
    photos = [make_photo(800, 600, i) for i in range(2)]  # 本来就是 4:3
    r43 = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0, aspect="4:3")
    r_orig = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0, aspect="原始")
    assert r43.image.size == r_orig.image.size  # 4:3 裁切 4:3 原图 ≈ 无变化


def test_invalid_aspect_falls_back_to_original():
    photos = [make_photo(400, 300, i) for i in range(2)]
    r_bad = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0, aspect="不是画幅")
    r_orig = layouts.get("电影竖排").render(photos, ["", ""], family, scale=1.0, aspect="原始")
    assert r_bad.image.size == r_orig.image.size


def test_other_layouts_ignore_aspect():
    """海报 / 四宫格收到 aspect 参数时静默忽略（不崩溃）。"""
    photo = make_photo(400, 300, 0)
    r = layouts.get("单张海报").render([photo], [""], family, scale=1.0, aspect="3:2")
    assert r.image.width == 50 * 2 + 400
    photos4 = [make_photo(400, 300, i) for i in range(4)]
    r4 = layouts.get("四宫格").render(photos4, ["", "", "", ""], family, scale=1.0, aspect="1:1")
    assert all((s.w, s.h) == (600, 450) for s in r4.slots)  # 四宫格固定 4:3 格子


def test_pipeline_passes_aspect(tmp_path):
    from pathlib import Path

    paths = []
    for i in range(2):
        p = tmp_path / f"p{i}.png"
        make_photo(300, 200, i).save(p)
        paths.append(Path(p))
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, ai_enabled=False, aspect="3:2")
    r = pipeline.build(paths, opts, texts=["一", "二"])
    assert all(s.h == s.w * 2 // 3 for s in r.slots)  # 1200 宽 → 800 高（3:2）
