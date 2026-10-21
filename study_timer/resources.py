# -*- coding: utf-8 -*-
"""静态资源定位：源码运行与 PyInstaller 打包后共用同一套路径规则。

``--onefile`` 打包后，数据文件被解包到 ``sys._MEIPASS`` 指向的临时目录，
此时不能再用 ``__file__`` 推算项目根目录；源码运行时则回退到项目根。
"""

from __future__ import annotations

import sys
from pathlib import Path

#: 源码运行时的项目根目录（``study_timer/resources.py`` 的上两级）
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def _base_dir() -> Path:
    """打包后返回 ``sys._MEIPASS``，源码运行返回项目根目录。"""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return PROJECT_ROOT


def resource_path(relative: str) -> str:
    """把相对资源路径解析成绝对路径字符串。

    Args:
        relative: 相对项目根目录的路径，例如 ``"assets/study_timer.ico"``。
            允许使用反斜杠分隔符，首尾多余的 ``/`` 会被忽略。

    Returns:
        绝对路径字符串。不保证文件存在，缺失由调用方降级处理。
    """
    cleaned = str(relative or "").replace("\\", "/").strip("/")
    base = _base_dir()
    if not cleaned:
        return str(base)
    return str(base / cleaned)


def resource_exists(relative: str) -> bool:
    """资源是否存在（打包后与源码运行语义一致）。"""
    return Path(resource_path(relative)).is_file()
