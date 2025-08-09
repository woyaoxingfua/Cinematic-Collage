# file: ai_connector.py (针对性修正版)

import openai
import os
from dotenv import load_dotenv
import base64
import io
from PIL import Image
import json

# --- 1. 加载环境变量 ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_API_BASE")

# 检查配置是否齐全
if not api_key or not base_url:
    raise ValueError("错误：请在 .env 文件中设置好 OPENAI_API_KEY 和 OPENAI_API_BASE")

client = openai.OpenAI(api_key=api_key, base_url=base_url)


def generate_prompt(content_style, num_photos):
    # ... 这个函数保持不变 ...
    prompts = {
        "简体短句": "请为图片生成一句有电影感的简体中文短句。",
        "繁体诗歌": "請為圖片創作一句充滿詩意、富有想像的繁體中文詩。",
        "英文散文": "Please write a short, atmospheric, and poetic sentence in English for the image."
    }
    base_prompt = prompts.get(content_style, prompts["简体短句"])
    if num_photos > 1:
        return (f"这是一组由{num_photos}张照片拼接而成的图片。"
                f"请你从上到下，分别为每一张照片生成一句对应的文字描述。"
                f"文字风格要求：{base_prompt}"
                f"请严格按照这个JSON格式返回，不要有任何额外说明: "
                f"{{\"texts\": [\"第一张照片的文字\", \"第二张照片的文字\", \"第三张照片的文字\"]}}")
    else:
        return (f"{base_prompt}"
                f"请严格按照这个JSON格式返回，不要有任何额外说明: "
                f"{{\"texts\": [\"文字内容\"]}}")


def get_ai_text(image: Image.Image, content_style: str, num_photos: int):
    try:
        buffered = io.BytesIO()
        image.convert("RGB").save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        prompt = generate_prompt(content_style, num_photos)

        # --- 2. 【核心修正】替换成您的服务商提供的、支持视觉功能的模型名称 ---
        # 警告：您示例中的 "Qwen/Qwen2.5-72B-Instruct" 很可能不支持视觉。
        # 您需要查找服务商文档，找到类似 Qwen-VL, Yi-VL, LLaVA 等多模态模型。
        # 我在这里先使用一个常见的开源视觉模型名称作为示例，您需要替换成您可用的模型。
        vision_model_name = "stepfun-ai/step3"  # <--- 请在这里填入您服务商提供的【正确视觉模型】名称！

        print(f"正在使用模型 '{vision_model_name}' 向AI发送请求...")

        messages_payload = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ]

        response = client.chat.completions.create(
            model=vision_model_name,  # 使用正确的模型变量
            messages=messages_payload,
            max_tokens=200,
            # stream=False, # 我们暂时不使用流式传输，以简化代码
            # response_format={"type": "json_object"} # 您的服务商可能不支持此参数，我们先注释掉以提高兼容性
        )

        raw_result_text = response.choices[0].message.content.strip()
        print(f"AI原始返回结果: '{raw_result_text}'")

        if not raw_result_text:
            print("AI返回了空内容。")
            return ["AI未能生成文本"]

        try:
            data = json.loads(raw_result_text)
            return data.get("texts", [f"AI返回了未知格式: {raw_result_text}"])
        except json.JSONDecodeError:
            print("AI未返回标准JSON，已按普通文本处理。")
            return [raw_result_text]

    except Exception as e:
        print(f"调用AI API时发生错误: {e}")
        return [f"AI调用失败: {e}"]