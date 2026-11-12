# tests/test_pipeline.py —— 生成流程：AI 调用次数 / 缓存 / 降级 / 选项
from dataclasses import replace

import pytest

import ai_connector
import imaging
import pipeline
from tests.helpers import make_photo


class CountingAi:
    """mock AI：计数并返回固定文案。"""

    def __init__(self):
        self.calls = 0

    def get_ai_texts(self, photos, content_style, extra_prompt=""):
        self.calls += 1
        return [f"第{i}张的文案" for i in range(1, len(photos) + 1)]


class FailingAi:
    def get_ai_texts(self, photos, content_style, extra_prompt=""):
        raise ai_connector.AiError("模型不存在，请检查 OPENAI_MODEL")


def _save_photos(tmp_path, n=3, w=300, h=200):
    paths = []
    for i in range(n):
        p = tmp_path / f"photo{i}.png"
        make_photo(w, h, i).save(p)
        paths.append(p)
    return paths


def test_first_build_calls_ai_once_then_rerender_keeps_count(tmp_path):
    """核心验收：首次生成调 AI 一次；改字体/滤镜重新渲染后仍是一次。"""
    paths = _save_photos(tmp_path, 3)
    ai = CountingAi()
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, ai_enabled=True)
    r1 = pipeline.build(paths, opts, ai_client=ai, texts=None)
    assert ai.calls == 1
    assert r1.texts == ["第1张的文案", "第2张的文案", "第3张的文案"]

    opts2 = replace(opts, font_name="默认", filter_name="无", strip_style="无缝拼接")
    r2 = pipeline.build(paths, opts2, ai_client=ai, texts=r1.texts)
    assert ai.calls == 1  # 没有重复调用 AI
    assert r2.texts == r1.texts


def test_ai_disabled_returns_empty_texts(tmp_path):
    paths = _save_photos(tmp_path, 2)
    ai = CountingAi()
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, ai_enabled=False)
    r = pipeline.build(paths, opts, ai_client=ai, texts=None)
    assert ai.calls == 0
    assert r.texts == ["", ""]


def test_ai_failure_downgrades_to_warning_not_crash(tmp_path):
    """AI 失败不阻断出图：文案留空 + 警告。"""
    paths = _save_photos(tmp_path, 2)
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, ai_enabled=True)
    r = pipeline.build(paths, opts, ai_client=FailingAi(), texts=None)
    assert r.texts == ["", ""]
    assert any("AI 配文失败" in w for w in r.warnings)


def test_missing_filter_becomes_warning(tmp_path):
    paths = _save_photos(tmp_path, 2)
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, filter_name="绝不存在的滤镜")
    r = pipeline.build(paths, opts, texts=["一", "二"])
    assert r.used_filter == "无"
    assert any("滤镜" in w for w in r.warnings)


def test_real_filter_applied_without_warning(tmp_path):
    paths = _save_photos(tmp_path, 2)
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, filter_name="BlueArchitecture")
    r = pipeline.build(paths, opts, texts=["一", "二"])
    assert r.used_filter == "BlueArchitecture"
    assert r.warnings == []


def test_wrong_photo_count_raises(tmp_path):
    paths = _save_photos(tmp_path, 2)
    opts = pipeline.BuildOptions(layout="单张海报")
    with pytest.raises(ValueError):
        pipeline.build(paths, opts, texts=None)


def test_unknown_layout_raises():
    opts = pipeline.BuildOptions(layout="不存在的布局")
    with pytest.raises(ValueError):
        pipeline.build([], opts)


def test_image_cache_reuses_loaded_photos(tmp_path, monkeypatch):
    """同一组照片第二次生成时不重读文件（缓存命中）。"""
    paths = _save_photos(tmp_path, 3)
    calls = []
    orig = imaging.load_image

    def counting(p):
        calls.append(str(p))
        return orig(p)

    monkeypatch.setattr(pipeline.imaging, "load_image", counting)
    cache = {}
    opts = pipeline.BuildOptions(layout="电影竖排", scale=1.0, ai_enabled=False)
    pipeline.build(paths, opts, texts=None, image_cache=cache)
    pipeline.build(paths, opts, texts=["x"] * 3, image_cache=cache)
    assert len(calls) == 3  # 第二次全部命中缓存


def test_poster_pipeline_dimensions(tmp_path):
    paths = _save_photos(tmp_path, 1, w=2000, h=1500)
    opts = pipeline.BuildOptions(layout="单张海报", scale=2.0, ai_enabled=False)
    r = pipeline.build(paths, opts, texts=["海报文案"])
    # 2000 宽照片 → 目标 1600（只缩不放）；画布 = 100 + 1600 + 100
    assert r.image.width == 1800
    assert len(r.slots) == 1


def test_film_strip_pipeline_dimensions(tmp_path):
    paths = _save_photos(tmp_path, 3)
    opts = pipeline.BuildOptions(layout="电影竖排", scale=2.0, ai_enabled=False)
    r = pipeline.build(paths, opts, texts=["一", "二", "三"])
    # 300x200 → 统一到 1200 宽（高 800）；总宽 = 120*2 + 1200
    assert r.image.width == 1440
    assert [s.w for s in r.slots] == [1200] * 3
    assert r.texts == ["一", "二", "三"]
