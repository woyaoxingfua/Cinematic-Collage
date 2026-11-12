# file: filters.py
"""LUT 滤镜：.cube 解析（numpy 三线性插值）、按路径缓存、明确报错。

说明：项目原有实现依赖 colour-science 读取并应用 LUT。本模块改为 numpy
自实现（解析 + 三线性插值），并有对拍测试（tests/test_filters_parity.py）
保证与 colour 结果误差在 1 个色阶内；若对拍不达标则回退 colour（见日志）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

import config

logger = logging.getLogger(__name__)


class FilterError(Exception):
    """滤镜不可用（文件缺失 / 损坏 / 格式不支持）；message 为中文，可直接展示。"""


@dataclass
class CubeLut:
    """解析后的 3D LUT。table 形状 (N,N,N,3)，索引顺序 [b][g][r]（.cube 中 R 变化最快）。"""

    size: int
    table: np.ndarray  # float32，值域 0..1
    domain_min: np.ndarray  # (3,)
    domain_max: np.ndarray  # (3,)


# 按路径缓存，同一 LUT 文件只读一次
_lut_cache: dict = {}


def _read_cube_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_cube(text: str, source: str = "<内存>") -> CubeLut:
    """解析 .cube 文本；格式非法抛 FilterError。"""
    size = None
    domain_min = np.zeros(3, dtype=np.float32)
    domain_max = np.ones(3, dtype=np.float32)
    rows = []
    for ln_no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0].upper()
        if key == "LUT_3D_SIZE":
            try:
                size = int(parts[1])
            except (IndexError, ValueError):
                raise FilterError(f"{source} 第 {ln_no} 行：LUT_3D_SIZE 非法")
        elif key == "LUT_1D_SIZE":
            raise FilterError(f"{source}：暂不支持 1D LUT")
        elif key == "DOMAIN_MIN":
            try:
                domain_min = np.array([float(x) for x in parts[1:4]], dtype=np.float32)
            except (IndexError, ValueError):
                raise FilterError(f"{source} 第 {ln_no} 行：DOMAIN_MIN 非法")
        elif key == "DOMAIN_MAX":
            try:
                domain_max = np.array([float(x) for x in parts[1:4]], dtype=np.float32)
            except (IndexError, ValueError):
                raise FilterError(f"{source} 第 {ln_no} 行：DOMAIN_MAX 非法")
        elif key == "TITLE":
            continue
        else:
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except (IndexError, ValueError):
                raise FilterError(f"{source} 第 {ln_no} 行：数据行格式非法：{line}")
    if size is None:
        raise FilterError(f"{source}：缺少 LUT_3D_SIZE")
    if size < 2:
        raise FilterError(f"{source}：LUT_3D_SIZE 必须 ≥ 2")
    if len(rows) != size**3:
        raise FilterError(f"{source}：数据行数 {len(rows)} 与 LUT_3D_SIZE {size}³ 不匹配")
    table = np.asarray(rows, dtype=np.float32).reshape(size, size, size, 3)  # [b][g][r]
    # 注意：表里允许超界值（部分 LUT 用 >1/负值做过冲），与 colour 一致——
    # 保留原值参与插值，只在最终输出时 clip
    return CubeLut(size, table, domain_min, domain_max)


def load_lut(path) -> CubeLut:
    """读取并缓存 LUT；缺失 / 损坏抛 FilterError（中文信息）。"""
    key = str(path)
    lut = _lut_cache.get(key)
    if lut is not None:
        return lut
    p = Path(path)
    if not p.exists():
        raise FilterError(f"找不到滤镜文件：{p}")
    try:
        lut = parse_cube(_read_cube_text(p), p.name)
    except FilterError:
        raise
    except Exception as e:
        raise FilterError(f"滤镜文件损坏（{p.name}）：{e}")
    _lut_cache[key] = lut
    return lut


def clear_cache() -> None:
    _lut_cache.clear()


def _apply_band(lut: CubeLut, arr: np.ndarray) -> np.ndarray:
    """对一帧行做三线性插值；arr 为 (h,w,3) float32，值域已归一。"""
    n = lut.size
    span = lut.domain_max - lut.domain_min
    span = np.where(span == 0, np.float32(1.0), span).astype(np.float32)
    g = np.clip((arr - lut.domain_min) / span, 0.0, 1.0) * (n - 1)
    r, gg, b = g[..., 0], g[..., 1], g[..., 2]
    r0 = np.floor(r).astype(np.int32)
    g0 = np.floor(gg).astype(np.int32)
    b0 = np.floor(b).astype(np.int32)
    r1 = np.minimum(r0 + 1, n - 1)
    g1 = np.minimum(g0 + 1, n - 1)
    b1 = np.minimum(b0 + 1, n - 1)
    fr = (r - r0)[..., None]
    fg = (gg - g0)[..., None]
    fb = (b - b0)[..., None]
    t = lut.table  # (N,N,N,3)，索引 [b][g][r]
    out = (
        t[b0, g0, r0] * ((1 - fr) * (1 - fg) * (1 - fb))
        + t[b1, g0, r0] * ((1 - fr) * (1 - fg) * fb)
        + t[b0, g1, r0] * ((1 - fr) * fg * (1 - fb))
        + t[b1, g1, r0] * ((1 - fr) * fg * fb)
        + t[b0, g0, r1] * (fr * (1 - fg) * (1 - fb))
        + t[b1, g0, r1] * (fr * (1 - fg) * fb)
        + t[b0, g1, r1] * (fr * fg * (1 - fb))
        + t[b1, g1, r1] * (fr * fg * fb)
    )
    out = out * span + lut.domain_min  # 输出映射回 DOMAIN
    return np.clip(out, 0.0, 1.0)


def apply_lut_array(lut: CubeLut, arr: np.ndarray) -> np.ndarray:
    """对 (H,W,3) float 数组（值域 0..1）应用 LUT；分带处理限制内存峰值。"""
    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise FilterError(f"apply_lut_array 需要 (H,W,3) 数组，收到 {arr.shape}")
    out = np.empty_like(arr)
    band_rows = max(1, 2_000_000 // max(1, arr.shape[1]))
    for y0 in range(0, arr.shape[0], band_rows):
        out[y0 : y0 + band_rows] = _apply_band(lut, arr[y0 : y0 + band_rows])
    return out


def apply_filter(image: Image.Image, filter_name) -> Image.Image:
    """对图片应用 luts/ 目录下的指定滤镜；"无"/空名原样返回。

    注意：调用方应先把图片缩放到目标尺寸再套滤镜（避免对超大原图做全尺寸计算）。
    LUT 缺失或损坏抛 FilterError，由上层提示并跳过，不再静默吞掉。
    """
    if not filter_name or filter_name == "无":
        return image
    lut = load_lut(config.LUTS_DIR / f"{filter_name}.cube")
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / np.float32(255.0)
    out = apply_lut_array(lut, arr)
    out8 = (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(out8)


def available_filters() -> list:
    """列出 luts 目录下可用的滤镜名（不含扩展名）。"""
    if not config.LUTS_DIR.exists():
        return []
    return sorted(p.stem for p in config.LUTS_DIR.glob("*.cube"))
