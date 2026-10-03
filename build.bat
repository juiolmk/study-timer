@echo off
REM 学习打卡 - 一键打包为 exe（需本机已安装 Python 3.10+）
REM 双击本文件即可生成 学习打卡.exe（位于 dist 目录）
cd /d "%~dp0"
IF NOT EXIST app.py (
  echo 未找到 app.py，请将本文件与 app.py 放在同一目录。
  pause
  exit /b
)
python -m venv .venv >nul 2>&1
call .venv\Scripts\activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyinstaller
python -m pyinstaller --onefile --windowed --name 学习打卡 app.py
echo.
echo 打包完成！exe 位于 dist\学习打卡.exe
pause
