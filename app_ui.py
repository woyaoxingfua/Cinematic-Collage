# file: app_ui.py（阶段 4 重写）
"""界面与调度：只负责收集选项、展示结果；图像逻辑全部在 pipeline 及其依赖里。

线程模型：工作线程只做纯计算（pipeline.build），结果经 queue.Queue 由主线程
after(100) 轮询取回——工作线程绝不直接触碰任何控件。
"""
from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, StringVar
from PIL import Image, ImageTk

import ai_connector
import config
import filters
import layouts
import pipeline
from layouts import TEXT_STYLES, TEXT_STYLE_CLASSIC

logger = logging.getLogger(__name__)

SCALE_OPTIONS = {"标准 1×": 1.0, "高清 2×": 2.0, "超清 3×": 3.0}
CONTENT_STYLES = ["简体短句", "繁体诗歌", "英文散文"]
STRIP_STYLES = ("保留间隙", "无缝拼接")


# ===================================================================
# 预览画布
# ===================================================================
class ImageCanvas(ctk.CTkFrame):
    """可缩放 / 拖拽的预览画布。

    - 双击 = 适应窗口；拖动 / 缩放后进入自由模式，窗口 resize 不再重置视图
    - 以鼠标位置为中心缩放，范围 0.05–8；兼容 Linux 的 <Button-4/5>
    - 拖动用 canvas.move（不重新采样）；缩放先 BILINEAR，停手 120ms 后 LANCZOS 补一次
    """

    ZOOM_MIN = 0.05
    ZOOM_MAX = 8.0
    FIT_MARGIN = 40

    def __init__(self, master):
        super().__init__(master)
        self.canvas = ctk.CTkCanvas(self, background="#2B2B2B", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.original_image = None  # 原始成图（Pillow）
        self._half_image = None     # 半分辨率副本（显示尺寸很小时加速重采样）
        self._tk_image = None
        self._image_item = None
        self.scale = 1.0
        self.image_x = 0.0
        self.image_y = 0.0
        self.fit_mode = True        # 「适应窗口」状态：只有此状态下 resize 才自动重排
        self._resize_job = None     # resize 防抖
        self._hq_job = None         # 高质量重绘延时
        self._drag_x = 0
        self._drag_y = 0

        # 事件绑定（绑定在画布本身，而不是整个窗口）
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<MouseWheel>", self._on_wheel)  # Windows / macOS
        self.canvas.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.1))     # Linux 放大
        self.canvas.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.1))  # Linux 缩小
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Double-Button-1>", lambda e: self.fit_to_window())

    # --- 对外接口 ---
    def show_image(self, pillow_image):
        """载入新图片并适应窗口。"""
        self.original_image = pillow_image
        self._half_image = None
        self.fit_to_window()

    def fit_to_window(self):
        """适应窗口（双击 / 新图载入 / 窗口变化且处于适应状态时调用）。"""
        if self.original_image is None:
            return
        self.canvas.update_idletasks()
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        iw, ih = self.original_image.size
        self.scale = min((cw - self.FIT_MARGIN) / iw, (ch - self.FIT_MARGIN) / ih)
        self.scale = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.scale))
        self.image_x = (cw - iw * self.scale) / 2
        self.image_y = (ch - ih * self.scale) / 2
        self.fit_mode = True
        self._render(Image.Resampling.LANCZOS, allow_half=False)

    # --- 事件处理 ---
    def _on_configure(self, event):
        # 防抖 150ms：只在停止变化后才重排，避免拖动窗口时反复重置
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(150, self._on_configure_debounced)

    def _on_configure_debounced(self):
        self._resize_job = None
        if self.fit_mode and self.original_image is not None:
            self.fit_to_window()

    def _on_wheel(self, event):
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._zoom_at(event.x, event.y, factor)

    def _zoom_at(self, cx, cy, factor):
        if self.original_image is None:
            return
        new_scale = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-9:
            return
        # 以鼠标位置 (cx, cy) 为不动点缩放
        k = new_scale / self.scale
        self.image_x = cx - (cx - self.image_x) * k
        self.image_y = cy - (cy - self.image_y) * k
        self.scale = new_scale
        self.fit_mode = False
        self._render(Image.Resampling.BILINEAR)
        # 停手 120ms 后用 LANCZOS 补一次高质量渲染
        if self._hq_job is not None:
            self.after_cancel(self._hq_job)
        self._hq_job = self.after(120, self._render_hq)

    def _render_hq(self):
        self._hq_job = None
        if self.original_image is not None:
            self._render(Image.Resampling.LANCZOS, allow_half=False)

    def _on_press(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        if self._image_item is None:
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self._drag_x = event.x
        self._drag_y = event.y
        self.image_x += dx
        self.image_y += dy
        self.fit_mode = False
        self.canvas.move(self._image_item, dx, dy)  # 移动图元，不重新采样

    # --- 渲染 ---
    def _render(self, resampling, allow_half=True):
        """按当前 scale / 位置重绘画布。BILINEAR 快渲可用半分辨率副本，LANCZOS 用原图。"""
        if self.original_image is None:
            return
        disp_w = max(1, round(self.original_image.width * self.scale))
        disp_h = max(1, round(self.original_image.height * self.scale))
        src = self.original_image
        if allow_half and disp_w * 2 < self.original_image.width:
            if self._half_image is None:
                half = self.original_image.copy()
                half.thumbnail(
                    (max(1, self.original_image.width // 2), max(1, self.original_image.height // 2)),
                    Image.Resampling.BILINEAR,
                )
                self._half_image = half
            src = self._half_image
        w = max(1, round(src.width * disp_w / self.original_image.width))
        h = max(1, round(src.height * disp_h / self.original_image.height))
        img = src.resize((w, h), resampling)
        self._tk_image = ImageTk.PhotoImage(img)
        if self._image_item is None:
            self._image_item = self.canvas.create_image(
                self.image_x, self.image_y, anchor="nw", image=self._tk_image)
        else:
            self.canvas.itemconfig(self._image_item, image=self._tk_image)
            self.canvas.coords(self._image_item, self.image_x, self.image_y)
        self.canvas.tag_raise(self._image_item)


# ===================================================================
# 主应用
# ===================================================================
class PhotoBoothApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("电影感照片生成器 V3.0")
        self.geometry("1280x860")
        self.minsize(980, 640)

        self.settings = config.load_settings()
        self._ai_ready = config.load_config().is_ready

        # 生成状态
        self._queue = queue.Queue()
        self._photo_cache = {}   # path -> Image：已读照片（换设置不重读）
        self._paths = []         # 当前照片路径列表
        self._texts = None       # 当前文案（None = 尚未生成过）
        self._result = None      # 最近一次 pipeline.BuildResult
        self._busy = False
        self._text_vars = []

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_controls()

        self.image_canvas = ImageCanvas(self)
        self.image_canvas.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self._restore_settings()
        self._poll_queue()  # 主线程轮询工作线程结果
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # 控件
    # ------------------------------------------------------------------
    def _font_names(self):
        names = ["默认"]
        if config.FONTS_DIR.exists():
            names += sorted(
                p.name for p in config.FONTS_DIR.iterdir()
                if p.suffix.lower() in (".ttf", ".otf", ".ttc")
            )
        return names

    def _build_controls(self):
        panel = ctk.CTkScrollableFrame(master=self, width=330)
        panel.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="nsw")
        panel.grid_columnconfigure(0, weight=1)
        self.panel = panel
        r = 0

        # 1. 开始创作
        ctk.CTkLabel(panel, text="1. 选择照片并生成").grid(
            row=r, column=0, sticky="w", padx=12, pady=(10, 2)); r += 1
        self.generate_button = ctk.CTkButton(panel, text="选择照片并生成", command=self.on_generate)
        self.generate_button.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 2. 排版风格
        ctk.CTkLabel(panel, text="2. 排版风格").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.layout_var = StringVar(value="电影竖排")
        self.layout_menu = ctk.CTkOptionMenu(
            panel, values=list(layouts.LAYOUTS), variable=self.layout_var,
            command=self._on_layout_changed)
        self.layout_menu.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 竖排样式（仅电影竖排时显示；grid_remove 可保持位置记忆）
        self.style_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.style_frame.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1
        ctk.CTkLabel(self.style_frame, text="竖排样式:").pack(side="left", padx=(2, 4))
        self.style_var = StringVar(value="保留间隙")
        for text in STRIP_STYLES:
            ctk.CTkRadioButton(self.style_frame, text=text, variable=self.style_var,
                               value=text).pack(side="left", padx=3)

        # 文字样式（电影竖排 / 四宫格支持，单张海报不适用）
        self.text_style_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.text_style_frame.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1
        ctk.CTkLabel(self.text_style_frame, text="文字样式:").pack(side="left", padx=(2, 4))
        self.text_style_var = StringVar(value=TEXT_STYLE_CLASSIC)
        ctk.CTkOptionMenu(self.text_style_frame, values=list(TEXT_STYLES),
                          variable=self.text_style_var, width=130).pack(side="left", padx=3)

        self.count_hint_label = ctk.CTkLabel(panel, text="", text_color="gray")
        self.count_hint_label.grid(row=r, column=0, sticky="w", padx=12, pady=(0, 2)); r += 1

        # 3. 电影滤镜
        ctk.CTkLabel(panel, text="3. 电影滤镜").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.filter_var = StringVar(value="无")
        ctk.CTkOptionMenu(panel, values=["无"] + filters.available_filters(),
                          variable=self.filter_var).grid(
            row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 4. 字体与文字风格
        ctk.CTkLabel(panel, text="4. 字体").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.font_var = StringVar(value="默认")
        ctk.CTkOptionMenu(panel, values=self._font_names(), variable=self.font_var).grid(
            row=r, column=0, sticky="ew", padx=12, pady=2); r += 1
        ctk.CTkLabel(panel, text="5. 文字风格（AI 生成的内容风格）").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.content_var = StringVar(value="简体短句")
        ctk.CTkOptionMenu(panel, values=CONTENT_STYLES, variable=self.content_var).grid(
            row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 6. 清晰度
        ctk.CTkLabel(panel, text="6. 清晰度").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.scale_var = StringVar(value="高清 2×")
        ctk.CTkOptionMenu(panel, values=list(SCALE_OPTIONS), variable=self.scale_var).grid(
            row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 7. AI 配文开关
        self.ai_switch = ctk.CTkSwitch(
            panel, text="AI 配文（关闭则手动写字）",
            onvalue=True, offvalue=False, command=self._on_ai_toggle)
        self.ai_switch.grid(row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        if not self._ai_ready:
            self.ai_switch.deselect()
            self.ai_switch.configure(state="disabled")
            ctk.CTkLabel(
                panel, text="未检测到 .env 配置：已切换为纯手动模式，可在下方直接写字",
                text_color="orange", wraplength=290, justify="left",
            ).grid(row=r, column=0, sticky="w", padx=12, pady=(0, 4)); r += 1

        # 配文输入区（生成后出现 N 个输入框）
        ctk.CTkLabel(panel, text="配文（生成后可在此手动修改）").grid(
            row=r, column=0, sticky="w", padx=12, pady=(12, 2)); r += 1
        self.texts_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.texts_frame.grid(row=r, column=0, sticky="ew", padx=8, pady=(0, 4)); r += 1

        # 操作按钮
        self.rerender_button = ctk.CTkButton(
            panel, text="重新渲染（不调用 AI）", command=self.on_rerender, state="disabled")
        self.rerender_button.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1
        self.regen_text_button = ctk.CTkButton(
            panel, text="重新生成文字（调用 AI）", command=self.on_regen_text, state="disabled")
        self.regen_text_button.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1
        self.save_button = ctk.CTkButton(
            panel, text="保存图片", command=self.on_save, state="disabled")
        self.save_button.grid(row=r, column=0, sticky="ew", padx=12, pady=2); r += 1

        # 进度条（不定长；仅忙时显示）
        self.progress = ctk.CTkProgressBar(panel, mode="indeterminate")
        self.progress.grid(row=r, column=0, sticky="ew", padx=12, pady=(8, 2)); r += 1
        self.progress.grid_remove()
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(panel, text="一切就绪，请开始创作", wraplength=290,
                                         justify="left")
        self.status_label.grid(row=r, column=0, sticky="w", padx=12, pady=(6, 12)); r += 1

    def _on_layout_changed(self, value=None):
        value = value or self.layout_var.get()
        try:
            layout = layouts.get(value)
        except ValueError:
            return
        self.count_hint_label.configure(text=f"请选择 {layout.count_hint()}")
        if value == "电影竖排":
            self.style_frame.grid()
        else:
            self.style_frame.grid_remove()
        # 文字样式对电影竖排 / 四宫格有效，单张海报不适用
        if value in ("电影竖排", "四宫格"):
            self.text_style_frame.grid()
        else:
            self.text_style_frame.grid_remove()

    def _on_ai_toggle(self):
        self._update_action_buttons()

    def _rebuild_text_inputs(self):
        """按当前照片数重建 N 个文字输入框，显示已知文案。"""
        for w in self.texts_frame.winfo_children():
            w.destroy()
        self._text_vars = []
        n = len(self._paths)
        for i in range(n):
            value = self._texts[i] if self._texts and i < len(self._texts) else ""
            var = StringVar(value=value)
            self._text_vars.append(var)
            entry = ctk.CTkEntry(self.texts_frame, textvariable=var,
                                 placeholder_text=f"第 {i + 1} 张的文字（可留空）")
            entry.pack(pady=2, padx=4, fill="x")

    def _collect_texts(self):
        if self._text_vars:
            return [v.get() for v in self._text_vars]
        return [""] * max(1, len(self._paths))

    def _update_action_buttons(self):
        has_result = self._result is not None
        ai_on = self._ai_ready and bool(self.ai_switch.get())
        self.rerender_button.configure(
            state="normal" if (has_result and not self._busy) else "disabled")
        self.regen_text_button.configure(
            state="normal" if (has_result and ai_on and not self._busy) else "disabled")
        self.save_button.configure(
            state="normal" if (has_result and not self._busy) else "disabled")

    def _set_busy(self, busy, message="正在生成..."):
        self._busy = busy
        if busy:
            self.generate_button.configure(state="disabled", text="生成中...")
            self.progress.grid()
            self.progress.start()
            self.status_label.configure(text=message, text_color="gray")
        else:
            self.generate_button.configure(state="normal", text="选择照片并生成")
            self.progress.stop()
            self.progress.grid_remove()
        self._update_action_buttons()

    # ------------------------------------------------------------------
    # 生成流程
    # ------------------------------------------------------------------
    def on_generate(self):
        if self._busy:
            return
        try:
            layout = layouts.get(self.layout_var.get())
        except ValueError as e:
            self.status_label.configure(text=str(e), text_color="red")
            return
        paths = self._ask_photos(layout)
        if not paths:
            return
        self._paths = paths
        self._texts = None
        self._photo_cache.clear()  # 换了一组照片，清掉旧缓存
        self._result = None
        self._rebuild_text_inputs()
        self._start_build(texts=None, use_ai=True)

    def _ask_photos(self, layout):
        types = [("图片文件", "*.jpg *.jpeg *.png *.webp *.bmp")]
        try:
            import pillow_heif  # 可选依赖：装了才支持 HEIC

            pillow_heif.register_heif_opener()
            types.append(("HEIC 图片", "*.heic *.heif"))
        except ImportError:
            pass
        types.append(("所有文件", "*.*"))
        paths = filedialog.askopenfilenames(
            title=f"请选择 {layout.count_hint()}",
            filetypes=types,
        )
        if not paths:
            self.status_label.configure(text="已取消选择", text_color="gray")
            return None
        if not (layout.min_photos <= len(paths) <= layout.max_photos):
            self.status_label.configure(
                text=f"错误：需要 {layout.count_hint()}，实际选择了 {len(paths)} 张",
                text_color="red")
            return None
        return list(paths)

    def on_rerender(self):
        """用输入框里的文字 + 当前全部设置重新渲染，不调用 AI（省 token）。"""
        if self._busy or not self._paths:
            return
        self._texts = self._collect_texts()
        self._start_build(texts=self._texts, use_ai=False)

    def on_regen_text(self):
        """重新调用 AI 生成文字（会覆盖输入框内容）。"""
        if self._busy or not self._paths:
            return
        self._start_build(texts=None, use_ai=True)

    def _collect_options(self, use_ai):
        return pipeline.BuildOptions(
            layout=self.layout_var.get(),
            strip_style=self.style_var.get(),
            text_style=self.text_style_var.get(),
            filter_name=self.filter_var.get(),
            font_name=self.font_var.get(),
            content_style=self.content_var.get(),
            scale=SCALE_OPTIONS.get(self.scale_var.get(), 2.0),
            ai_enabled=use_ai and self._ai_ready and bool(self.ai_switch.get()),
        )

    def _start_build(self, texts, use_ai):
        options = self._collect_options(use_ai)
        ai_client = ai_connector if (texts is None and options.ai_enabled) else None
        self._set_busy(True)

        def work():
            # 工作线程：只做纯计算，结果投递到队列
            try:
                result = pipeline.build(
                    self._paths, options,
                    ai_client=ai_client, texts=texts,
                    image_cache=self._photo_cache,
                )
                self._queue.put(("done", result))
            except Exception as e:
                logger.exception("生成失败")
                self._queue.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _poll_queue(self):
        """主线程每 100ms 轮询一次工作线程结果。"""
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "done":
                    self._on_build_done(payload)
                elif kind == "error":
                    self._on_build_error(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _on_build_done(self, result):
        self._result = result
        self._texts = list(result.texts)
        self._set_busy(False)
        self._rebuild_text_inputs()
        self.image_canvas.show_image(result.image)
        if result.warnings:
            self.status_label.configure(text="；".join(result.warnings), text_color="orange")
        else:
            self.status_label.configure(
                text="大功告成！可修改左侧文字后「重新渲染」", text_color="green")

    def _on_build_error(self, message):
        self._set_busy(False)
        self.status_label.configure(text=f"生成失败：{message}", text_color="red")

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def on_save(self):
        if self._result is None:
            return
        initial_dir = self.settings.get("last_save_dir") or None
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 图片", "*.png"), ("JPEG 图片", "*.jpg")],
            title="保存图片",
            initialfile=f"photomagic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            initialdir=initial_dir,
        )
        if not path:
            self.status_label.configure(text="保存已取消", text_color="gray")
            return
        try:
            if path.lower().endswith((".jpg", ".jpeg")):
                self._result.image.save(path, quality=95)
            else:
                self._result.image.save(path)
            self.settings["last_save_dir"] = str(Path(path).parent)
            config.save_settings(self.settings)
            self.status_label.configure(text=f"已保存：{path}", text_color="green")
            logger.info(f"图片已保存到 {path}")
        except Exception as e:
            logger.exception("保存失败")
            self.status_label.configure(text=f"保存失败：{e}", text_color="red")

    # ------------------------------------------------------------------
    # 设置持久化
    # ------------------------------------------------------------------
    def _restore_settings(self):
        s = self.settings
        if s.get("layout") in layouts.LAYOUTS:
            self.layout_var.set(s["layout"])
        if s.get("strip_style") in STRIP_STYLES:
            self.style_var.set(s["strip_style"])
        if s.get("text_style") in TEXT_STYLES:
            self.text_style_var.set(s["text_style"])
        if s.get("filter") in (["无"] + filters.available_filters()):
            self.filter_var.set(s["filter"])
        if s.get("font") in self._font_names():
            self.font_var.set(s["font"])
        if s.get("content_style") in CONTENT_STYLES:
            self.content_var.set(s["content_style"])
        if s.get("scale") in SCALE_OPTIONS:
            self.scale_var.set(s["scale"])
        if self._ai_ready and s.get("ai_enabled", True):
            self.ai_switch.select()
        else:
            self.ai_switch.deselect()
        self._on_layout_changed()
        self._update_action_buttons()

    def _save_settings(self):
        self.settings.update({
            "layout": self.layout_var.get(),
            "strip_style": self.style_var.get(),
            "text_style": self.text_style_var.get(),
            "filter": self.filter_var.get(),
            "font": self.font_var.get(),
            "content_style": self.content_var.get(),
            "scale": self.scale_var.get(),
            "ai_enabled": bool(self.ai_switch.get()) if self._ai_ready else True,
            "last_save_dir": self.settings.get("last_save_dir", ""),
        })
        config.save_settings(self.settings)

    def _on_close(self):
        try:
            self._save_settings()
        finally:
            self.destroy()
