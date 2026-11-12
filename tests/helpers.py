# tests/helpers.py —— 测试共用：合成照片（不依赖任何外部图片资源）
import numpy as np
from PIL import Image, ImageDraw


def make_photo(width, height, index=0):
    """生成一张合成照片：彩色渐变底 + 白色几何图形 + 序号，便于区分与目检。"""
    base = (index * 73) % 256
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(base, (base + 128) % 256, width, dtype=np.uint8)[None, :]
    arr[..., 1] = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    arr[..., 2] = (base + 64) % 256
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    lw = max(2, width // 100)
    d.rectangle([width // 10, height // 10, width // 2, height // 5],
                outline=(255, 255, 255), width=lw)
    d.ellipse([width // 2, height // 2, width - width // 10, height - height // 10],
              outline=(255, 255, 255), width=lw)
    d.text((width // 10, height // 2), f"#{index + 1}", fill=(255, 255, 255))
    return img
