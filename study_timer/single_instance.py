# -*- coding: utf-8 -*-
"""单实例保护：Windows 命名互斥量（mutex）。

- 零第三方依赖，只用 ``ctypes`` 调用 kernel32 的 ``CreateMutexW`` / ``CloseHandle``。
- 互斥量名为 ``Local\\StudyTimer_SingleInstance``：作用域限于当前登录会话，
  不同用户（含远程桌面会话）互不干扰。
- 非 Windows 平台（或 API 不可用）恒返回 True，保证应用总能启动。
"""

from __future__ import annotations

import ctypes
import logging
import sys

#: 默认互斥量名（``Local\\`` 前缀 = 当前会话作用域）
MUTEX_NAME = "Local\\StudyTimer_SingleInstance"

#: CreateMutexW 在“同名对象已存在”时写入的错误码
ERROR_ALREADY_EXISTS = 183

logger = logging.getLogger(__name__)

# 延迟初始化并缓存 kernel32，避免每次调用都重设 argtypes
_kernel32 = None


def _get_kernel32():
    """返回已配置 argtypes / restype 的 kernel32（仅 Windows 可调用）。"""
    global _kernel32
    if _kernel32 is not None:
        return _kernel32

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,      # LPSECURITY_ATTRIBUTES
        ctypes.c_bool,        # BOOL bInitialOwner
        ctypes.c_wchar_p,     # LPCWSTR lpName
    ]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    _kernel32 = kernel32
    return kernel32


class SingleInstance:
    """基于命名互斥量的单实例守卫。

    典型用法::

        guard = SingleInstance()
        if not guard.acquire():
            ...  # 已有实例，提示后退出
        try:
            main()
        finally:
            guard.release()
    """

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.name = name
        self._handle: int | None = None

    @property
    def is_acquired(self) -> bool:
        """当前对象是否持有互斥量句柄。"""
        return self._handle is not None

    def acquire(self) -> bool:
        """尝试获取实例锁。

        Returns:
            True 表示拿到锁（可以继续启动）；False 表示已有实例在运行。
            非 Windows 平台恒为 True。
        """
        if sys.platform != "win32":
            return True
        if self._handle is not None:
            return True

        try:
            kernel32 = _get_kernel32()
            handle = kernel32.CreateMutexW(None, False, self.name)
            # 必须在任何其他 Win32 调用之前读取错误码
            last_error = ctypes.get_last_error()
        except Exception:
            # 守卫自身出错不应阻止应用启动
            logger.warning("创建单实例互斥量失败，跳过检查", exc_info=True)
            return True

        if not handle:
            logger.warning("创建单实例互斥量失败：句柄为空（错误码 %s）", last_error)
            return True

        if last_error == ERROR_ALREADY_EXISTS:
            try:
                kernel32.CloseHandle(ctypes.c_void_p(handle))
            except Exception:
                logger.warning("关闭重复互斥量句柄失败", exc_info=True)
            logger.info("检测到已有实例持有互斥量 %s", self.name)
            return False

        self._handle = int(handle)
        return True

    def release(self) -> None:
        """释放互斥量句柄；可重复调用，不会抛异常。"""
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            _get_kernel32().CloseHandle(ctypes.c_void_p(handle))
        except Exception:
            logger.warning("释放单实例互斥量失败", exc_info=True)
