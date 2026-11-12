# file: pipeline.py
"""生成流程（阶段 4）：读图 → 缩放 → 滤镜 → AI 文案 → 排版渲染。

不依赖 Tk，UI 与测试共用同一入口 build()。
「重新渲染」传 texts 复用文案即可避免重复调用 AI。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import ai_connector  # 仅用其 AiError 类型
import filters
import imaging
import layouts
import textdraw

logger = logging.getLogger(__name__)


@dataclass
class BuildOptions:
    """一次生成的全部选项（UI 收集，pipeline 执行）。"""

    layout: str = "电影竖排"
    strip_style: str = "保留间隙"
    text_style: str = "经典底部"  # 经典底部 / 电影字幕
    aspect: str = "原始"          # 电影竖排统一画幅：原始 / 3:2 / 4:3 / 1:1
    filter_name: str = "无"
    font_name: str = "默认"
    content_style: str = "简体短句"
    scale: float = 2.0
    ai_enabled: bool = True
    extra_prompt: str = ""  # 追加到 AI 提示词的自定义风格要求


@dataclass
class BuildResult:
    """生成结果：成图、每张照片的位置、最终文案与警告。"""

    image: Image.Image
    slots: list
    texts: list
    used_filter: str = "无"
    warnings: list = field(default_factory=list)


def build(image_paths, options: BuildOptions, ai_client=None, texts=None, image_cache=None) -> BuildResult:
    """生成成品。

    - texts 不为 None 时直接使用（不调 AI）；为 None 时按 ai_enabled / ai_client 决定
    - ai_client 需提供 get_ai_texts(photos, content_style, extra_prompt) 接口
    - image_cache: dict[str(path), Image]，跨次调用复用已读照片（换设置不重读图）
    """
    paths = [Path(p) for p in image_paths]
    layout = layouts.get(options.layout)
    layout.check_count(len(paths))
    warnings = []

    # 1. 读图（带缓存）
    photos = []
    for p in paths:
        key = str(p)
        img = image_cache.get(key) if image_cache is not None else None
        if img is None:
            img = imaging.load_image(p)
            if image_cache is not None:
                image_cache[key] = img
        photos.append(img)

    # 2. 先缩放到目标尺寸再套滤镜（不对超大原图做全尺寸计算）
    target_w = layout.photo_width(options.scale)
    resized = [imaging.resize_to_width(im, target_w) for im in photos]

    # 3. 滤镜：缺失 / 损坏 → 记警告并跳过，不中断生成
    used_filter = "无"
    if options.filter_name and options.filter_name != "无":
        try:
            resized = [filters.apply_filter(im, options.filter_name) for im in resized]
            used_filter = options.filter_name
        except filters.FilterError as e:
            logger.warning(f"滤镜不可用，已跳过：{e}")
            warnings.append(f"滤镜「{options.filter_name}」不可用，已跳过（{e}）")

    # 4. AI 文案：texts 已提供则跳过（重新渲染不重复调 AI）
    n = len(photos)
    if texts is None:
        if options.ai_enabled and ai_client is not None:
            try:
                texts = ai_client.get_ai_texts(resized, options.content_style, options.extra_prompt)
            except ai_connector.AiError as e:
                # AI 失败不阻断出图：留空文案，用户可手动补写后重新渲染
                logger.warning(f"AI 配文失败：{e}")
                warnings.append(f"AI 配文失败：{e}")
        else:
            texts = []
    texts = (list(texts or []) + [""] * n)[:n]

    # 5. 渲染
    family = textdraw.family_from_name(options.font_name)
    result = layout.render(
        resized, texts, family,
        scale=options.scale,
        style=options.strip_style,
        text_style=options.text_style,
        aspect=options.aspect,
    )
    return BuildResult(result.image, result.slots, texts, used_filter, warnings)
