# tools/capture_screenshot.py —— 生成 README 用应用截图（需桌面环境）
# 启动 V3 界面、用合成风景照片走一次完整生成（不调 AI），然后把窗口截屏存为 img.png
# 用法：.venv/Scripts/python.exe tools/capture_screenshot.py
import ctypes
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:  # 让 tkinter 用物理像素，保证截屏坐标与窗口边缘对齐
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageGrab  # noqa: E402

import app_ui  # noqa: E402


def scenic_photo(w, h, top, bottom, sun, hills):
    """合成「风景照」：竖向天色渐变 + 太阳 + 两层山形剪影（截图素材用）。"""
    t = np.linspace(0.0, 1.0, h)[:, None, None]
    top, bottom = np.array(top, float), np.array(bottom, float)
    arr = top[None, None, :] * (1 - t) + bottom[None, None, :] * t
    img = Image.fromarray(np.repeat(arr, w, axis=1).astype(np.uint8))
    d = ImageDraw.Draw(img)
    cx, cy, r = int(w * 0.62), int(h * 0.20), int(h * 0.09)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=sun)
    d.polygon([(0, h), (w * 0.38, h * 0.60), (w * 0.72, h)], fill=hills[0])
    d.polygon([(w * 0.30, h), (w * 0.78, h * 0.52), (w * 1.05, h)], fill=hills[1])
    return img


def make_photos(tmp):
    scenes = [
        ((252, 178, 110), (96, 62, 96), (255, 214, 150), (58, 44, 60), (34, 28, 40)),   # 黄昏
        ((96, 130, 176), (26, 34, 58), (210, 228, 245), (30, 38, 56), (18, 24, 38)),    # 蓝调时刻
        ((240, 200, 160), (150, 92, 78), (255, 236, 200), (70, 46, 46), (44, 30, 32)),  # 破晓
    ]
    paths = []
    for i, (top, bottom, sun, h1, h2) in enumerate(scenes):
        p = Path(tmp) / f"scene{i}.png"
        scenic_photo(900, 620 if i != 1 else 1200, top, bottom, sun, (h1, h2)).save(p)
        paths.append(str(p))
    return paths


def main():
    tmp = tempfile.mkdtemp(prefix="photomagic_shot_")
    paths = make_photos(tmp)

    app = app_ui.PhotoBoothApp()
    app.geometry("1280x980+80+40")
    app.attributes("-topmost", True)  # 截屏时保证窗口在最前

    # 选好上镜的设置：电影字幕样式 + BlueArchitecture 滤镜 + 高清 2×
    app.text_style_var.set("电影字幕")
    app.filter_var.set("BlueArchitecture")
    app.scale_var.set("高清 2×")
    app.style_var.set("保留间隙")

    state = {"done_at": None}

    def start():
        app._paths = paths
        app._texts = None
        app._photo_cache.clear()
        app._result = None
        app._rebuild_text_inputs()
        app._start_build(texts=[
            "晚风把黄昏折成了一封信",
            "The city hums a quiet song",
            "灯亮起时，故事才刚开始",
        ], use_ai=False)

    def poll(n=0):
        if app._result is not None:
            if state["done_at"] is None:
                state["done_at"] = n
            # 完成后再等几帧，确保画布 LANCZOS 高质量重绘完成
            if n - state["done_at"] >= 6:
                grab()
                return
        app.after(150, lambda: poll(n + 1))

    def grab():
        # 截屏前强制重排一次画布（消除任何时序竞争），并打印诊断信息
        app.image_canvas.fit_to_window()
        app.update_idletasks()
        app.update()
        cv = app.image_canvas
        print(f"诊断：画布 {cv.canvas.winfo_width()}x{cv.canvas.winfo_height()}，"
              f"成图 {cv.original_image.size}，缩放 {cv.scale:.3f}，"
              f"位置 ({cv.image_x:.0f},{cv.image_y:.0f})")
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        shot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        shot = shot.crop((6, 6, w - 6, h - 6))  # 内缩几像素，去掉窗口边缘/阴影残留
        shot.save(ROOT / "img.png")
        print(f"截图已保存：{ROOT / 'img.png'}（{shot.width}x{shot.height}）")
        app.destroy()

    app.after(500, start)
    app.after(1200, poll)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
