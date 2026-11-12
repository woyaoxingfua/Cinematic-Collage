# conftest.py —— 让 tests/ 能直接 import 项目根目录下的模块
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
