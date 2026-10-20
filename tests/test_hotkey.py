# -*- coding: utf-8 -*-
"""全局快捷键管理器测试（仅 Windows）。

不创建任何 GUI；注册失败（热键被占用）按 skip 处理，不算失败。
"""

import ctypes
import sys
import time
import unittest

from study_timer.hotkey import HOTKEY_TEXT, WM_HOTKEY, HotkeyManager


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

            # 向后台线程的消息循环投递一条 WM_HOTKEY，模拟按下快捷键
            posted = ctypes.windll.user32.PostThreadMessageW(
                thread_id, WM_HOTKEY, 1, 0)
            self.assertTrue(posted, "PostThreadMessageW 应当成功")

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


if __name__ == "__main__":
    unittest.main()
