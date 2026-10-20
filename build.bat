@echo off
REM 学习打卡 - 一键打包为 exe（需本机已安装 Python 3.10+）
REM 双击本文件即可生成 dist\学习打卡.exe
cd /d "%~dp0"

IF NOT EXIST app.py (
  echo 未找到 app.py，请将本文件与 app.py 放在同一目录。
  pause
  exit /b
)

IF NOT EXIST .venv (
  python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyinstaller

python -m compileall -q study_timer app.py
python -m PyInstaller --onefile --windowed --name 学习打卡 --collect-submodules study_timer app.py --noconfirm --clean

echo.
echo 打包完成！exe 位于 dist\学习打卡.exe
pause
