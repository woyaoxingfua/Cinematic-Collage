# REFACTOR_LOG —— 无人值守改造日志

- 分支：`refactor/usable-v3`（自 `fa2db76` 切出）
- 方案：见 [REFACTOR_PLAN.md](REFACTOR_PLAN.md)
- 环境实测：Windows 10 (22631) x64 / Git Bash / Python 3.12.5（项目 .venv）
  已装：customtkinter 5.2.2、Pillow 11.3.0、openai 1.99.3、python-dotenv 1.1.1、colour-science 0.4.6、numpy 2.3.2；本阶段加装 pytest 9.2.0

---

## ⏸ 中断点快照（2026-11-13，因额度切换模型暂停）

> ✅ 本快照所列工作已全部完成（见下方阶段 5 / 6 与晨报），仅作历史记录保留。

**给续跑的 agent：读完本节即可继续，无需翻聊天记录。**

- 阶段 0–4 已完成并分别提交（最新 `7ffd864`），工作区干净。验收状态：pytest 74 passed、smoke 0、UI 自检 15/15
- **剩余工作：**
  1. 阶段 5（收尾）：重写 Readme.md（真实安装步骤：luts/fonts 已在仓库不用手动建、新功能、正确结构、实测 Python 3.12.5）；`.env.example` 补可选键 OPENAI_MODEL / AI_TIMEOUT / AI_MAX_TOKENS 并注明"模型必须是支持图片的视觉模型"；requirements.txt 写最低版本（customtkinter>=5.2、Pillow>=10.0、openai>=1.0、python-dotenv>=1.0、numpy>=1.24）并**移除 colour-science**（阶段 2 对拍已达标，filters.py 已是纯 numpy，tests/test_filters_parity.py 有 importorskip 会自动跳过）；写 build_exe.md（PyInstaller：`--collect-all customtkinter --add-data "fonts;fonts" --add-data "luts;luts"`，标注"未验证"，注明 onefile 模式下 settings.json/app.log 会写进临时目录的坑）；完成后 pytest + smoke + 本日志追加记录 + 单独提交
  2. 阶段 6（可选加分项，全绿才做，**每项单独提交**）：四宫格布局（Layout 注册表新增，imaging.crop_to_fill 已备好）；「电影字幕」文字样式（居中白字黑描边+底部渐变遮罩，layouts.render 的 **opts 传 text_style）；自定义风格提示输入框（BuildOptions.extra_prompt 字段和 ai_connector.get_ai_texts 的 extra_prompt 参数已就绪，只差 UI 一个 CTkEntry）；电影竖排统一画幅（imaging.crop_to_aspect 已备好）
  3. 最终晨报（写进本文件末尾）：每阶段完成/跳过/回退状态、需用户手动做的 3 件事（真实 Key 跑一次 3 张图、目检 samples/、确认 手写体.ttf 授权）、需拍板的问题、samples/ 路径清单
- .env.example 当前内容只有 OPENAI_API_KEY / OPENAI_API_BASE 两行（刚读过，未改动）
- 执行规则提醒：不读不提交 .env；GUI 只用 `timeout 30 .venv/Scripts/python.exe main.py --smoke-test` 验证；测试全 mock；新增注释用中文；不改 luts/、fonts/

---

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

---

## 阶段 5：收尾 —— 完成

- [x] `Readme.md` 重写：真实安装步骤（luts/fonts 已在仓库，不用手动建）、V3 新功能清单、**正确的项目结构**（此前列的是不存在的 `PhotoMagic/` 嵌套目录）、实测 Python 3.12、开发与测试一节（pytest / --smoke-test / make_samples / ui_selftest）
- [x] `.env.example` 补可选键 `OPENAI_MODEL` / `AI_TIMEOUT` / `AI_MAX_TOKENS`，注明「模型必须是支持图片输入的视觉模型」
- [x] `requirements.txt` 写最低版本，**移除 colour-science**（阶段 2 对拍已达标，filters.py 已纯 numpy）；对拍测试保留 `importorskip`，装了 colour 的环境仍可跑
- [x] `build_exe.md` 新建：PyInstaller onedir 命令（`--collect-all customtkinter` + fonts/luts add-data），标注**未验证**；说明为何不推荐 onefile（临时目录导致 settings.json/app.log 丢失）；分发前字体授权提醒

### 验收结果
- `pytest`：74 passed
- `python main.py --smoke-test` 退出码 0
- 移除 colour 后 `import filters` 正常工作

---

## 阶段 6：可选加分项 —— 完成（4/4，各单独提交）

- [x] 6-1 「四宫格」布局（`996f2e4`）：2×2、照片居中裁切铺满 600×450 格子、配文复用公共函数；验证了注册表扩展性——UI 菜单零改动自动出现
- [x] 6-2 「电影字幕」文字样式（`6c984f7`）：底部渐变遮罩 + 居中白字黑描边；电影竖排/四宫格可用；UI 选项 + settings 记忆
- [x] 6-3 「自定义风格提示」输入框（`67cc7ad`）：经 `BuildOptions.extra_prompt` 追加到 AI 提示词
- [x] 6-4 电影竖排「统一画幅」（`3fe4c50`）：原始 / 3:2 / 4:3 / 1:1，居中裁切不变形；海报/四宫格静默忽略该参数

### 视觉验收（visual-judge，像素级实测）
- 首轮 3 张新样图：四宫格 ✓、3:2 画幅 ✓、电影字幕 ✗（遮罩底部 alpha=170 只压暗到 67%，照片色透出形成接缝）
- 修复：渐变底部改为 255（纯黑）→ 复审通过（底缘中位 RGB [0,0,0]，无接缝、文字无回归）
- 最终视觉验收 **3/3 通过**；此前阶段 2 的 4 张基础样图亦 4/4 通过

---
---

# 🌅 晨报（2026-11-13）

## 1. 各阶段状态

| 阶段 | 状态 | 提交 |
|---|---|---|
| 0 准备（分支/脚手架/基线） | ✅ 完成 | `5acec12` |
| 1 地基（config/日志/smoke-test） | ✅ 完成 | `13e4a5b` |
| 2 图像管线（imaging/filters/layouts/textdraw） | ✅ 完成 | `c6cef63` |
| 3 AI 层（多图请求/解析器/AiError） | ✅ 完成 | `1832700` |
| 4 界面与交互（线程安全/可编辑文字/免AI重渲染） | ✅ 完成 | `7ffd864` |
| 中断点快照（模型切换） | ✅ 已全部兑现 | `1a06c70` |
| 5 收尾（README/.env.example/依赖/build_exe.md） | ✅ 完成 | `3616a0c` |
| 6-1 四宫格 | ✅ 完成 | `996f2e4` |
| 6-2 电影字幕样式 | ✅ 完成（含一轮视觉返修） | `6c984f7` + 渐变修复 |
| 6-3 自定义风格提示 | ✅ 完成 | `67cc7ad` |
| 6-4 统一画幅 | ✅ 完成 | `3fe4c50` |

**无回退**。过程中两次失败均在 1 次修复内解决（fit_text 截断漏省略号；LUT 表超界值的解析策略）。
最终：**pytest 91 passed** · smoke test 0 · UI 自检 19/19 · 视觉验收 7/7（4 基础 + 3 新增）。

## 2. 需要您手动做的 3 件事

1. **用真实 Key 跑一次**：`.env` 填好后启动程序，选 3 张照片走完整流程（重点验证您的服务商对「一次请求多张图」的支持——不支持会自动降级，状态栏会有橙色提示）；再试一次「改字体→重新渲染」，确认 AI 调用次数为 0（不重复花钱）。
2. **目检 `samples/` 里的 12 张样图**：布局观感、字号、间距是否符合您的审美，随时可调各布局的基准参数。
3. **确认 `fonts/手写体.ttf` 的授权**：如果打算打包 exe 或公开分发，需确认该字体允许再分发（build_exe.md 里也有提醒）。

## 3. 需要您拍板的问题清单

1. **未跟踪的垃圾目录**：`Users/Lenovo/.../layouts.py` 与 `PhotoMagic/PhotoMagic/`（历史误写路径的产物，已被 .gitignore 忽略）——确认无用后可手动删除。
2. **colour-science 已从必装依赖移除**（numpy 实现对拍达标）。对拍测试保留（装了 colour 的环境会自动跑）；若希望彻底删除对拍测试文件，请示下。
3. **AI 失败时的策略**：当前是「出图 + 空文案 + 警告，可手动补写后重渲染」；备选是「整体失败不出图」。如需更严格的策略请告知。
4. **默认清晰度为高清 2×**（胶卷 1440px / 海报 1800px 宽）；如想默认 3× 或 1×，改 `config.DEFAULT_SETTINGS` 一行即可。
5. **打包**：build_exe.md 已写好但**未验证**（本环境无法装 PyInstaller 实测），需要您抽空跑一次；onefile 模式有 settings 丢失的坑，文档建议 onedir。

## 4. 样图路径（samples/，共 12 张）

| 样图 | 内容 |
|---|---|
| `film_strip_gap_{1x,2x,3x}.png` | 电影竖排·保留间隙，三档清晰度 |
| `film_strip_seamless_2x.png` | 电影竖排·无缝拼接 |
| `film_strip_5photos_2x.png` | 电影竖排·5 张照片 |
| `film_strip_subtitle_2x.png` | 电影字幕样式（渐变遮罩+居中白字） |
| `film_strip_aspect32_2x.png` | 统一画幅 3:2 |
| `film_strip_filtered_BlueArchitecture_2x.png` | 真实 LUT 滤镜 |
| `grid4_2x.png` | 四宫格 |
| `poster_{long_text,english,no_text}_2x.png` | 单张海报（长文案/英文/无字） |

## 5. 其他说明

- 分支 `refactor/usable-v3`，未 push（按规则不 push main）；合并到 main 由您决定。
- `.env` 全程未读取、未提交；所有 AI 测试均为 mock。
- 新增依赖仅 dev 侧 pytest；运行依赖反而减少了 colour-science。
- 手写体.ttf 授权、垃圾目录清理等细节见上。

---

## 发布准备（2026-11-13 上午，用户准备 push）

- 删除垃圾目录 `Users/`、`PhotoMagic/`（均为 2025-08-09 开发残留的十几行残片）与各处 `__pycache__`/`.pytest_cache`
- README：去掉指向不存在文件的英文版死链（原版即坏）；结构一节补 REFACTOR_PLAN.md
- **UX 修复**：默认窗口 1280x860→**1280x980**；左侧面板在 125%/150% DPI 屏幕上内容高于可视区，会把操作按钮挤出折叠区——已把「重新渲染/重新生成/保存」提到配文输入框之前，状态栏+进度条固定到窗口底部（不随面板滚动），并收紧分区标签间距
- `img.png` 更新为 V3 界面截图（tools/capture_screenshot.py 自动生成，作为占位；用户将自己截图替换）
- 验收：pytest 91 passed · smoke 0 · UI 自检全过
