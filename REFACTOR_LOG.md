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

---

## 阶段 2：图像管线（核心）—— 完成

- [x] `imaging.py` 新建：`load_image()`（EXIF 转正 / RGBA/P 带透明铺白底 / CMYK 等统一 RGB / 长边 >3000 先缩小）；`resize_to_width`（只缩不放）、`resize_exact_width`（统一宽度）、`crop_to_fill`、`crop_to_aspect`
- [x] `filters.py` 新建：.cube 解析 + numpy 三线性插值；按路径缓存只读一次；缺失/损坏抛 `FilterError`（中文）由上层提示并跳过；分带处理限制内存峰值
- [x] `layouts.py` 按新接口重写：`Slot` / `RenderResult` / `Layout` 基类 + `LAYOUTS` 注册表
  - 电影竖排：2–6 张，「保留间隙 / 无缝拼接」，齿孔边条随 scale 缩放
  - 单张海报：先排文字再定画布高度，底部留白 = max(180×s, 文字高 + 2×40×s)，文字在留白内垂直+水平居中
  - 所有尺寸 = 基准值 × scale；预设 1×/2×/3×（电影竖排 2× 总宽 1440px，海报 2× 约 1800px）
- [x] `textdraw.py` 新建：字体解析链（系统中文 → 仓库手写体.ttf → load_default，修掉 truetype(None) 崩溃）；中英混合换行（中文按字、英文按词、避头标点、`font.getlength` 测宽）；`fit_text` 逐步缩字号 + 省略号截断；`draw_lines` 绘制
- [x] `app_ui.py` 最小适配（阶段 4 才整体重写）：生成流程改走 imaging/filters/layouts/textdraw；电影竖排接受 2–6 张；文件类型加 webp/bmp；AI 旧接口的报错字符串提前过滤，绝不上图；工作线程 UI 更新全部经 `self.after` 投递
- [x] `tools/make_samples.py`：9 张样图输出到 `samples/`
- [x] 测试 31 个新增（imaging 9 / textdraw 10 / filters 9 / layouts 12 + 对拍 2）

### 重要发现与修复（colour 对拍）
- ColdChrome.cube 的表含**超界值**（负值 / >1）。colour 保留原值参与插值、仅输出时截断；我最初在解析时 clip 表导致内插偏差最大 7 个色阶。修正为「表不 clip、输出才 clip」后，三个仓库 LUT + identity 对拍全部达标（平均 <1、最大 <3 个色阶）→ **numpy 实现保留，colour-science 可在阶段 5 从必装依赖移除**（对拍测试保留，colour 缺失时自动跳过）
- fit_text 截断分支曾漏加省略号（丢弃内容时最后一行必须补 …），已修

### 验收结果
- `pytest`：44 passed（含对拍）
- `python main.py --smoke-test` 退出码 0
- `tools/make_samples.py` 生成 9 张样图；visual-judge 视觉验收 4/4 通过（齿孔对称、配文不越界不压间隙、海报文字居中留白充足、滤镜观感正常）

### 样图路径（供早上目检）
`samples/`：film_strip_gap_{1x,2x,3x}.png、film_strip_seamless_2x.png、film_strip_5photos_2x.png、film_strip_filtered_BlueArchitecture_2x.png、poster_{long_text,english,no_text}_2x.png

---

## 阶段 3：AI 层 —— 完成

- [x] 客户端延迟创建（`get_client()` 首次调用才读配置），带 `timeout`（默认 60）与 `max_retries=2`；`set_client()/reset_client()` 支持测试注入
- [x] 一次请求发 N 张缩小图（长边 ≤1024、JPEG q85），不再发整张拼好的成图；服务商报 BadRequest（不支持多图）时自动降级为逐张请求
- [x] 提示词 JSON 示例按 N 动态生成；「恰好 N 条、每条 ≤20 汉字（英文 ≤15 词）」；风格预设字典 `STYLE_PROMPTS`；支持 `extra_prompt` 追加自定义风格要求（阶段 6 的输入框会用到）
- [x] `parse_texts(raw, n)`：去 ```json 围栏 → 提取第一个配平 `{...}`/`[...]`（括号在字符串内时忽略）→ 支持 `{"texts":[...]}` 与纯数组 → 非字符串转 str（None→空串）→ 不足补空串、过多截断 → 完全失败按换行拆分兜底
- [x] 错误绝不当文案：失败抛 `AiError`（中文），按异常类型映射（Key 无效 / 模型不存在需视觉模型 / 限流 / 超时 / 连接失败 / HTTP 状态码 / 通用）
- [x] `app_ui.py` 适配层同步切换到新接口（AiError → 状态栏橙色提示 + 留空，不上图）
- [x] 新增 20 个 mock 测试（不碰真实 API、不读 .env）

### 验收结果
- `pytest`：64 passed（新增围栏 JSON / 前后废话 / 纯数组 / 空回复 / 条数不符 / 非字符串元素 / 括号不配平兜底 / 多图→单图降级 / 各类异常映射 / 请求图片数 = N / 缺 .env import 安全）
- `python main.py --smoke-test` 退出码 0

### 保守决策记录
- **空回复 / 全空白回复 → 抛 AiError**（方案原文只说"完全解析失败按换行拆分"，但空内容拆行只会得到全空串，用户会拿到无字成品却毫无提示；选择显式失败更符合"错误绝不当文案"的原则）
- JSON 对象里没有 `texts` 键（如 `{"result": ...}`）→ 不强行取值，按换行拆分兜底
- 降级为逐张请求时，单张也失败则整体抛 AiError（不静默丢某张的文案）

---

## 阶段 4：界面与交互 —— 完成

- [x] `pipeline.py` 新建：Tk 无关的生成流程 `build(paths, options, ai_client, texts, image_cache)`；滤镜失败→警告跳过；AI 失败→留空+警告（不阻断出图，可手动补写后重渲染）
- [x] `app_ui.py` 整体重写（约 480 行）：
  - **线程安全**：工作线程只跑 pipeline，结果经 `queue.Queue` + 主线程 `after(100)` 轮询；文件对话框直接在按钮回调里弹（删掉了旧的两层线程套娃和重复的 `on_resize`）
  - **预览画布**：`<Configure>` 绑定画布本身 + 150ms 防抖，且只在「适应窗口」态自动重排；双击=适应窗口；以鼠标为中心缩放（0.05–8）；兼容 Linux `<Button-4/5>`；拖动用 `canvas.move` 不重采样；缩放先 BILINEAR、停手 120ms 后 LANCZOS 补渲；显示尺寸小于原图一半时用半分辨率副本快渲（3× 大图不卡）
  - **控件联动**：「竖排样式」仅电影竖排显示（grid_remove 位置记忆）；数量提示随布局变化（「请选择 2–6 张照片」）；文件类型加 webp/bmp，装了 pillow-heif 时自动支持 heic（try-import，不进 requirements）
  - **文字可编辑、可重渲染**：生成后左侧出现 N 个输入框显示 AI 文案可手改；「重新渲染」用当前文字/滤镜/字体/布局/清晰度出图且**不调 AI**；「重新生成文字」才调 AI；照片读取与文案均缓存（换设置只重算必要部分）
  - **AI 配文开关**：关闭（或未配置 .env，开关自动禁用并提示）时纯手动写字，应用照样可用
  - **反馈与保存**：不定长进度条 + 忙时禁用按钮；错误一句人话（细节进 app.log）；保存记住上次目录、JPEG quality=95；settings.json 记住布局/滤镜/字体/文字风格/清晰度/AI 开关；窗口标题 V3.0；关闭时自动保存设置
- [x] 测试：pipeline 10 个（核心：首次调 AI 1 次、改字体/滤镜重渲染后仍 1 次）
- [x] `tools/ui_selftest.py`：程序化 UI 自检（不弹对话框、不调真实 AI），15 项全过

### 验收结果
- `pytest`：74 passed
- `python main.py --smoke-test` 退出码 0
- `tools/ui_selftest.py` 15/15 通过（生成→改字→免 AI 重渲染→布局联动→缩放/适应切换）

### 保守决策记录
- AI 失败时选择「出图 + 空文案 + 警告」而不是整体失败：用户仍能拿到拼图并可手动补字（输入框就在手边），「重新生成文字」可重试
- 布局切换后旧结果保留：换布局再点「重新渲染」可复用照片与文案；若数量不匹配会得到明确报错（如 3 张选单张海报）
- settings 里 `ai_enabled` 在未配置 .env 时强制存 True，避免配置好 .env 后用户误以为开关坏了
