# 打包为 Windows 可执行文件（未验证）

> ⚠️ 状态：**未验证**。本文档的命令按 PyInstaller 常规用法整理，尚未在真实环境跑通过。
> 打包前建议先用 `python main.py` 确认程序本身正常。

## 前置

```bash
pip install pyinstaller
```

## 推荐命令（onedir 模式）

```bat
pyinstaller --noconfirm --windowed --name PhotoMagic ^
  --collect-all customtkinter ^
  --add-data "fonts;fonts" ^
  --add-data "luts;luts" ^
  main.py
```

*   `--collect-all customtkinter`：customtkinter 运行时需要带出主题资源，缺了会报找不到文件。
*   `--add-data "fonts;fonts"` / `--add-data "luts;luts"`：把字体和滤镜一起打进去（Windows 分隔符是 `;`，macOS/Linux 用 `:`）。
*   产物在 `dist/PhotoMagic/`，入口 `dist/PhotoMagic/PhotoMagic.exe`。

## 为什么推荐 onedir 而不是 onefile（--onefile）

onefile 模式每次启动把资源解压到**临时目录**，程序里的 `config.APP_DIR`
（`settings.json`、`app.log` 的落盘位置）会指向那个临时目录——退出即被清理，
导致设置不记忆、日志丢失。若坚持 onefile，需要先把 `APP_DIR` 迁移到
`%APPDATA%/PhotoMagic` 之类的持久目录（改 `config.py`），本文档不展开。

## 公开分发前的两个提醒

1.  `fonts/手写体.ttf` 来源不明，分发前请确认字体授权允许再分发。
2.  确认 `.env` 没有被打进包（默认不会，但别手动 `--add-data .env`）。
