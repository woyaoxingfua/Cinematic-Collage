# file: app_ui.py (终极交互版)

import customtkinter as ctk
from tkinter import filedialog, StringVar
from PIL import Image, ImageTk  # 添加ImageTk模块
import layouts
import ai_connector
import threading
import os  # 添加os模块用于读取目录内容
from datetime import datetime  # 添加datetime模块用于生成文件名


# ===================================================================
# 【新】创建一个专门用于图片交互的画布控件类
class ImageCanvas(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        # 创建画布控件
        self.canvas = ctk.CTkCanvas(self, background="#2B2B2B", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # 初始化状态变量
        self.original_image = None  # 存储原始的、未经缩放的Pillow图片
        self.display_image = None  # 存储当前显示在画布上的CTkImage对象
        self.scale = 1.0  # 当前的缩放比例
        self.image_x = 0  # 图片在画布上的X坐标
        self.image_y = 0  # 图片在画布上的Y坐标

        # 绑定滑鼠事件
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # 滚轮缩放
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)  # 左键按下
        self.canvas.bind("<B1-Motion>", self.on_drag)  # 左键拖动

    def show_image(self, pillow_image):
        """外部调用此方法来载入一张新图片"""
        self.original_image = pillow_image
        self.fit_image_to_canvas()

    def fit_image_to_canvas(self):
        """【修正版】计算最佳缩放比例，让图片完整地显示在画布中央"""
        if not self.original_image:
            return

        # 【核心修正】在获取尺寸前，强制UI更新布局信息，确保获取到的是真实尺寸
        self.canvas.update_idletasks()

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # 【删除】我们不再需要延时重试的逻辑了

        # ...后续的缩放和居中逻辑保持不变...
        img_ratio = self.original_image.width / self.original_image.height
        canvas_ratio = canvas_width / canvas_height

        if img_ratio > canvas_ratio:
            self.scale = canvas_width / self.original_image.width
        else:
            self.scale = canvas_height / self.original_image.height

        self.image_x = (canvas_width - self.original_image.width * self.scale) / 2
        self.image_y = (canvas_height - self.original_image.height * self.scale) / 2

        self._redraw_image()

    def _redraw_image(self):
        """核心重绘函数：根据当前缩放和位置，在画布上重新绘制图片"""
        if not self.original_image:
            return

        # 清空画布
        self.canvas.delete("all")

        # 根据缩放比例计算新的宽高
        new_width = int(self.original_image.width * self.scale)
        new_height = int(self.original_image.height * self.scale)

        # 使用Pillow缩放图片
        resized_img = self.original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 转换为PhotoImage并放置在画布上
        self.display_image = ImageTk.PhotoImage(resized_img)
        self.canvas.create_image(self.image_x, self.image_y, anchor="nw", image=self.display_image)

    def on_mouse_wheel(self, event):
        """响应鼠标滚轮事件，进行缩放"""
        # event.delta 在Windows和macOS上符号不同，但通常是120的倍数
        if event.delta > 0:
            self.scale *= 1.1  # 放大
        else:
            self.scale /= 1.1  # 缩小
        self._redraw_image()

    def on_button_press(self, event):
        """响应鼠标左键按下事件，记录拖动起点"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag(self, event):
        """响应鼠标拖动事件，移动图片"""
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        self.image_x += dx
        self.image_y += dy

        # 更新拖动起点
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        self._redraw_image()


# ===================================================================

class PhotoBoothApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.style_choice_var = StringVar(value="保留间隙")
        self.title("电影感照片生成器 V2.2 - 交互式预览")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.bind("<Configure>", self.on_resize)  # 窗口大小变化时也需要重绘

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(0, weight=1)
        self.setup_ui()

    def get_font_options(self):
        """获取fonts目录下的所有字体文件"""
        font_options = ["默认"]
        if os.path.exists("fonts"):
            for file in os.listdir("fonts"):
                if file.endswith((".ttf", ".otf", ".ttc")):
                    font_options.append(file)
        return font_options

    def get_filter_options(self):
        """获取luts目录下的所有滤镜文件"""
        filter_options = ["无"]
        if os.path.exists("luts"):
            for file in os.listdir("luts"):
                if file.endswith(".cube"):
                    # 移除文件扩展名
                    filter_name = file[:-5]  # 移除 ".cube" 扩展名
                    filter_options.append(filter_name)
        return filter_options

    def setup_ui(self):
        control_frame = ctk.CTkFrame(master=self)
        control_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        # ... (左侧控制面板的UI控件创建和之前一样，此处省略) ...
        ctk.CTkLabel(master=control_frame, text="1. 开始创作").pack(pady=(20, 5), padx=20)
        self.process_button = ctk.CTkButton(master=control_frame, text="选择照片并生成",
                                            command=self.start_generation_thread)
        self.process_button.pack(pady=5, padx=20)
        ctk.CTkLabel(master=control_frame, text="2. 选择排版风格").pack(pady=(20, 5), padx=20)
        layout_options = ["电影竖排", "单张海报"]
        self.layout_option_menu = ctk.CTkOptionMenu(master=control_frame, values=layout_options)
        self.layout_option_menu.pack(pady=5, padx=20, fill="x")
        style_frame = ctk.CTkFrame(master=control_frame)
        style_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(master=style_frame, text="竖排样式:").pack(side="left", padx=10)
        ctk.CTkRadioButton(master=style_frame, text="保留间隙", variable=self.style_choice_var, value="保留间隙").pack(
            side="left", padx=5)
        ctk.CTkRadioButton(master=style_frame, text="无缝拼接", variable=self.style_choice_var, value="无缝拼接").pack(
            side="left", padx=5)
        ctk.CTkLabel(master=control_frame, text="3. 选择电影滤镜").pack(pady=(20, 5), padx=20)
        # 使用动态加载的滤镜选项
        filter_options = self.get_filter_options()
        self.filter_option_menu = ctk.CTkOptionMenu(master=control_frame, values=filter_options)
        self.filter_option_menu.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(master=control_frame, text="4. 选择文字风格").pack(pady=(20, 5), padx=20)
        # 使用动态加载的字体选项
        font_options = self.get_font_options()
        self.font_option_menu = ctk.CTkOptionMenu(master=control_frame, values=font_options)
        self.font_option_menu.pack(pady=5, padx=20, fill="x")
        content_style_options = ["简体短句", "繁体诗歌", "英文散文"]
        self.content_style_menu = ctk.CTkOptionMenu(master=control_frame, values=content_style_options)
        self.content_style_menu.pack(pady=10, padx=20, fill="x")
        
        # 添加保存图片按钮
        self.save_button = ctk.CTkButton(master=control_frame, text="保存图片", 
                                        command=self.save_image, state="disabled")
        self.save_button.pack(pady=10, padx=20, fill="x")
        
        self.status_label = ctk.CTkLabel(master=control_frame, text="一切就绪，请开始创作")
        self.status_label.pack(pady=20, padx=20)

        # 【核心修改】用我们新的ImageCanvas替换掉旧的Frame和Label
        self.image_canvas = ImageCanvas(self)
        self.image_canvas.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
    def on_resize(self, event):
        """当整个App窗口大小改变时，让图片自适应"""
        # 调用我们自定义控件的自适应方法
        self.image_canvas.fit_image_to_canvas()

    def on_resize(self, event):
        """当整个App窗口大小改变时，让图片自适应"""
        # 调用我们自定义控件的自适应方法
        self.image_canvas.fit_image_to_canvas()

    # # ... (start_generation_thread, generation_logic, select_files_and_proceed 等函数保持不变) ...
    def start_generation_thread(self):
        self.process_button.configure(state="disabled", text="生成中...")
        thread = threading.Thread(target=self.generation_logic)
        thread.daemon = True
        thread.start()

    def generation_logic(self):
        selected_layout = self.layout_option_menu.get()
        selected_style = self.style_choice_var.get()
        selected_filter = self.filter_option_menu.get()
        selected_font = self.font_option_menu.get()
        selected_content_style = self.content_style_menu.get()
        num_images_needed = 3 if selected_layout == "电影竖排" else 1
        self.after(0, lambda: self.select_files_and_proceed(num_images_needed, selected_layout, selected_style,
                                                            selected_filter, selected_font, selected_content_style))

    def select_files_and_proceed(self, num_images, *args):
        image_paths = filedialog.askopenfilenames(title=f"请选择 {num_images} 张照片",
                                                  filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if len(image_paths) != num_images:
            self.status_label.configure(text=f"错误: 需要 {num_images} 张图片!", text_color="red")
            self.process_button.configure(state="normal", text="选择照片并生成")
            return
        thread = threading.Thread(target=self.process_after_selection, args=(image_paths, *args))
        thread.daemon = True
        thread.start()

    def process_after_selection(self, image_paths, selected_layout, selected_style, selected_filter, selected_font,
                                selected_content_style):
        try:
            self.status_label.configure(text="图片处理中...")
            images = [Image.open(p) for p in image_paths]

            # 【核心修正】调整操作顺序：先应用滤镜
            self.status_label.configure(text="滤镜应用中...")
            # 1. 先对原始图片应用滤镜
            filtered_images = [layouts.apply_filter(img, selected_filter) for img in images]

            # 将用户的布局选择打包，方便传递
            layout_params = {'style': selected_style}

            self.status_label.configure(text="正在生成布局...")
            # 2. 然后用处理过的图片去创建布局
            if selected_layout == "电影竖排":
                composed_image = layouts.create_film_strip_layout(filtered_images, style=selected_style)
            else:  # 单张海报
                composed_image = layouts.create_poster_layout(filtered_images)

            self.status_label.configure(text="正在请求AI生成文字...")
            # 3. 把带边框但不带文字的图发给AI
            ai_texts = ai_connector.get_ai_text(composed_image, selected_content_style, len(images))

            self.status_label.configure(text="正在绘制文字...")
            # 4. 最后在图上绘制文字
            self.final_image_with_text = layouts.draw_text_on_image(
                image=composed_image,
                texts=ai_texts,
                layout_style=selected_layout,
                font_name=selected_font,
                original_images=images,  # 仍然传入最原始的图片用于尺寸计算
                layout_params=layout_params
            )

            self.after(0, self.update_status_and_display, self.final_image_with_text)

        except Exception as e:
            self.status_label.configure(text=f"发生未知错误: {e}", text_color="red")
        finally:
            self.process_button.configure(state="normal", text="选择照片并生成")

    def update_status_and_display(self, final_image):
        """更新状态，并让新的画布控件显示图片"""
        self.status_label.configure(text="大功告成！请在右侧交互！", text_color="green")
        self.image_canvas.show_image(final_image)
        # 启用保存按钮
        self.save_button.configure(state="normal")

    def save_image(self):
        """保存生成的图片到本地"""
        if not hasattr(self, 'final_image_with_text'):
            self.status_label.configure(text="没有可保存的图片！", text_color="red")
            return
            
        try:
            # 打开保存文件对话框
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
                title="保存图片",
                initialfile=f"photomagic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # 如果用户选择了文件路径，则保存图片
            if file_path:
                self.final_image_with_text.save(file_path)
                self.status_label.configure(text=f"图片已保存到: {file_path}", text_color="green")
            else:
                self.status_label.configure(text="保存操作已取消", text_color="green")
        except Exception as e:
            self.status_label.configure(text=f"保存图片时出错: {str(e)}", text_color="red")