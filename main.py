# file: main.py —— 程序入口（仅负责启动 UI，不含业务逻辑）
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 电影感照片生成器 V3.0")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="冒烟测试：创建窗口 1 秒后自动销毁，用于无人值守验证（退出码 0 即通过）",
    )
    args = parser.parse_args()

    import config

    config.setup_logging()

    from app_ui import PhotoBoothApp

    app = PhotoBoothApp()
    if args.smoke_test:
        app.title("电影感照片生成器 V3.0 - 冒烟测试")
        app.after(1000, app.destroy)  # 1 秒后自动销毁窗口
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
