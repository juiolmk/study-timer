# -*- coding: utf-8 -*-
"""Windows 全局快捷键：Ctrl+Alt+S 切换计时状态。

设计要点：
- 零第三方依赖，仅用 ``ctypes`` 调用 user32 的 ``RegisterHotKey`` / ``GetMessageW``。
- 热键注册与消息循环必须位于同一线程，因此后台线程持有全部 Win32 状态。
- 线程命中热键时只把事件写入 ``queue.Queue``；Tk 主线程通过 ``poll()`` 取事件，
  保证任何 Tk API 都只在主线程调用。
- 非 Windows 平台或热键被其他程序占用时静默降级：``start()`` 返回 False，不抛异常。
"""

from __future__ import annotations

import ctypes
import queue
import sys
import threading

try:  # 非 Windows 平台的 wintypes 定义可能不完整，缺失时按“不支持”处理
    from ctypes import wintypes
except Exception:  # pragma: no cover - 仅非 Windows 平台可能触发
    wintypes = None  # type: ignore[assignment]

#: 全局快捷键的展示文案，供 UI 引用，避免多处硬编码
HOTKEY_TEXT = "Ctrl+Alt+S"

# ---------------------------------------------------------------- Win32 常量
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_S = 0x53
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

#: 应用内唯一的热键 id
_HOTKEY_ID = 0xB001
#: 等待后台线程注册结果的上限（秒）
_START_TIMEOUT = 0.8
#: 回收后台线程的上限（秒）
_STOP_TIMEOUT = 0.5
#: 轮询间隔建议值（毫秒），由 UI 使用
POLL_INTERVAL_MS = 150

_api_ready = False
_api_lock = threading.Lock()


def _user32():
    """返回已配置 argtypes / restype 的 user32（仅 Windows 可调用）。"""
    global _api_ready
    user32 = ctypes.windll.user32
    with _api_lock:
        if not _api_ready:
            user32.RegisterHotKey.argtypes = [
                wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT,
            ]
            user32.RegisterHotKey.restype = wintypes.BOOL

            user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.UnregisterHotKey.restype = wintypes.BOOL

            user32.GetMessageW.argtypes = [
                ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                wintypes.UINT, wintypes.UINT,
            ]
            # 返回 0 表示 WM_QUIT，-1 表示出错，故用有符号 int
            user32.GetMessageW.restype = ctypes.c_int

            user32.PostThreadMessageW.argtypes = [
                wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            ]
            user32.PostThreadMessageW.restype = wintypes.BOOL

            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentThreadId.argtypes = []
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            _api_ready = True
    return user32


class HotkeyManager:
    """全局快捷键管理器（后台线程 + 消息队列）。

    典型用法::

        manager = HotkeyManager()
        if manager.start():
            ...  # Tk 主线程定时调用 manager.poll()
        manager.stop()

    线程安全约定：后台线程只写队列与内部状态（加锁），主线程只调用
    ``poll()`` / ``stop()``。
    """

    def __init__(self) -> None:
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._registered: bool = False
        self._running: bool = False
        # 后台线程用它通知主线程“注册已完成”
        self._register_event = threading.Event()
        # 停止意图：start() 清位，stop() 置位，用于关闭“注册进行中”的竞争窗口
        self._stop_requested = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 对外属性
    @property
    def is_running(self) -> bool:
        """后台线程是否仍在运行。"""
        return self._running

    @property
    def thread_id(self) -> int:
        """后台线程 id（0 表示尚未注册 / 已停止），用于测试注入消息。"""
        with self._lock:
            return self._thread_id

    # ------------------------------------------------------------ 生命周期
    def start(self) -> bool:
        """启动后台线程并注册 Ctrl+Alt+S，返回是否注册成功。

        - 已在运行时直接返回 True。
        - 非 Windows 平台返回 False。
        - 上一个后台线程尚未回收时返回 False（避免两个线程抢同一热键）。
        - 热键被占用或注册超时返回 False，且不抛异常。
        """
        with self._lock:
            if self._running:
                return True
            if sys.platform != "win32":
                return False

            previous = self._thread
            if previous is not None and previous.is_alive():
                # 上次 stop 未能在超时内回收线程，拒绝启动，等它自然退出
                return False

            self._stop_requested.clear()
            self._register_event.clear()
            self._registered = False
            self._thread_id = 0
            thread = threading.Thread(
                target=self._run, name="StudyTimerHotkey", daemon=True,
            )
            self._thread = thread
            self._running = True
            thread.start()

        # 等后台线程给出注册结果
        if not self._register_event.wait(_START_TIMEOUT):
            self.stop()
            return False

        with self._lock:
            registered = self._registered
            running = self._running
        if not registered:
            self.stop()
            return False
        return running

    def stop(self) -> None:
        """停止后台线程并注销热键；可重复调用，不会抛异常。

        先置位“停止意图”，让尚在注册中的线程放弃注册；再投递 WM_QUIT 唤醒
        消息循环。join 超时则保留线程引用、如实反映 ``is_running``，交由下次
        stop() 或线程自身的 finally 收尾，绝不在线程仍存活时假装已停止。
        """
        self._stop_requested.set()

        with self._lock:
            thread = self._thread
            thread_id = self._thread_id

        if thread_id:
            try:
                _user32().PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass

        stopped = True
        if thread is not None and thread.is_alive():
            thread.join(_STOP_TIMEOUT)
            stopped = not thread.is_alive()

        with self._lock:
            if stopped:
                self._thread = None
                self._thread_id = 0
                self._registered = False
                self._running = False
            else:
                # 线程仍未退出：保留引用以便下次重试，状态保持诚实
                self._thread = thread
                self._running = bool(thread is not None and thread.is_alive())

        if stopped:
            self._drain()

    # ------------------------------------------------------------ 主线程读取
    def poll(self) -> bool:
        """非阻塞排空队列：期间收到过热键事件则返回 True。"""
        fired = False
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
            fired = True
        return fired

    # ------------------------------------------------------------ 后台线程
    def _run(self) -> None:
        """后台线程主体：注册热键 + 消息循环（不触碰任何 Tk API）。

        在“写线程 id → 注册热键 → 进入消息循环”这三个关键点前后检查
        ``_stop_requested``，确保启动与停止竞争时不会残留持有热键的孤儿线程。
        """
        registered = False
        try:
            user32 = _user32()
            with self._lock:
                self._thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())

            if self._stop_requested.is_set():
                return  # 线程刚起来就被要求停止：不注册

            modifiers = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
            registered = bool(
                user32.RegisterHotKey(None, _HOTKEY_ID, modifiers, VK_S))
            with self._lock:
                self._registered = registered
            # 注册结果已可见，先唤醒 start() 再判断是否需要立刻回滚
            self._register_event.set()
            if not registered:
                return

            if self._stop_requested.is_set():
                # 已注册但停止请求已到：立即注销，避免热键被孤儿线程长期占用
                try:
                    user32.UnregisterHotKey(None, _HOTKEY_ID)
                except Exception:
                    pass
                with self._lock:
                    self._registered = False
                registered = False
                return

            msg = wintypes.MSG()
            while True:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break  # WM_QUIT 或出错
                if msg.message == WM_HOTKEY:
                    # 只写队列，真正的 UI 操作留给主线程
                    self._queue.put(int(msg.wParam))

            try:
                user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass
            with self._lock:
                self._registered = False
        except Exception:
            # 任何 Win32 异常都降级为非启用状态
            with self._lock:
                self._registered = False
        finally:
            self._register_event.set()
            with self._lock:
                self._registered = False
                self._running = False
                self._thread_id = 0

    # ------------------------------------------------------------ 内部工具
    def _drain(self) -> None:
        """丢弃残留事件，避免重新启用时误触发。"""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return
