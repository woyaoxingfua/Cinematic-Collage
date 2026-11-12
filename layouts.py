# file: layouts.py
"""布局渲染（阶段 2 重写）。

- 所有布局实现 Layout 接口并注册到 LAYOUTS 注册表，新增布局只需注册即可被 UI 使用
- 所有尺寸都是「基准值 × scale」，不再跨文件手抄魔法数字
- render() 返回 RenderResult（成图 + 每张照片的 Slot），文字通过 slots 定位
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image, ImageDraw

import imaging
import textdraw

logger = logging.getLogger(__name__)


def _s(base, scale) -> int:
    """基准值 × scale，四舍五入，至少为 1。"""
    return max(1, int(round(base * scale)))


@dataclass
class Slot:
    """一张照片在成图中的位置。"""

    x: int
    y: int
    w: int
    h: int

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def right(self) -> int:
        return self.x + self.w


@dataclass
class RenderResult:
    """布局渲染结果：成图 + 每张照片的位置（供文字定位与测试校验）。"""

    image: Image.Image
    slots: list


class Layout:
    """布局基类：子类设置 name / min_photos / max_photos 并实现两个方法。"""

    name = ""
    min_photos = 1
    max_photos = 1

    def photo_width(self, scale) -> int:
        """该布局需要的照片目标宽度（基准值 × scale）。"""
        raise NotImplementedError

    def render(self, photos, texts, font, scale=1.0, **opts) -> RenderResult:
        """渲染布局。texts 与 photos 一一对应；font 为 textdraw.FontFamily。"""
        raise NotImplementedError

    def check_count(self, n) -> None:
        if not (self.min_photos <= n <= self.max_photos):
            raise ValueError(f"布局「{self.name}」需要 {self.count_hint()}，实际收到 {n} 张")

    def count_hint(self) -> str:
        """给用户看的照片数量提示，如「2–6 张照片」。"""
        if self.min_photos == self.max_photos:
            return f"{self.min_photos} 张照片"
        return f"{self.min_photos}–{self.max_photos} 张照片"


# 布局注册表：UI 与 pipeline 按名字查找
LAYOUTS: dict = {}


def register(layout: Layout) -> None:
    LAYOUTS[layout.name] = layout


def get(name) -> Layout:
    try:
        return LAYOUTS[name]
    except KeyError:
        raise ValueError(f"未知布局：{name}（可用：{'、'.join(LAYOUTS)}）") from None


# ===================================================================
# 电影竖排
# ===================================================================
class FilmStripLayout(Layout):
    """电影竖排：黑色胶卷边框 + 两侧齿孔，2–6 张照片纵向排列。"""

    name = "电影竖排"
    min_photos = 2
    max_photos = 6

    PHOTO_W = 600  # 照片区宽度（基准）
    SIDEBAR = 60   # 两侧边条宽度
    GAP = 25       # 「保留间隙」模式下照片之间的间隙
    HOLE = 12      # 齿孔边长
    HOLE_SPACING = 30  # 齿孔纵向间距
    CANVAS_BG = (10, 10, 10)
    HOLE_COLOR = (32, 32, 32)

    TEXT_SIZE = 28   # 配文字号上限
    TEXT_MIN = 14    # 配文字号下限（再小就截断）
    TEXT_PAD = 20    # 文字距照片边缘
    TEXT_MAX_H = 120  # 单张照片上文字区最大高度

    def photo_width(self, scale) -> int:
        return _s(self.PHOTO_W, scale)

    def render(self, photos, texts, font, scale=1.0, style="保留间隙", **_) -> RenderResult:
        self.check_count(len(photos))
        n = len(photos)
        texts = list(texts or [])
        texts = (texts + [""] * n)[:n]

        pw, sw = _s(self.PHOTO_W, scale), _s(self.SIDEBAR, scale)
        gap = _s(self.GAP, scale) if style == "保留间隙" else 0
        hole = max(2, _s(self.HOLE, scale))
        hole_margin = max(1, (sw - hole) // 2)
        hole_spacing = max(hole * 2, _s(self.HOLE_SPACING, scale))

        # 统一照片宽度（窄图会被放大到目标宽度，与旧版行为一致）
        imgs = [imaging.resize_exact_width(im, pw) for im in photos]
        total_h = sum(im.height for im in imgs) + gap * (n - 1)
        total_w = sw * 2 + pw

        canvas = Image.new("RGB", (total_w, total_h), self.CANVAS_BG)
        draw = ImageDraw.Draw(canvas)
        slots = []
        pad = _s(self.TEXT_PAD, scale)
        tmax, tmin = _s(self.TEXT_SIZE, scale), _s(self.TEXT_MIN, scale)
        tmax_h = _s(self.TEXT_MAX_H, scale)

        y = 0
        for i, im in enumerate(imgs):
            canvas.paste(im, (sw, y))
            slot = Slot(sw, y, pw, im.height)
            slots.append(slot)
            self._draw_caption(draw, slot, texts[i], font, pad, tmax, tmin, tmax_h)
            y += im.height + gap

        # 两侧齿孔
        yy = hole_spacing // 2
        while yy + hole <= total_h:
            draw.rectangle([hole_margin, yy, hole_margin + hole, yy + hole], fill=self.HOLE_COLOR)
            draw.rectangle(
                [total_w - hole_margin - hole, yy, total_w - hole_margin, yy + hole],
                fill=self.HOLE_COLOR,
            )
            yy += hole_spacing

        return RenderResult(canvas, slots)

    def _draw_caption(self, draw, slot: Slot, text, font, pad, tmax, tmin, tmax_h) -> None:
        """在单张照片底部绘制白字黑描边的配文（fit_text 自适应字号）。"""
        text = (text or "").strip()
        if not text:
            return
        box_w = slot.w - pad * 2
        box_h = min(tmax_h, slot.h - pad)
        if box_w <= tmin or box_h < tmin:
            return  # 照片太矮，放不下文字
        lines, size = textdraw.fit_text(text, box_w, box_h, tmax, tmin, font)
        if not lines:
            return
        f = font.at(size)
        line_h = font.measure_line_height(f)
        block_h = len(lines) * line_h
        y0 = slot.bottom - pad - block_h
        textdraw.draw_lines(
            draw,
            lines,
            slot.x + pad,
            y0,
            f,
            (240, 240, 240),
            line_h=line_h,
            stroke_width=max(1, size // 14),
            stroke_fill=(0, 0, 0),
        )


# ===================================================================
# 单张海报
# ===================================================================
class PosterLayout(Layout):
    """单张海报：非对称「拍立得 / 画廊打印」风格，白边 + 底部宽留白放文字。"""

    name = "单张海报"
    min_photos = 1
    max_photos = 1

    MAX_W = 800       # 照片最大宽度（基准；只缩不放）
    SIDE = 50         # 上 / 左 / 右边框宽度
    MIN_BOTTOM = 180  # 底部留白最小值
    TEXT_GAP = 40     # 文字与照片、文字与画布底边的边距
    TEXT_CAP = 400    # 文字区高度上限（基准，防超长文字撑爆画布）
    TEXT_SIZE = 40
    TEXT_MIN = 18
    FRAME = (255, 255, 255)
    TEXT_COLOR = (50, 50, 50)

    def photo_width(self, scale) -> int:
        return _s(self.MAX_W, scale)

    def render(self, photos, texts, font, scale=1.0, **_) -> RenderResult:
        self.check_count(len(photos))
        text = ""
        if texts:
            text = (texts[0] or "").strip()

        max_w, side = _s(self.MAX_W, scale), _s(self.SIDE, scale)
        min_bottom = _s(self.MIN_BOTTOM, scale)
        gap = _s(self.TEXT_GAP, scale)

        im = imaging.resize_to_width(photos[0], max_w)  # 只缩不放
        canvas_w = side * 2 + im.width
        box_w = im.width  # 文字区宽度与照片同宽

        # 先排好文字，再定画布高度
        lines, size = [], 0
        if text:
            cap = max(min_bottom * 2, _s(self.TEXT_CAP, scale))
            lines, size = textdraw.fit_text(
                text, box_w, cap, _s(self.TEXT_SIZE, scale), _s(self.TEXT_MIN, scale), font
            )
        block_h = 0.0
        f = None
        line_h = 0.0
        if lines:
            f = font.at(size)
            line_h = font.measure_line_height(f)
            block_h = len(lines) * line_h

        # 底部留白 = max(最小值, 文字高度 + 上下边距)
        if lines:
            bottom = max(min_bottom, int(round(block_h)) + gap * 2)
        else:
            bottom = min_bottom
        canvas_h = side + im.height + bottom

        canvas = Image.new("RGB", (canvas_w, canvas_h), self.FRAME)
        canvas.paste(im, (side, side))
        if lines:
            # 文字在底部留白里垂直居中、水平居中
            y0 = side + im.height + (bottom - block_h) / 2
            draw = ImageDraw.Draw(canvas)
            textdraw.draw_lines(
                draw, lines, side, y0, f, self.TEXT_COLOR,
                line_h=line_h, align="center", max_width=box_w,
            )
        return RenderResult(canvas, [Slot(side, side, im.width, im.height)])


# 注册全部布局（新增布局在这里 register 即可）
register(FilmStripLayout())
register(PosterLayout())
