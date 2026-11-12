# file: ai_connector.py（阶段 1：import 安全化——配置读取与客户端创建全部延迟，缺 .env 不再在 import 时崩溃）
import base64
import io
import json
import logging

import openai
from PIL import Image

import config

logger = logging.getLogger(__name__)

# 延迟创建的客户端（阶段 3 会引入 timeout / max_tokens / AiError）
_client = None


def _get_client():
    """首次调用时才读取配置并创建客户端；未配置时抛中文异常。"""
    global _client
    if _client is None:
        cfg = config.load_config()
        if not cfg.is_ready:
            raise ValueError(cfg.summary())
        _client = openai.OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    return _client


def generate_prompt(content_style, num_photos):
    """按内容风格与照片数生成提示词（阶段 3 会重写为动态 JSON 示例）。"""
    prompts = {
        "简体短句": "请为图片生成一句有电影感的简体中文短句。",
        "繁体诗歌": "請為圖片創作一句充滿詩意、富有想像的繁體中文詩。",
        "英文散文": "Please write a short, atmospheric, and poetic sentence in English for the image.",
    }
    base_prompt = prompts.get(content_style, prompts["简体短句"])
    if num_photos > 1:
        return (
            f"这是一组由{num_photos}张照片拼接而成的图片。"
            f"请你从上到下，分别为每一张照片生成一句对应的文字描述。"
            f"文字风格要求：{base_prompt}"
            f"请严格按照这个JSON格式返回，不要有任何额外说明: "
            f'{{"texts": ["第一张照片的文字", "第二张照片的文字", "第三张照片的文字"]}}'
        )
    else:
        return (
            f"{base_prompt}"
            f"请严格按照这个JSON格式返回，不要有任何额外说明: "
            f'{{"texts": ["文字内容"]}}'
        )


def get_ai_text(image: Image.Image, content_style: str, num_photos: int):
    """旧接口：发给 AI 一张拼好的成图并解析文案（阶段 3 重写为多图请求）。"""
    try:
        buffered = io.BytesIO()
        image.convert("RGB").save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
        prompt = generate_prompt(content_style, num_photos)

        cfg = config.load_config()
        vision_model_name = cfg.model  # 可通过 .env 的 OPENAI_MODEL 覆盖，默认 stepfun-ai/step3
        logger.info(f"正在使用模型 '{vision_model_name}' 向AI发送请求...")

        messages_payload = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ]

        response = _get_client().chat.completions.create(
            model=vision_model_name,
            messages=messages_payload,
            max_tokens=cfg.max_tokens,
        )

        raw_result_text = (response.choices[0].message.content or "").strip()
        logger.info(f"AI原始返回结果: '{raw_result_text}'")

        if not raw_result_text:
            logger.warning("AI返回了空内容。")
            return ["AI未能生成文本"]

        try:
            data = json.loads(raw_result_text)
            return data.get("texts", [f"AI返回了未知格式: {raw_result_text}"])
        except json.JSONDecodeError:
            logger.warning("AI未返回标准JSON，已按普通文本处理。")
            return [raw_result_text]

    except Exception as e:
        logger.error(f"调用AI API时发生错误: {e}")
        return [f"AI调用失败: {e}"]
