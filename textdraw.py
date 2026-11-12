# file: textdraw.py
"""文字排版：字体解析（含回退链）、中英文混合换行、自适应字号与绘制。

修掉的历史问题：
- 旧代码字体名选「默认」时把 None 传给 ImageFont.truetype 直接 AttributeError 崩溃
- 逐字 textbbox 测宽很慢，且中文按字、英文按词的规则没有区分
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)

# 禁则：这些标点不允许出现在行首（避头标点）
NO_LINE_START = "，。！？、；：”’）》】』」…—～·,.!?;:)]}%"

# 英文单词：字母数字串，允许中间带 ' - （如 it's、well-known）
_WORD_RE = re.compile(r"[0-9A-Za-z]+(?:['\u2019\-][0-9A-Za-z]+)*")


def _system_font_candidates() -> list:
    """按平台给出系统中文字体候选路径（按优先级）。"""
    if sys.platform == "win32":
        return [
            Path("C:/Windows/Fonts/msyh.ttc"),    # 微软雅黑
            Path("C:/Windows/Fonts/simhei.ttf"),  # 黑体
        ]
    if sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/STHeiti Light.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    return [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc"),
    ]


class FontFamily:
    """一个可按任意字号生成 ImageFont 的字体族。

    candidates 里第一个存在的文件生效；都不存在则回退 Pillow 默认字体。
    """

    def __init__(self, candidates, label: str):
        self.candidates = [Path(p) for p in candidates if p]
        self.path = next((p for p in self.candidates if p.exists()), None)
        self.label = label
        if self.path is None:
            logger.warning(f"字体「{label}」无可用文件，将回退 Pillow 默认字体")

    def at(self, size: int) -> ImageFont.ImageFont:
        """生成指定字号的字体；truetype 失败时逐级回退，绝不抛异常。"""
        size = max(1, int(size))
        if self.path is not None:
            try:
                return ImageFont.truetype(str(self.path), size)
            except OSError as e:  # 文件损坏等
                logger.error(f"加载字体 {self.path} 失败：{e}，回退默认字体")
        try:
            return ImageFont.load_default(size=size)  # Pillow >= 10.1
        except TypeError:
            return ImageFont.load_default()

    def measure_line_height(self, font: ImageFont.ImageFont) -> float:
        """一行文字的行高（ascent + descent），取不到时按字号估计。"""
        try:
            ascent, descent = font.getmetrics()
            return float(ascent + descent)
        except Exception:
            return getattr(font, "size", 12) * 1.25


def _bundled_fallback() -> list:
    """仓库自带字体，作为系统字体全都没有时的兜底。"""
    candidates = []
    for name in ("手写体.ttf",):
        p = config.FONTS_DIR / name
        if p.exists():
            candidates.append(p)
    # 顺带把 fonts 目录里其他字体也作为候选（排序保证稳定）
    if config.FONTS_DIR.exists():
        for p in sorted(config.FONTS_DIR.glob("*")):
            if p.suffix.lower() in (".ttf", ".otf", ".ttc") and p not in candidates:
                candidates.append(p)
    return candidates


def default_family() -> FontFamily:
    """「默认」字体的解析链：系统中文字体 → 仓库自带字体 → Pillow 默认。"""
    return FontFamily(_system_font_candidates() + _bundled_fallback(), "默认")


def family_from_name(name) -> FontFamily:
    """按 UI 里的字体名解析；名字不存在时回退默认（记日志，不崩溃）。"""
    if not name or name == "默认":
        return default_family()
    path = config.FONTS_DIR / name
    if path.exists():
        return FontFamily([path], name)
    logger.warning(f"字体 {name} 不存在于 fonts 目录，回退默认字体")
    return default_family()


# ===================================================================
# 换行
# ===================================================================
def _tokenize(text: str) -> list:
    """把文本切成不可再分的单元：英文单词整体保留，其他（含中文、标点、空格）按单字符。"""
    tokens = []
    pos = 0
    for m in _WORD_RE.finditer(text):
        if m.start() > pos:
            tokens.extend(text[pos : m.start()])
        tokens.append(m.group())
        pos = m.end()
    if pos < len(text):
        tokens.extend(text[pos:])
    return tokens


def _is_no_line_start(ch: str) -> bool:
    return len(ch) == 1 and ch in NO_LINE_START


def _measure(text: str, font) -> float:
    """用 font.getlength 测宽（比逐字 textbbox 快得多）。"""
    try:
        return float(font.getlength(text))
    except AttributeError:  # 极旧 Pillow 的位图字体
        return float(len(text) * getattr(font, "size", 12) // 2)


def _split_overwide(tok: str, width: float, font) -> list:
    """单个单元超过行宽时按字符硬拆（超长英文单词等罕见情况）。"""
    pieces = []
    cur = ""
    for ch in tok:
        if cur and _measure(cur + ch, font) > width:
            pieces.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        pieces.append(cur)
    return pieces


def wrap_text(text, width, font) -> list:
    """中英文混合换行：中文按字、英文按词；行首避开禁则标点。

    返回行列表；空串返回 []。
    """
    if not text:
        return []
    width = float(width)
    tokens = _tokenize(text)
    lines = []
    cur = ""
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if cur == "" and tok == " ":
            i += 1  # 行首空格直接丢弃
            continue
        if cur and _measure(cur + tok, font) > width:
            if _is_no_line_start(tok):
                # 禁则：闭标点跟随上一行行尾（允许轻微超宽）
                cur += tok
                i += 1
                continue
            lines.append(cur)
            cur = ""
            continue
        if cur == "" and len(tok) > 1 and _measure(tok, font) > width:
            # 行首单元本身超宽：硬拆
            pieces = _split_overwide(tok, width, font)
            lines.extend(pieces[:-1])
            cur = pieces[-1]
            i += 1
            continue
        cur += tok
        i += 1
    if cur:
        lines.append(cur)
    return [ln for ln in (l.strip() for l in lines) if ln]


# ===================================================================
# 自适应字号
# ===================================================================
def _truncate_to_width(s: str, width: float, font) -> str:
    """截断字符串并加省略号，使其宽度不超过 width。"""
    if _measure(s, font) <= width:
        return s
    while s and _measure(s + "…", font) > width:
        s = s[:-1]
    return s + "…"


def fit_text(text, box_w, box_h, max_size, min_size, family: FontFamily):
    """把 text 放进 (box_w, box_h)：从 max_size 逐步缩字号；到下限仍放不下则截断加 …。

    返回 (lines, font_size)；空文本返回 ([], max_size)。
    """
    if not text or not str(text).strip():
        return [], max(int(max_size), 1)
    text = str(text)
    size = max(int(max_size), 1)
    min_size = max(1, int(min_size))
    while size >= min_size:
        font = family.at(size)
        lines = wrap_text(text, box_w, font)
        line_h = family.measure_line_height(font)
        widths_ok = all(_measure(l, font) <= box_w * 1.02 for l in lines)
        if widths_ok and lines and len(lines) * line_h <= box_h:
            return lines, size
        size -= 2
    # 到达下限仍放不下：按 min_size 截断
    font = family.at(min_size)
    line_h = family.measure_line_height(font)
    max_lines = max(1, int(box_h // line_h))
    all_lines = wrap_text(text, box_w, font)
    dropped = len(all_lines) > max_lines  # 有内容放不下，需要省略号提示
    lines = all_lines[:max_lines]
    if not lines:
        lines = [_truncate_to_width(text, box_w, font)]
    elif dropped:
        # 内容被丢弃：最后一行补省略号（再按宽度收一次）
        lines[-1] = _truncate_to_width(lines[-1] + "…", box_w, font)
    # 安全兜底：极端窄盒时只保留真正放得下的行
    while len(lines) > 1 and len(lines) * line_h > box_h:
        lines.pop()
    return lines, min_size


# ===================================================================
# 绘制
# ===================================================================
def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines,
    x,
    y,
    font,
    fill,
    line_h=None,
    align="left",
    max_width=None,
    stroke_width=0,
    stroke_fill=None,
    family: FontFamily | None = None,
):
    """从 (x, y) 开始逐行绘制；align="center" 时以 max_width 为参照水平居中。"""
    if not lines:
        return
    if line_h is None:
        line_h = family.measure_line_height(font) if family is not None else _fallback_line_h(font)
    yy = float(y)
    for line in lines:
        xx = float(x)
        if align == "center" and max_width:
            xx = x + (max_width - _measure(line, font)) / 2
        draw.text(
            (xx, yy),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        yy += line_h
    return yy - line_h  # 返回最后一行的基线 y（便于上层继续排版）


def _fallback_line_h(font) -> float:
    try:
        ascent, descent = font.getmetrics()
        return float(ascent + descent)
    except Exception:
        return getattr(font, "size", 12) * 1.25


def make_draw(image: Image.Image) -> ImageDraw.ImageDraw:
    """便捷方法：为图片创建绘制对象（RGB 模式安全）。"""
    return ImageDraw.Draw(image)
