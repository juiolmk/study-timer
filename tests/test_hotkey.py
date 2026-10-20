# -*- coding: utf-8 -*-
"""全局快捷键管理器测试（仅 Windows）。

不创建任何 GUI；注册失败（热键被占用）按 skip 处理，不算失败。
"""

import ctypes
import sys
import time
import unittest

from study_timer.hotkey import HOTKEY_TEXT, WM_HOTKEY, HotkeyManager


def _post_hotkey(thread_id: int) -> bool:
    """向指定线程的消息队列投递一条 WM_HOTKEY，模拟按下快捷键。"""
    return bool(ctypes.windll.user32.PostThreadMessageW(thread_id, WM_HOTKEY, 1, 0))


@unittest.skipUnless(sys.platform == "win32", "全局快捷键仅支持 Windows")
class HotkeyManagerTest(unittest.TestCase):
    """HotkeyManager 生命周期与事件队列。"""

    def test_start_poll_stop(self):
        self.assertEqual(HOTKEY_TEXT, "Ctrl+Alt+S")
        manager = HotkeyManager()
        try:
            if not manager.start():
                self.skipTest("hotkey occupied")

            self.assertTrue(manager.is_running)
            thread_id = manager.thread_id
            self.assertTrue(thread_id, "后台线程应已启动")

            # 初始状态下没有待处理事件
            self.assertFalse(manager.poll())
            self.assertTrue(_post_hotkey(thread_id), "PostThreadMessageW 应当成功")

            deadline = time.monotonic() + 1.0
            fired = False
            while time.monotonic() < deadline:
                if manager.poll():
                    fired = True
                    break
                time.sleep(0.01)
            self.assertTrue(fired, "1 秒内应收到热键事件")
        finally:
            manager.stop()

        self.assertFalse(manager.is_running)
        # 可重复 stop，且不抛异常
        manager.stop()
        self.assertFalse(manager.is_running)

    def test_start_twice_same_thread(self):
        """重复 start 应幂等：返回 True 且复用同一个后台线程。"""
        manager = HotkeyManager()
        try:
            if not manager.start():
                self.skipTest("hotkey occupied")
            first_id = manager.thread_id
            self.assertTrue(manager.start(), "已在运行时 start 应返回 True")
            self.assertEqual(manager.thread_id, first_id, "不应创建第二个线程")
            self.assertTrue(manager.is_running)
        finally:
            manager.stop()
        self.assertFalse(manager.is_running)

    def test_restart_after_stop(self):
        """stop 后可以再次 start，且使用新的后台线程。"""
        manager = HotkeyManager()
        try:
            if not manager.start():
                self.skipTest("hotkey occupied")
            first_id = manager.thread_id

            manager.stop()
            self.assertFalse(manager.is_running)
            self.assertEqual(manager.thread_id, 0)

            if not manager.start():
                self.skipTest("hotkey occupied after restart")
            self.assertTrue(manager.is_running)
            self.assertNotEqual(manager.thread_id, 0)
            self.assertNotEqual(manager.thread_id, first_id, "重启应新建后台线程")
        finally:
            manager.stop()
        self.assertFalse(manager.is_running)

    def test_double_stop(self):
        """连续多次 stop 不抛异常，状态始终为已停止。"""
        manager = HotkeyManager()
        if not manager.start():
            self.skipTest("hotkey occupied")

        manager.stop()
        manager.stop()
        manager.stop()
        self.assertFalse(manager.is_running)
        self.assertEqual(manager.thread_id, 0)

    def test_poll_drains(self):
        """一次 poll 会排空队列：两条事件只报告一次 True。"""
        manager = HotkeyManager()
        try:
            if not manager.start():
                self.skipTest("hotkey occupied")

            thread_id = manager.thread_id
            self.assertTrue(_post_hotkey(thread_id))
            self.assertTrue(_post_hotkey(thread_id))

            deadline = time.monotonic() + 1.0
            first = False
            while time.monotonic() < deadline:
                if manager.poll():
                    first = True
                    break
                time.sleep(0.01)
            self.assertTrue(first, "首次 poll 应报告收到事件")
            self.assertFalse(manager.poll(), "队列应已被排空")
        finally:
            manager.stop()

    def test_occupied_returns_false(self):
        """热键被占用时 start 返回 False，且不抛异常、不残留线程。"""
        first = HotkeyManager()
        second = HotkeyManager()
        try:
            if not first.start():
                self.skipTest("hotkey occupied before test")

            self.assertFalse(second.start(), "热键已被占用时 start 应返回 False")
            self.assertFalse(second.is_running)
            self.assertEqual(second.thread_id, 0)
            # 被占用方不应影响占用方
            self.assertTrue(first.is_running)
            self.assertFalse(first.poll())
        finally:
            second.stop()
            first.stop()

        self.assertFalse(first.is_running)
        self.assertFalse(second.is_running)


if __name__ == "__main__":
    unittest.main()
