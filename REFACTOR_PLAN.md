# 改造方案：Cinematic-Collage → 可用的 v3

> 本文件是本次无人值守重构的执行蓝图，由用户于 2026-11-13 提供。
> 执行日志见 [REFACTOR_LOG.md](REFACTOR_LOG.md)。

## 一、目标

从"能跑的 demo"变成"每次都能出片的工具"：

- 不再因配置、字体、路径崩溃
- 成品够清晰（原来只有约 720px 宽）
- AI 出错时，不把报错文字画到照片上
- AI 文字可手改；换滤镜、字体、布局时不重复调用 AI（省 token）

## 二、执行规则

1. 新建分支 `refactor/usable-v3`，每阶段单独提交；不 push main，不强推。
2. 绝不在前台运行 `python main.py`。GUI 验证只用 `python main.py --smoke-test`（建窗口、1 秒后自动销毁、退出码 0），并加 `timeout 30`。
3. 不用真实 API Key 调用，不读取、不提交 `.env`；AI 相关测试一律 mock。
4. 每阶段完成标准：pytest 全绿 + smoke test 通过 + 在 REFACTOR_LOG.md 追加记录。同一问题连续失败 2 次 → 回退该阶段改动，记录原因，转去不依赖它的阶段。
5. 拿不准就选保守方案并写进日志，不要停下来等人。
6. 不改 `luts/`、`fonts/` 里的文件；不做无关格式化；新增注释用中文；除 pytest 外不新增必装依赖。
7. 保持不变：`.env` 现有键名、字体/滤镜按文件夹自动识别、界面中文文案风格。

## 三、目标结构

```
main.py          入口（仅启动 UI，支持 --smoke-test）
app_ui.py        界面与调度（不含图像逻辑）
config.py   新   路径、.env、设置（延迟读取，import 时不报错）
imaging.py  新   读图（EXIF 转正、统一 RGB）
filters.py  新   LUT 加载缓存 + 应用
layouts.py       布局渲染（返回成图 + 每张照片的位置）
textdraw.py 新   字体解析、换行、自适应字号、绘制
pipeline.py 新   生成流程（不依赖 Tk，UI 和测试共用）
ai_connector.py  AI 调用与解析
tests/
tools/make_samples.py
```

核心接口：

```python
@dataclass
class Slot: x: int; y: int; w: int; h: int      # 一张照片在成图中的位置
@dataclass
class RenderResult: image: Image.Image; slots: list[Slot]

class Layout:            # 注册表 LAYOUTS: dict[str, Layout]
    name: str; min_photos: int; max_photos: int
    def photo_width(self, scale) -> int
    def render(self, photos, texts, font, scale, **opts) -> RenderResult
```

所有尺寸都是"基准值 × scale"，文字用 slots 定位，不再在两个文件里手抄同一组魔法数字。

## 四、分阶段

### 阶段 0：准备
建分支，确认 Python 版本和依赖能装，跑 py_compile 做基线。创建 REFACTOR_LOG.md；.gitignore 增加 app.log、settings.json、samples/。建 tests/ 和 requirements-dev.txt（pytest）。

### 阶段 1：地基
- config.py：APP_DIR 基路径，FONTS_DIR、LUTS_DIR 全基于它，不依赖 CWD。load_config() 返回带 is_ready 和中文提示的对象，缺 .env 不抛异常。新增可选键 OPENAI_MODEL（默认 stepfun-ai/step3）、AI_TIMEOUT（默认 60）、AI_MAX_TOKENS（默认 800）。
- 用 logging 替换所有 print，写入滚动的 app.log，绝不记录 API Key。
- main.py 删掉前 190 行注释掉的旧代码，加 --smoke-test。
- 验收：删掉 .env 后 smoke test 仍通过；cd /tmp && python <项目路径>/main.py --smoke-test 通过。

### 阶段 2：图像管线（核心）
1. imaging.py：load_image(path) 做 EXIF 转正；RGBA/P/CMYK 转 RGB，透明处铺白底；长边超过 3000 先缩小。
2. filters.py：LUT 按路径缓存只读一次；先缩放到目标尺寸再套滤镜；LUT 缺失或损坏抛明确异常，由 UI 提示并跳过。
3. layouts.py 按新接口重写：
   - 电影竖排：支持 2–6 张；保留"保留间隙 / 无缝拼接"；齿孔和边条随 scale 缩放。
   - 单张海报：先排好文字再定画布高度，底部留白 = max(最小值, 文字高度 + 上下边距)，文字在留白里垂直居中。
   - 默认 scale=2（电影竖排约 1440px 宽，海报约 1800px 宽）；预设"标准 1× / 高清 2× / 超清 3×"。
4. textdraw.py：字体解析（系统中文字体 → 仓库手写体.ttf → load_default）；换行（中文按字、英文按词、避头标点、font.getlength）；fit_text 自适应字号与截断。
5. 验收（headless pytest，图片全用代码合成）：布局 × N × scale 尺寸公式与 slots 检查；identity LUT 误差 ≤1；缓存命中；EXIF 转正；RGBA 铺白底；换行规则；fit_text 不越界。写 tools/make_samples.py 输出 samples/ 供目检。

### 阶段 3：AI 层
- 客户端延迟创建，带 timeout、max_retries=2；import 时不再读 key、不再抛异常。
- 一次请求发 N 张缩小图（长边 ≤1024，JPEG quality 85）；BadRequest 时降级为逐张请求。
- 提示词 JSON 示例按 N 动态生成；"恰好 N 条，每条不超过 20 个汉字（英文不超过 15 词）"。
- parse_texts(raw, n)：去围栏、提取 {...}/[...]、支持 {"texts":[...]} 与纯数组、非字符串转 str、不足补空串、过多截断、失败按换行拆分。
- 错误绝不当文案：失败抛 AiError(message)，按异常类型给中文提示。
- 验收（mock）：围栏 JSON / 前后带废话 / 纯数组 / 空回复 / 条数不符 / 抛异常；请求图片数 = N；缺 .env 时 import 不报错。

### 阶段 4：界面与交互
1. 线程安全：工作线程只算图；queue.Queue + after(100, poll)；文件对话框在按钮回调里弹。
2. 预览画布：Configure 防抖 150ms 且仅"适应窗口"态生效；双击适应；鼠标为中心缩放（0.05–8）；Linux Button-4/5；拖动 canvas.move；缩放 BILINEAR、停手 120ms 后 LANCZOS。
3. 控件联动：竖排样式仅电影竖排显示；照片数量提示随布局；文件类型加 webp/bmp，可选 heic（try-import pillow-heif）。
4. 文字可编辑、可重渲染：N 个输入框；「重新渲染」不调 AI；「重新生成文字」才调 AI；缓存照片与文字；AI 配文开关（未配置 .env 时纯手动可用）。
5. 反馈与保存：不定长进度条；错误一句人话 + 细节进日志；记住上次保存目录，JPEG quality=95；settings.json 记住设置；标题 V3.0。
6. 验收：smoke test；pipeline.build(paths, options, ai_client, texts=None) 的 pytest（mock AI 调用次数）。

### 阶段 5：收尾
- README 重写（真实安装步骤、新功能、正确结构、验证过的 Python 版本）。
- .env.example 补可选键并注明"模型必须是视觉模型"；requirements.txt 写最低版本。
- （可选，门槛严格）去掉 colour-science：numpy 三线性插值，先写对拍测试（平均 <1 色阶、最大 <3），达不到就保留 colour 并写明日志。
- （可选）build_exe.md + PyInstaller 命令，标注"未验证"。

### 阶段 6：可选加分项（全绿才做，每项单独提交）
四宫格布局 / 电影字幕文字样式 / 自定义风格提示输入框 / 电影竖排统一画幅（3:2、4:3、1:1）。

## 五、早上的汇报（写进 REFACTOR_LOG.md）
1. 每个阶段：完成 / 跳过 / 回退，及原因
2. 需要手动做的 3 件事
3. 需要拍板的问题清单
4. samples/ 里各布局样图的路径
