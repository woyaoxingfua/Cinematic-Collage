# file: ai_connector.py（阶段 3 重写）
"""AI 配文：OpenAI 兼容接口调用与结果解析。

设计要点：
- import 本模块不做任何网络/配置操作（缺 .env 不崩溃）
- 客户端延迟创建，带 timeout 与 max_retries=2
- 一次请求发 N 张缩小图（长边 ≤1024、JPEG quality 85），比发整张拼图省 token，
  也不受胶卷边框干扰；服务商不支持多图（BadRequest）时自动降级为逐张请求
- 失败一律抛 AiError（中文信息），绝不把报错文字当文案返回
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import types

import openai
from PIL import Image

import config

logger = logging.getLogger(__name__)


class AiError(Exception):
    """AI 调用失败；message 为可直接展示给用户的中文提示。"""


_client = None


def get_client():
    """延迟创建客户端（首次调用才读配置）；未配置时抛 AiError。"""
    global _client
    if _client is None:
        cfg = config.load_config()
        if not cfg.is_ready:
            raise AiError("尚未配置 AI：" + cfg.summary())
        _client = openai.OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
            max_retries=2,
        )
        logger.info(f"AI 客户端已创建（模型 {cfg.model}）")
    return _client


def set_client(client) -> None:
    """注入客户端（测试用）；传 None 恢复延迟创建。"""
    global _client
    _client = client


def reset_client() -> None:
    set_client(None)


# ===================================================================
# 提示词
# ===================================================================
STYLE_PROMPTS = {
    "简体短句": "请为每张照片生成一句有电影感的简体中文短句。",
    "繁体诗歌": "請為每張照片創作一句充滿詩意、富有想像的繁體中文短詩。",
    "英文散文": "Please write one short, atmospheric, poetic sentence in English for each photo.",
}


def build_prompt(content_style: str, n: int, extra_prompt: str = "") -> str:
    """按内容风格与照片数生成提示词；JSON 示例按 N 动态生成。"""
    style = STYLE_PROMPTS.get(content_style, STYLE_PROMPTS["简体短句"])
    if content_style == "英文散文":
        length_limit = "Each caption must be at most 15 English words."
    else:
        length_limit = "每条文字不超过 20 个汉字。"
    example = json.dumps(
        {"texts": [f"第{i}张照片的文字" for i in range(1, n + 1)]},
        ensure_ascii=False,
    )
    parts = []
    parts.append(f"这里共有 {n} 张照片，按发送顺序编号。" if n > 1 else "这里有一张照片。")
    parts.append(style)
    parts.append(f"要求：恰好返回 {n} 条文字；{length_limit}不要在文字里使用引号。")
    if extra_prompt and extra_prompt.strip():
        parts.append("额外的风格要求：" + extra_prompt.strip())
    parts.append("请严格按照以下 JSON 格式返回，不要有任何额外说明：")
    parts.append(example)
    return "\n".join(parts)


def _to_data_url(image: Image.Image, max_edge: int = 1024, quality: int = 85) -> str:
    """照片缩小到长边 ≤1024 后转 JPEG base64 data URL（控制 token）。"""
    im = image
    if max(im.size) > max_edge:
        ratio = max_edge / max(im.size)
        im = image.resize(
            (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _build_content(content_style: str, photos, extra_prompt: str = "") -> list:
    """构造多模态消息 content：1 段提示词 + N 张图。"""
    content = [{"type": "text", "text": build_prompt(content_style, len(photos), extra_prompt)}]
    for p in photos:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(p)}})
    return content


# ===================================================================
# 请求与异常映射
# ===================================================================
def _call_model(client, cfg, content) -> str:
    """单次请求；异常映射为 AiError（中文）。BadRequestError 原样上抛以便多图降级。"""
    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=cfg.max_tokens,
        )
    except openai.BadRequestError:
        raise  # 可能是「不支持一次多图」，由上层降级为逐张请求
    except openai.AuthenticationError:
        raise AiError("API Key 无效，请检查 .env 中的 OPENAI_API_KEY") from None
    except openai.NotFoundError:
        raise AiError("模型不存在，请检查 .env 中的 OPENAI_MODEL（必须是支持图片的视觉模型）") from None
    except openai.RateLimitError:
        raise AiError("AI 请求被限流，请稍等片刻再试") from None
    except openai.APITimeoutError:
        raise AiError("AI 请求超时，请稍后重试") from None
    except openai.APIConnectionError:
        raise AiError("无法连接 AI 服务器，请检查网络与 .env 中的 OPENAI_API_BASE") from None
    except openai.APIStatusError as e:
        raise AiError(f"AI 服务返回错误（HTTP {e.status_code}）") from None
    except AiError:
        raise
    except Exception as e:
        raise AiError(f"AI 调用失败：{e}") from None
    choices = getattr(resp, "choices", None)
    if not choices:
        raise AiError("AI 返回了空回复")
    return (choices[0].message.content or "").strip()


def get_ai_texts(photos, content_style: str, extra_prompt: str = "") -> list:
    """为 N 张照片生成配文，返回恰好 N 条文字。

    失败抛 AiError；服务商不支持一次多图时自动降级为逐张请求。
    """
    n = len(photos)
    if n == 0:
        return []
    client = get_client()
    cfg = config.load_config()

    try:
        return parse_texts(_call_model(client, cfg, _build_content(content_style, photos, extra_prompt)), n)
    except openai.BadRequestError as e:
        logger.warning(f"多图请求被拒绝（{e}），降级为逐张请求")
        texts = []
        for p in photos:
            raw = _call_model(client, cfg, _build_content(content_style, [p], extra_prompt))
            texts.append(parse_texts(raw, 1)[0])
        return texts


# ===================================================================
# 结果解析
# ===================================================================
_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.S)


def parse_texts(raw, n: int) -> list:
    """把 AI 回复解析成恰好 n 条文字。

    - 去掉 ```json 围栏；从文本中提取第一个配平的 {...} 或 [...]
    - 支持 {"texts": [...]} 与纯数组；非字符串元素转 str（None → 空串）
    - 不足补空串、过多截断；完全解析失败时按换行拆分兜底
    - 空回复抛 AiError（不能静默给用户空白成品）
    """
    if raw is None:
        raise AiError("AI 返回了空回复")
    text = str(raw).strip()
    if not text:
        raise AiError("AI 返回了空回复")

    candidate = text
    m = _FENCE_RE.search(candidate)
    if m and m.group(1).strip():
        candidate = m.group(1).strip()

    payload = _extract_json(candidate)
    if payload is not None:
        try:
            texts = _normalize_texts(json.loads(payload))
            if texts is not None:
                return _fit_count(texts, n)
        except json.JSONDecodeError:
            logger.warning(f"JSON 解析失败，按换行拆分兜底：{payload[:120]}")

    # 兜底：按换行拆分（去掉空行）
    lines = [ln.strip() for ln in candidate.splitlines() if ln.strip()]
    if not lines:
        raise AiError("AI 返回了无法解析的内容")
    return _fit_count(lines, n)


def _extract_json(text: str):
    """提取第一个配平的 {...} 或 [...]（括号在字符串内时忽略）。"""
    best = None
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start != -1 and (best is None or start < best[0]):
            best = (start, opener, closer)
    if best is None:
        return None
    start, opener, closer = best
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None  # 没有配平的括号


def _normalize_texts(data):
    """dict 取 texts 键、list 原样；元素统一转 str；结构不符返回 None。"""
    if isinstance(data, dict):
        if "texts" not in data:
            return None
        data = data["texts"]
    if not isinstance(data, list):
        return None
    out = []
    for x in data:
        if x is None:
            out.append("")
        elif isinstance(x, str):
            out.append(x.strip())
        else:
            out.append(str(x).strip())
    return out


def _fit_count(texts, n: int) -> list:
    """截断到 n 条；不足补空串。"""
    texts = [str(t) for t in texts][:n]
    while len(texts) < n:
        texts.append("")
    return texts
