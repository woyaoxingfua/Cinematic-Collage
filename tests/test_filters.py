# tests/test_filters.py —— LUT 解析 / 缓存 / 应用 / 报错
import numpy as np
import pytest
from PIL import Image

import config
import filters
from tests.helpers import make_photo


def _identity_cube_text(n):
    """生成 n³ 的 identity .cube 文本。"""
    lines = ['TITLE "identity"', f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                lines.append(f"{r / (n - 1):.6f} {g / (n - 1):.6f} {b / (n - 1):.6f}")
    return "\n".join(lines) + "\n"


def test_identity_lut_error_within_1_level(tmp_path):
    cube = tmp_path / "identity33.cube"
    cube.write_text(_identity_cube_text(33), encoding="utf-8")
    lut = filters.load_lut(cube)
    # 覆盖 0-255 全值域的渐变图
    arr = np.zeros((16, 256, 3), dtype=np.uint8)
    arr[..., 0] = np.arange(256)[None, :]
    arr[..., 1] = np.arange(256)[None, :]
    arr[..., 2] = 128
    out = filters.apply_lut_array(lut, arr.astype(np.float32) / 255.0)
    out8 = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
    diff = np.abs(out8.astype(int) - arr.astype(int))
    assert diff.max() <= 1


def test_lut_cache_reads_file_only_once(tmp_path, monkeypatch):
    cube = tmp_path / "tiny.cube"
    cube.write_text(_identity_cube_text(2), encoding="utf-8")
    calls = []
    orig = filters._read_cube_text

    def counting(path):
        calls.append(str(path))
        return orig(path)

    monkeypatch.setattr(filters, "_read_cube_text", counting)
    filters.clear_cache()
    try:
        lut1 = filters.load_lut(cube)
        lut2 = filters.load_lut(cube)
        assert lut1 is lut2
        assert len(calls) == 1
    finally:
        filters.clear_cache()


def test_missing_lut_raises_filter_error(tmp_path):
    with pytest.raises(filters.FilterError):
        filters.load_lut(tmp_path / "不存在的滤镜.cube")


def test_corrupt_lut_raises_filter_error(tmp_path):
    p = tmp_path / "broken.cube"
    p.write_text("LUT_3D_SIZE 4\n0.1 0.2 0.3\n", encoding="utf-8")  # 行数不足
    with pytest.raises(filters.FilterError):
        filters.load_lut(p)


def test_cube_without_size_raises(tmp_path):
    p = tmp_path / "nosize.cube"
    p.write_text("0.1 0.2 0.3\n", encoding="utf-8")
    with pytest.raises(filters.FilterError):
        filters.load_lut(p)


def test_no_filter_passthrough():
    im = make_photo(60, 40)
    assert filters.apply_filter(im, "无") is im
    assert filters.apply_filter(im, "") is im
    assert filters.apply_filter(im, None) is im


def test_missing_named_filter_raises_for_apply():
    im = make_photo(60, 40)
    with pytest.raises(filters.FilterError):
        filters.apply_filter(im, "绝不存在的滤镜")


def test_available_filters_lists_repo_luts():
    names = filters.available_filters()
    assert "BlueArchitecture" in names
    assert "ColdChrome" in names


def test_real_lut_changes_image():
    im = make_photo(120, 90)
    out = filters.apply_filter(im, "BlueArchitecture")
    assert out.size == im.size
    diff = np.abs(
        np.asarray(out, dtype=int) - np.asarray(im.convert("RGB"), dtype=int)
    )
    assert diff.mean() > 0.5  # 滤镜确实改变了颜色
