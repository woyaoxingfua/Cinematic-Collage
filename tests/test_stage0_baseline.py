# tests/test_stage0_baseline.py —— 阶段 0 基线：所有根目录模块可编译
import py_compile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_all_root_modules_compile():
    files = sorted(PROJECT_ROOT.glob("*.py"))
    assert files, "未找到任何根目录 .py 文件"
    for f in files:
        py_compile.compile(str(f), doraise=True)
