# tools/ui_selftest.py —— UI 程序化自检（需要桌面环境；不弹对话框、不调真实 AI）
# 用法：.venv/Scripts/python.exe tools/ui_selftest.py   退出码 0 = 全部通过
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app_ui  # noqa: E402
from tests.helpers import make_photo  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        failures.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="photomagic_selftest_")
    paths = []
    for i in range(3):
        p = Path(tmp) / f"photo{i}.png"
        make_photo(600, 450, i).save(p)
        paths.append(str(p))

    app = app_ui.PhotoBoothApp()

    def step1():
        check("窗口标题含 V3.0", "V3.0" in app.title())
        # 模拟用户选好 3 张照片（绕过文件对话框），AI 关闭 → 纯手动
        app._paths = paths
        app._texts = None
        app._photo_cache.clear()
        app._result = None
        app._rebuild_text_inputs()
        check("生成前出现 3 个输入框", len(app._text_vars) == 3)
        check("生成按钮可点", str(app.generate_button.cget("state")) == "normal")
        app._start_build(texts=None, use_ai=False)

    def step2():
        check("生成完成（有结果）", app._result is not None)
        check("手动模式文案为空", list(app._texts) == ["", "", ""])
        check("画布已显示成图", app.image_canvas.original_image is not None)
        check("按钮恢复可用", str(app.rerender_button.cget("state")) == "normal"
              and str(app.save_button.cget("state")) == "normal")
        # 手动改第一句 → 重新渲染（不应调 AI）
        app._text_vars[0].set("手写的第一句")
        app.on_rerender()

    def step3():
        check("重新渲染完成", app._result is not None and app._texts[0] == "手写的第一句")
        check("重新渲染保留输入", app._text_vars[0].get() == "手写的第一句")
        # 布局联动：切到单张海报时隐藏竖排样式
        app.layout_var.set("单张海报")
        app._on_layout_changed()
        check("海报时隐藏竖排样式", app.style_frame.winfo_manager() == "")
        check("数量提示已更新", "1 张" in app.count_hint_label.cget("text"))
        app.layout_var.set("电影竖排")
        app._on_layout_changed()
        check("竖排时恢复竖排样式", app.style_frame.winfo_manager() == "grid")
        check("数量提示为 2–6", "2–6" in app.count_hint_label.cget("text"))
        # 画布交互：模拟缩放后不再处于适应模式
        app.image_canvas._zoom_at(100, 100, 1.5)
        check("缩放后退出适应模式", app.image_canvas.fit_mode is False)
        app.image_canvas.fit_to_window()
        check("双击适应恢复", app.image_canvas.fit_mode is True)
        app.destroy()

    # 生成 3 张 600×450 @2x 大约 1 秒内完成，留足余量
    app.after(400, step1)
    app.after(3000, step2)
    app.after(6000, step3)
    app.mainloop()

    print("=" * 40)
    if failures:
        print(f"自检失败 {len(failures)} 项：{failures}")
        return 1
    print("UI 自检全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
