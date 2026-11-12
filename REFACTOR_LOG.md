# REFACTOR_LOG —— 无人值守改造日志

- 分支：`refactor/usable-v3`（自 `fa2db76` 切出）
- 方案：见 [REFACTOR_PLAN.md](REFACTOR_PLAN.md)
- 环境实测：Windows 10 (22631) x64 / Git Bash / Python 3.12.5（项目 .venv）
  已装：customtkinter 5.2.2、Pillow 11.3.0、openai 1.99.3、python-dotenv 1.1.1、colour-science 0.4.6、numpy 2.3.2；本阶段加装 pytest 9.2.0

---

## 阶段 0：准备 —— 完成

- [x] 建分支 `refactor/usable-v3`
- [x] 基线 `py_compile main.py app_ui.py layouts.py ai_connector.py` 全部通过
- [x] 创建 `REFACTOR_LOG.md`、`REFACTOR_PLAN.md`（方案原文整理）
- [x] `.gitignore` 追加：`app.log`、`app.log.*`、`settings.json`、`samples/`、`.pytest_cache/`
- [x] 建 `tests/`（含基线编译测试）、`conftest.py`、`pytest.ini`、`requirements-dev.txt`

### 侦察发现（不需要动作，仅记录）
- 根目录存在未跟踪的垃圾目录 `Users/Lenovo/.../layouts.py` 与 `PhotoMagic/PhotoMagic/{app_ui,layouts}.py`（历史上路径误写产生的副本）。已被现有 `.gitignore` 忽略，未删除（保守：不碰用户文件），建议用户自行确认后删除。
- `fonts/手写体.ttf` 来源不明，公开分发前需确认授权（已列入晨报"需要拍板"）。
- 仓库内未发现泄露密钥，`.env` 已在 `.gitignore` 中。

### 验收
- `pytest`：1 passed（基线编译）
