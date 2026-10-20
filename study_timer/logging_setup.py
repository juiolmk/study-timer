# -*- coding: utf-8 -*-
"""日志配置与全局异常钩子。

设计要点：
- 只用标准库：``logging`` + ``RotatingFileHandler``，不引入第三方依赖。
- ``setup_logging()`` 幂等：重复调用不会叠加 handler，只更新已有 handler 的级别。
- 日志文件固定轮转：单文件 1MB，保留 3 份历史，总量可控。
- 无法创建日志文件时降级为控制台输出，绝不影响应用启动。
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

from .config import LOG_DIR

#: 日志行格式：时间 级别 模块名: 消息
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

#: 单个日志文件上限（字节）
MAX_BYTES = 1_000_000
#: 保留的历史日志份数
BACKUP_COUNT = 3
#: 默认日志文件名
DEFAULT_FILENAME = "app.log"

#: 标记本项目 handler 的私有属性名，用于幂等判断与测试清理
HANDLER_MARK = "_study_timer_handler"

#: 应用自身的根 logger 名称，模块级 logger 均挂在其下
ROOT_LOGGER_NAME = "study_timer"

_state_lock = threading.Lock()
#: 最近一次配置的日志文件绝对路径（供 UI / 诊断使用）
_log_path: str = os.path.join(LOG_DIR, DEFAULT_FILENAME)
_hooks_installed = False


def get_log_path() -> str:
    """返回当前日志文件的绝对路径。"""
    return _log_path


def setup_logging(level: int = logging.INFO, log_dir: str | None = None,
                  filename: str = DEFAULT_FILENAME) -> str:
    """配置根日志输出，返回日志文件路径。

    幂等：若本项目的 handler 已存在，则只同步级别，不重复添加。

    Args:
        level: 日志级别，默认 ``logging.INFO``。
        log_dir: 日志目录；``None`` 表示使用 :data:`study_timer.config.LOG_DIR`。
        filename: 日志文件名。

    Returns:
        日志文件的绝对路径（降级为控制台输出时仍返回预期路径）。
    """
    global _log_path

    target_dir = log_dir or LOG_DIR
    path = os.path.abspath(os.path.join(target_dir, filename))

    root = logging.getLogger()
    with _state_lock:
        _log_path = path

        for handler in list(root.handlers):
            if getattr(handler, HANDLER_MARK, False):
                handler.setLevel(level)
                root.setLevel(level)
                return path

        formatter = logging.Formatter(LOG_FORMAT)
        handler: logging.Handler
        try:
            os.makedirs(target_dir, exist_ok=True)
            handler = RotatingFileHandler(
                path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        except OSError as exc:  # 目录不可写等极端情况：降级为控制台
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            setattr(handler, HANDLER_MARK, True)
            root.addHandler(handler)
            root.setLevel(level)
            logging.getLogger(ROOT_LOGGER_NAME).warning(
                "无法创建日志文件 %s，已降级为控制台输出：%s", path, exc)
            return path

        handler.setFormatter(formatter)
        handler.setLevel(level)
        setattr(handler, HANDLER_MARK, True)
        root.addHandler(handler)
        root.setLevel(level)

    return path


def install_exception_hooks() -> None:
    """接管主线程 / 子线程的未捕获异常，统一写入日志。

    重复调用是安全的（只安装一次）。
    """
    global _hooks_installed
    with _state_lock:
        if _hooks_installed:
            return
        _hooks_installed = True

    sys.excepthook = _handle_uncaught_exception
    if hasattr(threading, "excepthook"):  # Python 3.8+
        threading.excepthook = _handle_thread_exception


def _handle_uncaught_exception(exc_type, exc_value, exc_tb) -> None:
    """``sys.excepthook``：记录 CRITICAL + traceback。"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 尊重 Ctrl+C 的默认行为，不写入日志噪音
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.getLogger(ROOT_LOGGER_NAME).critical(
        "未捕获异常", exc_info=(exc_type, exc_value, exc_tb))


def _handle_thread_exception(args) -> None:
    """``threading.excepthook``：记录后台线程（如热键线程）异常。"""
    if issubclass(args.exc_type, SystemExit):
        return
    thread_name = getattr(getattr(args, "thread", None), "name", "unknown")
    logging.getLogger(ROOT_LOGGER_NAME).critical(
        "线程 %s 未捕获异常", thread_name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
