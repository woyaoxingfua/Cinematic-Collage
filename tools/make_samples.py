# tools/make_samples.py —— 生成各布局样图到 samples/，供人工目检
# 用法：.venv/Scripts/python.exe tools/make_samples.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import filters  # noqa: E402
import imaging  # noqa: E402
import layouts  # noqa: E402
import textdraw  # noqa: E402
import config  # noqa: E402


def make_photo(width, height, index=0):
    """合成照片：彩色渐变底 + 几何图形 + 序号（与 tests/helpers.py 同思路，供目检）。"""
    base = (index * 73) % 256
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(base, (base + 128) % 256, width, dtype=np.uint8)[None, :]
    arr[..., 1] = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    arr[..., 2] = (base + 64) % 256
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    lw = max(3, width // 80)
    d.rectangle([width // 10, height // 10, width // 2, height // 4],
                outline=(255, 255, 255), width=lw)
    d.ellipse([width // 2, height // 2, width - width // 10, height - height // 6],
              outline=(255, 255, 255), width=lw)
    d.line([(0, height * 2 // 3), (width, height // 3)], fill=(255, 255, 255), width=lw)
    big = textdraw.default_family().at(max(24, width // 12))
    d.text((width // 12, height // 2), f"No.{index + 1}", font=big, fill=(255, 255, 255))
    return img


TEXTS_3 = [
    "山风穿过旧巷，夏天正在离开",
    "The last page of a long summer",
    "夜色温柔，灯火渐暗，风停了",
]
TEXT_LONG = "夜色温柔，灯火渐暗，风停了，雨还会来吗？她说：\u201c再见。\u201d然后转身，走了很久、很久……"
TEXT_EN = "The quiet street keeps every story that ever passed through it."


def main():
    out_dir = config.SAMPLES_DIR
    out_dir.mkdir(exist_ok=True)
    family = textdraw.default_family()
    strip = layouts.get("电影竖排")
    poster = layouts.get("单张海报")
    written = []

    # 三张不同画幅的照片，更接近真实使用
    photos3 = [make_photo(800, 600, 0), make_photo(600, 800, 1), make_photo(900, 500, 2)]

    def save(img, name):
        p = out_dir / name
        img.save(p)
        written.append(p)

    # 电影竖排 ×2 档清晰度 ×2 种样式
    for style, tag in (("保留间隙", "gap"), ("无缝拼接", "seamless")):
        r = strip.render(photos3, TEXTS_3, family, scale=2.0, style=style)
        save(r.image, f"film_strip_{tag}_2x.png")
    r = strip.render(photos3, TEXTS_3, family, scale=1.0, style="保留间隙")
    save(r.image, "film_strip_gap_1x.png")
    r = strip.render(photos3, TEXTS_3, family, scale=3.0, style="保留间隙")
    save(r.image, "film_strip_gap_3x.png")

    # 电影竖排 5 张
    photos5 = photos3 + [make_photo(700, 700, 3), make_photo(640, 480, 4)]
    texts5 = TEXTS_3 + ["第四张的独白", "and the fifth one whispered"]
    r = strip.render(photos5, texts5, family, scale=2.0, style="保留间隙")
    save(r.image, "film_strip_5photos_2x.png")

    # 四宫格
    photos4 = photos3 + [make_photo(700, 700, 3)]
    r = layouts.get("四宫格").render(photos4, TEXTS_3 + ["第四张的独白"], family, scale=2.0)
    save(r.image, "grid4_2x.png")

    # 电影字幕样式
    r = strip.render(photos3, TEXTS_3, family, scale=2.0, style="保留间隙", text_style="电影字幕")
    save(r.image, "film_strip_subtitle_2x.png")

    # 单张海报（长文案 / 短文案 / 空文案）
    r = poster.render([make_photo(1200, 900, 5)], [TEXT_LONG], family, scale=2.0)
    save(r.image, "poster_long_text_2x.png")
    r = poster.render([make_photo(1200, 900, 5)], [TEXT_EN], family, scale=2.0)
    save(r.image, "poster_english_2x.png")
    r = poster.render([make_photo(1200, 900, 5)], [""], family, scale=2.0)
    save(r.image, "poster_no_text_2x.png")

    # 带真实 LUT 滤镜的样张（检验 numpy 实现的观感）
    try:
        target = strip.photo_width(2.0)
        filtered = [filters.apply_filter(imaging.resize_to_width(p, target), "BlueArchitecture")
                    for p in photos3]
        r = strip.render(filtered, TEXTS_3, family, scale=2.0, style="保留间隙")
        save(r.image, "film_strip_filtered_BlueArchitecture_2x.png")
    except filters.FilterError as e:
        print(f"跳过滤镜样张：{e}")

    print(f"已生成 {len(written)} 张样图：")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
