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

---

## 阶段 1：地基 —— 完成

- [x] `config.py` 新建：`APP_DIR` 基路径（FONTS_DIR / LUTS_DIR / SAMPLES_DIR / ENV_FILE / LOG_FILE / SETTINGS_FILE 全部由它派生）；`load_config()` 缺 .env 不抛异常，返回 `is_ready` + 中文提示；新增可选键 `OPENAI_MODEL`（默认 stepfun-ai/step3）、`AI_TIMEOUT`（默认 60）、`AI_MAX_TOKENS`（默认 800）；`setup_logging()` 滚动日志（app.log 1MB×2）；`load_settings()/save_settings()` 容错读写 settings.json
- [x] 全部 `print` 替换为 `logging`（ai_connector.py、layouts.py；app_ui.py 本无 print）
- [x] `main.py` 重写：删除前 190 行注释旧码，新增 `--smoke-test`（建窗 1 秒后自动销毁，退出码 0）
- [x] `ai_connector.py` import 安全化：配置读取与客户端创建全部延迟到 `_get_client()`，缺 .env 不再在 import 时崩溃（本阶段保持旧接口 `get_ai_text`，阶段 3 重写）
- [x] `app_ui.py` / `layouts.py` 的字体、滤镜目录改为 `config.FONTS_DIR` / `config.LUTS_DIR`，不再依赖 CWD

### 验收结果
- 临时移走 `.env`（仅改名未读取，测后已还原）→ `timeout 30 python main.py --smoke-test` 退出码 **0**
- `cd /tmp && python <项目>/main.py --smoke-test` 退出码 **0**（证明不依赖工作目录）
- `pytest`：1 passed

### 保守决策记录
- 日志文件不可写时 `setup_logging` 仅输出控制台（不因日志失败拖垮启动）
- `app_ui.py` 里重复定义的 `on_resize` 留待阶段 4 整体重写时删除（本阶段不做无关格式化/顺手改）
