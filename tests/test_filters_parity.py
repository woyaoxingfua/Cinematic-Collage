# tests/test_filters_parity.py —— numpy 实现与 colour-science 的对拍
# 门槛：平均误差 < 1 个色阶、最大 < 3（达不到则回退 colour，见 REFACTOR_LOG）
import numpy as np
import pytest
from PIL import Image

import config
import filters
from tests.helpers import make_photo

colour = pytest.importorskip("colour")


def _sample_array(seed=7):
    """确定性的伪随机测试图（覆盖 0-1 值域）。"""
    rng = np.random.default_rng(seed)
    return rng.random((64, 96, 3)).astype(np.float32)


def _to8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def _parity(cube_path):
    lut_colour = colour.io.luts.read_LUT(str(cube_path))
    lut_numpy = filters.load_lut(cube_path)
    arr = _sample_array()
    a = _to8(lut_colour.apply(arr.astype(np.float64)))
    b = _to8(filters.apply_lut_array(lut_numpy, arr))
    diff = np.abs(a.astype(int) - b.astype(int))
    return diff.mean(), diff.max()


def test_parity_repo_luts():
    """与仓库自带的三个 LUT 对拍。"""
    for name in ("BlueArchitecture", "ColdChrome", "复古电"):
        mean_err, max_err = _parity(config.LUTS_DIR / f"{name}.cube")
        assert mean_err < 1.0, f"{name}：平均误差 {mean_err:.3f} 超过 1 个色阶"
        assert max_err < 3.0, f"{name}：最大误差 {max_err} 超过 3 个色阶"


def test_parity_identity(tmp_path):
    n = 17
    lines = ['TITLE "identity"', f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                lines.append(f"{r / (n - 1):.6f} {g / (n - 1):.6f} {b / (n - 1):.6f}")
    p = tmp_path / "identity.cube"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mean_err, max_err = _parity(p)
    assert mean_err < 1.0 and max_err < 3.0
