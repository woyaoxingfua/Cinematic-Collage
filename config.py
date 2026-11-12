# file: config.py
"""集中管理路径、.env 配置与用户设置。

设计原则（阶段 1）：
- import 本模块绝不抛异常、绝不读取 .env（配置延迟到 load_config() 才读）
- 所有路径基于 APP_DIR，程序在任意工作目录下启动都正确
- 日志写滚动的 app.log，绝不记录 API Key
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger(__name__)

# --- 路径常量（全部基于本文件所在目录） ---
APP_DIR = Path(__file__).resolve().parent
FONTS_DIR = APP_DIR / "fonts"
LUTS_DIR = APP_DIR / "luts"
SAMPLES_DIR = APP_DIR / "samples"
TOOLS_DIR = APP_DIR / "tools"
TESTS_DIR = APP_DIR / "tests"
ENV_FILE = APP_DIR / ".env"
LOG_FILE = APP_DIR / "app.log"
SETTINGS_FILE = APP_DIR / "settings.json"

# --- .env 可选键及默认值 ---
DEFAULT_MODEL = "stepfun-ai/step3"
DEFAULT_AI_TIMEOUT = 60
DEFAULT_AI_MAX_TOKENS = 800


def _to_int(value, default: int) -> int:
    """把环境变量安全转成正整数，非法值回退默认。"""
    try:
        n = int(str(value).strip())
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


@dataclass
class AppConfig:
    """load_config() 的返回值；缺配置时 is_ready=False 并带中文原因。"""

    api_key: str = ""
    base_url: str = ""
    model: str = DEFAULT_MODEL
    timeout: int = DEFAULT_AI_TIMEOUT
    max_tokens: int = DEFAULT_AI_MAX_TOKENS
    problems: list = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    def summary(self) -> str:
        """给用户看的中文配置提示。"""
        if self.is_ready:
            return f"AI 已配置（模型 {self.model}）"
        missing = []
        if not self.api_key:
            missing.append("OPENAI_API_KEY")
        if not self.base_url:
            missing.append("OPENAI_API_BASE")
        return "未配置 AI：请在 .env 中填写 " + " 和 ".join(missing)


def load_config() -> AppConfig:
    """读取 .env 与环境变量；缺配置不抛异常，返回 is_ready=False。"""
    try:
        if ENV_FILE.exists():
            from dotenv import load_dotenv

            load_dotenv(ENV_FILE)
    except Exception as e:  # .env 损坏不应影响程序启动
        logger.warning(f"读取 .env 失败，已忽略：{e}")
    return AppConfig(
        api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        base_url=os.getenv("OPENAI_API_BASE", "").strip(),
        model=os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
        timeout=_to_int(os.getenv("AI_TIMEOUT"), DEFAULT_AI_TIMEOUT),
        max_tokens=_to_int(os.getenv("AI_MAX_TOKENS"), DEFAULT_AI_MAX_TOKENS),
    )


# ===================================================================
# 日志
# ===================================================================
def setup_logging(level=logging.INFO) -> None:
    """初始化滚动日志（app.log，1MB × 2 个备份）；重复调用无副作用。"""
    root = logging.getLogger()
    if getattr(root, "_photomagic_configured", False):
        return
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:  # 日志文件不可写时仅输出到控制台
        pass
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    root._photomagic_configured = True


# ===================================================================
# 用户设置（settings.json）
# ===================================================================
DEFAULT_SETTINGS = {
    "layout": "电影竖排",
    "strip_style": "保留间隙",
    "text_style": "经典底部",
    "filter": "无",
    "font": "默认",
    "content_style": "简体短句",
    "scale": "高清 2×",
    "ai_enabled": True,
    "last_save_dir": "",
}


def load_settings() -> dict:
    """读取 settings.json；缺失或损坏时返回默认值副本，绝不抛异常。"""
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"settings.json 读取失败，使用默认设置：{e}")
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    """保存设置；失败只记日志不影响主流程。"""
    try:
        SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        logger.warning(f"保存设置失败：{e}")
