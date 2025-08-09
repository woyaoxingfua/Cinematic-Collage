# import customtkinter as ctk
# from tkinter import filedialog
# from PIL import Image, ImageTk, ImageDraw
#
#
# # --- 全局变量 ---
# # 我们不再需要全局变量了，因为我们会把图片对象作为参数传来传去，这是更好的编程习惯
# # selected_image_paths = [] (删除)
# # composed_image_tk = None (删除)
#
#
# # ===================================================================
# # 【新功能模块一】：创建“电影竖排”布局的专属函数
# def create_film_strip_layout(images):
#     """
#     【增强版】
#     接收图片列表，返回一张带有电影边孔效果的、拼接好的Pillow图片对象。
#     """
#     # --- 1. 定义布局参数，让细节更可控 ---
#     image_width = 600  # 主图片区域的宽度
#     sidebar_width = 60   # 两侧边条的宽度
#     gap = 25           # 图片之间的垂直间隙
#     hole_size = 12     # 边孔的大小
#     hole_margin = (sidebar_width - hole_size) // 2 # 边孔距离边缘的距离
#     hole_spacing = hole_size * 2.5 # 边孔之间的垂直距离
#
#     # --- 2. 准备图片 ---
#     # 统一图片宽度，并保持长宽比
#     resized_images = []
#     for img in images:
#         ratio = image_width / img.width
#         target_height = int(img.height * ratio)
#         resized_images.append(img.resize((image_width, target_height), Image.Resampling.LANCZOS))
#
#     # --- 3. 创建画布 ---
#     # 计算总尺寸
#     total_image_height = sum(img.height for img in resized_images)
#     total_gap_height = gap * (len(resized_images) - 1)
#     total_height = total_image_height + total_gap_height
#     total_width = sidebar_width + image_width + sidebar_width
#
#     # 创建一个黑色的底画布
#     composed_image = Image.new('RGB', (total_width, total_height), 'black')
#
#     # --- 4. 粘贴图片 ---
#     # 像之前一样，把图片依次贴上去，但这次X坐标要向右移动一个边条的宽度
#     current_y = 0
#     for img in resized_images:
#         composed_image.paste(img, (sidebar_width, current_y))
#         current_y += img.height + gap
#
#     # --- 5. 绘制边孔 (最关键的美化步骤) ---
#     # 创建一个绘图对象
#     draw = ImageDraw.Draw(composed_image)
#     hole_color = (25, 25, 25) # 使用深灰色，比纯白或纯黑更有质感
#
#     # 从上到下，循环绘制两侧的边孔
#     for y in range(int(hole_spacing // 2), total_height, int(hole_spacing)):
#         # 左侧边孔
#         left_hole_x0 = hole_margin
#         left_hole_y0 = y
#         left_hole_x1 = left_hole_x0 + hole_size
#         left_hole_y1 = y + hole_size
#         draw.rectangle([left_hole_x0, left_hole_y0, left_hole_x1, left_hole_y1], fill=hole_color)
#
#         # 右侧边孔
#         right_hole_x0 = image_width + sidebar_width + hole_margin
#         right_hole_y0 = y
#         right_hole_x1 = right_hole_x0 + hole_size
#         right_hole_y1 = y + hole_size
#         draw.rectangle([right_hole_x0, right_hole_y0, right_hole_x1, right_hole_y1], fill=hole_color)
#
#     return composed_image
#
#
# # 【新功能模块二】：创建“单张海报”布局的专属函数 (目前只是一个占位符)
# def create_poster_layout(images):
#     """
#     “单张海报”的专职处理函数。
#     目前，它只简单地返回列表中的第一张图片。
#     """
#     # 我们先做最简单的版本，直接返回第一张图，后续再优化
#     return images[0]
#
#
# # ===================================================================
#
# # 【重大改造】：“调度中心”函数
# def process_images_based_on_selection():
#     """
#     这是新的主逻辑函数，它像一个调度中心。
#     """
#     # 1. 从UI获取用户选择的布局风格
#     selected_layout = layout_option_menu.get()
#     print(f"用户选择了布局: {selected_layout}")
#
#     # 2. 根据不同的布局，确定需要几张图片，并引导用户选择
#     num_images_needed = 0
#     if selected_layout == "电影竖排 (待优化)":
#         num_images_needed = 3
#     elif selected_layout == "单张海报 (待开发)":
#         num_images_needed = 1
#
#     image_paths = filedialog.askopenfilenames(
#         title=f"请选择 {num_images_needed} 张照片",
#         filetypes=[("Image Files", "*.jpg *.jpeg *.png")]
#     )
#
#     # 3. 检查用户选择的图片数量是否正确
#     if len(image_paths) != num_images_needed:
#         status_label.configure(text=f"错误: 此布局需要 {num_images_needed} 张图片!", text_color="red")
#         return
#
#     status_label.configure(text="正在处理图片...", text_color="gray")
#
#     try:
#         # 4. 打开所有图片
#         images = [Image.open(p) for p in image_paths]
#
#         # 5. 【调度核心】：根据用户的选择，调用相应的专职函数
#         composed_image = None
#         if selected_layout == "电影竖排 (待优化)":
#             composed_image = create_film_strip_layout(images)
#         elif selected_layout == "单张海报 (待开发)":
#             composed_image = create_poster_layout(images)
#
#         # 6. 显示最终结果图
#         if composed_image:
#             # 【Bug修复】我们不再获取 Label 的大小，而是获取它所在的、尺寸更稳定的父容器 display_frame 的大小
#             container_width = display_frame.winfo_width()
#             container_height = display_frame.winfo_height()
#
#             # 创建一个副本用于显示，不影响原始大图
#             display_image = composed_image.copy()
#
#             # 使用 thumbnail 方法按比例缩放，确保图片能完整显示在容器内
#             # 我们从容器尺寸里减去一点，是为了留出边距，更好看
#             display_image.thumbnail((container_width - 40, container_height - 40))
#
#             ctk_image = ImageTk.PhotoImage(display_image)
#             image_display_label.configure(image=ctk_image, text="")
#             image_display_label.image = ctk_image # 必须保留引用，否则图片不显示
#             status_label.configure(text="生成成功！", text_color="green")
#         else:
#             status_label.configure(text="错误: 未知布局", text_color="red")
#
#     except Exception as e:
#         print(f"处理图片时发生错误: {e}")
#         status_label.configure(text=f"错误: {e}", text_color="red")
#
#
# # --- 主程式视窗与UI布局 (这部分几乎不变) ---
# app = ctk.CTk()
# app.title("电影感照片生成器 V0.4 - 调度中心已建立")
# app.geometry("1200x800")
# ctk.set_appearance_mode("dark")
#
# app.grid_columnconfigure(0, weight=1)
# app.grid_columnconfigure(1, weight=3)
# app.grid_rowconfigure(0, weight=1)
#
# # --- 左侧控制面板 ---
# control_frame = ctk.CTkFrame(master=app)
# control_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
#
# button_label = ctk.CTkLabel(master=control_frame, text="1. 开始创作")
# button_label.pack(pady=(20, 5), padx=20)
#
# # 【重要改变】按钮现在调用的是我们新的调度函数
# process_button = ctk.CTkButton(
#     master=control_frame,
#     text="选择照片并生成",
#     command=process_images_based_on_selection
# )
# process_button.pack(pady=5, padx=20)
#
# layout_label = ctk.CTkLabel(master=control_frame, text="2. 选择排版风格")
# layout_label.pack(pady=(30, 5), padx=20)
#
# layout_options = ["电影竖排 (待优化)", "单张海报 (待开发)"]
# layout_option_menu = ctk.CTkOptionMenu(master=control_frame, values=layout_options)
# layout_option_menu.pack(pady=5, padx=20, fill="x")
#
# status_label = ctk.CTkLabel(master=control_frame, text="请选择风格后，点击上方按钮")
# status_label.pack(pady=30, padx=20)
#
# # --- 右侧图片显示区 ---
# display_frame = ctk.CTkFrame(master=app)
# display_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
#
# image_display_label = ctk.CTkLabel(master=display_frame, text="这里将显示处理后的图片")
# image_display_label.pack(pady=20, padx=20, expand=True)
#
# app.mainloop()

# file: main.py

from app_ui import PhotoBoothApp # 从我们的UI文件，导入应用主类

if __name__ == "__main__":
    app = PhotoBoothApp() # 实例化应用
    app.mainloop()      # 运行应用