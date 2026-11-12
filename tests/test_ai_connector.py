# tests/test_ai_connector.py —— AI 层：解析器 / 异常映射 / 多图请求与降级（全部 mock，不碰真实 API）
import base64
import importlib
import io
import json
import types

import httpx
import openai
import pytest
from PIL import Image

import ai_connector
import config
from tests.helpers import make_photo


# ===================================================================
# mock 基础设施
# ===================================================================
class FakeResponse:
    def __init__(self, content):
        msg = types.SimpleNamespace(content=content)
        self.choices = [types.SimpleNamespace(message=msg)]


class FakeCompletions:
    def __init__(self, behavior):
        self.behavior = behavior  # callable(kwargs) -> FakeResponse 或抛异常
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.behavior(kwargs)


class FakeClient:
    def __init__(self, behavior):
        self.chat = types.SimpleNamespace(completions=FakeCompletions(behavior))

    @property
    def calls(self):
        return self.chat.completions.calls


def _http_error(cls, status, message):
    """构造 openai 的 HTTP 错误（需要 httpx.Request/Response）。"""
    req = httpx.Request("POST", "https://api.test.local/v1/chat/completions")
    resp = httpx.Response(status, request=req, json={"error": {"message": message}})
    return cls(message, response=resp, body=None)


@pytest.fixture
def inject():
    """注入 mock 客户端；测试结束自动还原。"""
    installed = []

    def _install(behavior):
        client = FakeClient(behavior)
        installed.append(client)
        ai_connector.set_client(client)
        return client

    yield _install
    ai_connector.reset_client()


def _reply(content):
    return lambda kwargs: FakeResponse(content)


def _images_in(kwargs):
    return [c for c in kwargs["messages"][0]["content"] if c["type"] == "image_url"]


# ===================================================================
# import 安全 / 配置
# ===================================================================
def test_import_without_env_is_safe(monkeypatch, tmp_path):
    """缺 .env、缺环境变量时 import（reload）不报错。"""
    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "不存在的.env")
    importlib.reload(ai_connector)  # 不应抛异常
    ai_connector.reset_client()


def test_get_client_without_config_raises(monkeypatch, tmp_path):
    ai_connector.reset_client()
    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "不存在的.env")
    with pytest.raises(ai_connector.AiError, match="尚未配置"):
        ai_connector.get_client()
    ai_connector.reset_client()


# ===================================================================
# 提示词
# ===================================================================
def test_build_prompt_dynamic_example():
    p3 = ai_connector.build_prompt("简体短句", 3)
    assert "3 张照片" in p3
    assert json.dumps({"texts": ["第1张照片的文字", "第2张照片的文字", "第3张照片的文字"]},
                      ensure_ascii=False) in p3
    p1 = ai_connector.build_prompt("英文散文", 1)
    assert "15 English words" in p1
    assert "第1张照片的文字" in p1
    px = ai_connector.build_prompt("简体短句", 2, extra_prompt="带一点乡愁")
    assert "带一点乡愁" in px


def test_to_data_url_downscales():
    big = make_photo(3000, 2000)
    url = ai_connector._to_data_url(big)
    assert url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    assert img.format == "JPEG"
    assert max(img.size) <= 1024


# ===================================================================
# parse_texts：各种回复形态
# ===================================================================
def test_parse_fenced_json():
    assert ai_connector.parse_texts('```json\n{"texts": ["一", "二", "三"]}\n```', 3) == ["一", "二", "三"]


def test_parse_json_wrapped_in_prose():
    raw = '好的，这是为您生成的文字：\n{"texts": ["山风", "夜色", "灯火"]}\n希望您喜欢！'
    assert ai_connector.parse_texts(raw, 3) == ["山风", "夜色", "灯火"]


def test_parse_plain_array():
    assert ai_connector.parse_texts('["a", "b", "c"]', 3) == ["a", "b", "c"]


def test_parse_empty_reply_raises():
    with pytest.raises(ai_connector.AiError):
        ai_connector.parse_texts("", 3)
    with pytest.raises(ai_connector.AiError):
        ai_connector.parse_texts(None, 3)
    with pytest.raises(ai_connector.AiError):
        ai_connector.parse_texts("   \n  ", 3)


def test_parse_count_mismatch_pads_and_truncates():
    assert ai_connector.parse_texts('{"texts": ["一", "二"]}', 3) == ["一", "二", ""]
    assert ai_connector.parse_texts('{"texts": ["一", "二", "三", "四"]}', 2) == ["一", "二"]


def test_parse_non_string_elements_coerced():
    assert ai_connector.parse_texts('{"texts": [1, 2.5, null, "四"]}', 4) == ["1", "2.5", "", "四"]


def test_parse_fallback_splits_lines():
    assert ai_connector.parse_texts("第一张的文案\n第二张的文案\n第三张的文案", 3) == [
        "第一张的文案", "第二张的文案", "第三张的文案"]
    # 行数不足时补空串
    assert ai_connector.parse_texts("只有一句", 2) == ["只有一句", ""]


def test_parse_unbalanced_brace_falls_back():
    raw = "我把括号弄丢了 {\"texts\": [\"一\""
    assert ai_connector.parse_texts(raw, 2) == [raw.strip(), ""]


# ===================================================================
# get_ai_texts：请求结构与降级
# ===================================================================
def test_request_contains_n_images(inject):
    client = inject(_reply('{"texts": ["一", "二", "三"]}'))
    photos = [make_photo(300, 200, i) for i in range(3)]
    texts = ai_connector.get_ai_texts(photos, "简体短句")
    assert texts == ["一", "二", "三"]
    assert len(client.calls) == 1
    assert len(_images_in(client.calls[0])) == 3


def test_multi_image_fallback_to_single(inject):
    """多图请求被 BadRequest 拒绝时，自动降级为逐张请求。"""

    def behavior(kwargs):
        if len(_images_in(kwargs)) > 1:
            raise _http_error(openai.BadRequestError, 400, "multi-image not supported")
        return FakeResponse('{"texts": ["这张的文案"]}')

    client = inject(behavior)
    photos = [make_photo(300, 200, i) for i in range(3)]
    texts = ai_connector.get_ai_texts(photos, "简体短句")
    assert texts == ["这张的文案"] * 3
    assert len(client.calls) == 1 + 3  # 1 次多图 + 3 次单图
    for call in client.calls[1:]:
        assert len(_images_in(call)) == 1


def test_authentication_error_maps_to_chinese_hint(inject):
    def behavior(kwargs):
        raise _http_error(openai.AuthenticationError, 401, "bad key")

    inject(behavior)
    photos = [make_photo(300, 200)]
    with pytest.raises(ai_connector.AiError, match="API Key"):
        ai_connector.get_ai_texts(photos, "简体短句")


def test_not_found_error_maps_to_model_hint(inject):
    def behavior(kwargs):
        raise _http_error(openai.NotFoundError, 404, "model not found")

    inject(behavior)
    with pytest.raises(ai_connector.AiError, match="视觉模型"):
        ai_connector.get_ai_texts([make_photo(300, 200)], "简体短句")


def test_rate_limit_maps_to_retry_hint(inject):
    def behavior(kwargs):
        raise _http_error(openai.RateLimitError, 429, "slow down")

    inject(behavior)
    with pytest.raises(ai_connector.AiError, match="限流"):
        ai_connector.get_ai_texts([make_photo(300, 200)], "简体短句")


def test_generic_exception_wrapped_as_ai_error(inject):
    def behavior(kwargs):
        raise RuntimeError("boom")

    inject(behavior)
    with pytest.raises(ai_connector.AiError, match="boom"):
        ai_connector.get_ai_texts([make_photo(300, 200)], "简体短句")


def test_empty_choices_raises(inject):
    def behavior(kwargs):
        return types.SimpleNamespace(choices=[])

    inject(behavior)
    with pytest.raises(ai_connector.AiError, match="空回复"):
        ai_connector.get_ai_texts([make_photo(300, 200)], "简体短句")


def test_extra_prompt_reaches_request(inject):
    client = inject(_reply('{"texts": ["一"]}'))
    ai_connector.get_ai_texts([make_photo(300, 200)], "简体短句", extra_prompt="带一点乡愁")
    sent_text = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "带一点乡愁" in sent_text
