# -*- coding: utf-8 -*-
"""学习打卡（StudyTimer）程序入口。

开发运行：
    python app.py

打包为单文件 exe：
    pyinstaller --onefile --windowed --name 学习打卡 \
        --icon assets/study_timer.ico --version-file version_info.txt \
        --add-data "assets/study_timer.ico;assets" \
        --collect-submodules study_timer app.py
"""

from study_timer.ui.app import run

if __name__ == "__main__":
    run()
