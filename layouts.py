# file: layouts.py
import numpy as np
import colour
from PIL import Image, ImageDraw, ImageFont


def create_film_strip_layout(images, style="保留间隙"):
    """
    【功能确认版】
    确保胶卷边框和齿孔效果能正确显示。
    """
    # --- 1. 定义布局参数 ---
    image_width = 600
    sidebar_width = 60

    if style == "保留间隙":
        gap = 25
    else:  # "无缝拼接"
        gap = 0

    hole_size = 12
    hole_margin = (sidebar_width - hole_size) // 2
    hole_spacing = hole_size * 2.5

    # --- 2. 准备图片 ---
    resized_images = []
    for img in images:
        ratio = image_width / img.width
        target_height = int(img.height * ratio)
        resized_images.append(img.resize((image_width, target_height), Image.Resampling.LANCZOS))

    # --- 3. 创建画布 ---
    total_image_height = sum(img.height for img in resized_images)
    total_gap_height = gap * (len(resized_images) - 1)
    total_height = total_image_height + total_gap_height
    total_width = sidebar_width + image_width + sidebar_width

    composed_image = Image.new('RGB', (total_width, total_height), 'black')

    # --- 4. 粘贴图片 ---
    current_y = 0
    for img in resized_images:
        composed_image.paste(img, (sidebar_width, current_y))
        current_y += img.height + gap

    # --- 5. 绘制边孔 ---
    draw = ImageDraw.Draw(composed_image)
    hole_color = (25, 25, 25)

    for y in range(int(hole_spacing // 2), total_height, int(hole_spacing)):
        left_hole_x0 = hole_margin
        left_hole_y0 = y
        left_hole_x1 = left_hole_x0 + hole_size
        left_hole_y1 = y + hole_size
        draw.rectangle([left_hole_x0, left_hole_y0, left_hole_x1, left_hole_y1], fill=hole_color)

        right_hole_x0 = image_width + sidebar_width + hole_margin
        right_hole_y0 = y
        right_hole_x1 = right_hole_x0 + hole_size
        right_hole_y1 = y + hole_size
        draw.rectangle([right_hole_x0, right_hole_y0, right_hole_x1, right_hole_y1], fill=hole_color)

    return composed_image


def create_poster_layout(images):
    """
    【最终版 - 参照用户图片】
    实现非对称的“拍立得/画廊打印”风格，顶部和两侧是窄边，底部是宽边。
    """
    # --- 1. 定义画框参数 ---
    # 非对称边框，顶部和两侧使用一个尺寸，底部使用一个更宽的尺寸
    side_padding = 50       # 上、左、右三边的边框宽度
    bottom_padding = 180    # 底部边框的宽度，留出更多空间
    frame_color = (255, 255, 255) # 纯白色画框

    # --- 2. 准备图片 ---
    image = images[0]
    # 设定一个最大宽度，防止图片过大
    max_width = 800
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    # --- 3. 计算最终画布尺寸 ---
    # 画布的宽度 = 左边框 + 图片宽度 + 右边框
    canvas_width = side_padding + image.width + side_padding
    # 画布的高度 = 上边框 + 图片高度 + 下边框
    canvas_height = side_padding + image.height + bottom_padding
    
    # --- 4. 创建纯白画布并粘贴图片 ---
    # 这次的逻辑更简单：先创建一块纯白的“相纸”
    final_image = Image.new('RGB', (canvas_width, canvas_height), frame_color)
    
    # 然后，把用户的照片精确地“贴”在相纸的正确位置上
    # X坐标 = 左边框宽度
    # Y坐标 = 上边框宽度
    paste_position = (side_padding, side_padding)
    final_image.paste(image, paste_position)
    
    return final_image


def apply_filter(image, filter_name):
    """
    【再次修正版】
    使用 'colour-science' 库更稳定的方法来应用LUT滤镜。
    """
    if filter_name == "无":
        return image

    try:
        lut_path = f"luts/{filter_name}.cube"

        # 1. 使用 colour.io.luts.read_LUT 方法加载LUT (根据项目规范)
        lut = colour.io.luts.read_LUT(lut_path)

        # 2. 将Pillow图片转换为NumPy数组，并确保颜色值在0-1之间
        image = image.convert("RGB")  # 确保是RGB格式
        image_array = np.array(image) / 255.0

        # 3. 应用LUT
        filtered_array = lut.apply(image_array)

        # 4. 将处理后的0-1浮点数数组转换回0-255的整数数组
        filtered_array_8bit = (np.clip(filtered_array, 0, 1) * 255).astype(np.uint8)

        # 5. 将NumPy数组转换回Pillow图片对象
        return Image.fromarray(filtered_array_8bit)

    except FileNotFoundError:
        print(f"错误：找不到滤镜文件 {lut_path}！请检查luts文件夹和文件名。")
        return image
    except Exception as e:
        print(f"应用滤镜时发生错误: {e}")
        return image


def draw_text_on_image(image, texts, layout_style, font_name, original_images, layout_params):
    """
    【终极修正版】
    修正了单张海报布局的文字Y坐标计算问题。
    """
    if not texts:
        texts = ["未能获取文字"]

    draw = ImageDraw.Draw(image)
    font_path = f"fonts/{font_name}" if font_name != "默认" else None

    if layout_style == "单张海报":
        text = texts[0]
        font_size = 40
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()

        # 【核心修正】精确计算文字写入位置
        # 1. 获取原始照片尺寸信息，以便定位照片下边缘
        side_padding = 50  # 这个值必须和 create_poster_layout 中的一致
        max_width = 800  # 这个值也必须一致
        original_photo = original_images[0]
        if original_photo.width > max_width:
            ratio = max_width / original_photo.width
            photo_height = int(original_photo.height * ratio)
        else:
            photo_height = original_photo.height

        # 2. 计算文字区域和起始Y坐标
        # 文字区域的顶部，在照片下边缘再往下一点
        text_area_top_y = side_padding + photo_height + 40  # 40是照片与文字的间距

        text_area_width = image.width - (side_padding * 2)
        wrapped_lines = wrap_text(draw, text, text_area_width, font)

        # 3. 逐行绘制
        current_y = text_area_top_y
        for line in wrapped_lines:
            line_bbox = draw.textbbox((0, 0), line, font=font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = (image.width - line_width) / 2  # 水平居中
            draw.text((line_x, current_y), line, font=font, fill=(50, 50, 50))
            current_y += font_size * 1.2  # 1.2倍行距

    elif layout_style == "电影竖排":
        # ... (这部分逻辑保持不变) ...
        font_size = 28
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()
        params = {"image_width": 600, "sidebar_width": 60, "gap": 25 if layout_params.get('style') == "保留间隙" else 0}
        current_y = 0
        for i, original_img in enumerate(original_images):
            ratio = params["image_width"] / original_img.width
            img_height = int(original_img.height * ratio)
            text = texts[i] if i < len(texts) else ""
            text_area_width = params["image_width"] - 40
            wrapped_lines = wrap_text(draw, text, text_area_width, font)
            total_text_height = len(wrapped_lines) * font_size
            start_y = current_y + img_height - total_text_height - 20
            for line in wrapped_lines:
                line_x = params["sidebar_width"] + 20
                draw.text((line_x, start_y), line, font=font, fill=(240, 240, 240), stroke_width=1,
                          stroke_fill=(0, 0, 0))
                start_y += font_size
            current_y += img_height + params["gap"]

    return image


def wrap_text(draw, text, width, font):
    """
    【中文优化版】
    一个辅助函数，用于将长文本（包括中文）换行。
    """
    lines = []
    if not text:
        return lines

    current_line = ""
    for char in text:
        # 检查加上新字符后是否会超宽
        if draw.textbbox((0, 0), current_line + char, font=font)[2] <= width:
            current_line += char
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)

    return lines
