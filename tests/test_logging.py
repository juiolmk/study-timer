# -*- coding: utf-8 -*-
"""日志配置的单元测试（文件落地、幂等、异常钩子）。

所有测试都用临时目录，并在结束时移除自己添加的 handler、恢复被接管的
钩子，避免污染其他测试。
"""

import logging
import os
import shutil
import sys
import tempfile
import threading
import unittest

from study_timer import logging_setup

#: 套件启动时的全局状态基线，供最后一个用例做“无污染”回归断言
_BASELINE_ROOT_LEVEL = logging.getLogger().level
_BASELINE_LOG_PATH = logging_setup._log_path
_BASELINE_HOOKS_INSTALLED = logging_setup._hooks_installed
_BASELINE_EXCEPTHOOK = sys.excepthook
_BASELINE_THREAD_HOOK = threading.excepthook


class LoggingSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = logging.getLogger()
        # 记录全部将被改写的全局状态，tearDown 完整还原
        self._original_level = self.root.level
        self._original_excepthook = sys.excepthook
        self._original_thread_hook = threading.excepthook
        self._original_hooks_installed = logging_setup._hooks_installed
        self._original_log_path = logging_setup._log_path
        # 从干净状态开始：移除其他模块可能安装的 handler
        self._remove_marked_handlers()
        self.path = logging_setup.setup_logging(log_dir=self.tmpdir)

    def tearDown(self):
        self._remove_marked_handlers()
        sys.excepthook = self._original_excepthook
        threading.excepthook = self._original_thread_hook
        logging_setup._hooks_installed = self._original_hooks_installed
        logging_setup._log_path = self._original_log_path
        self.root.setLevel(self._original_level)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- 辅助 ----------
    def _marked_handlers(self):
        return [h for h in self.root.handlers
                if getattr(h, logging_setup.HANDLER_MARK, False)]

    def _remove_marked_handlers(self):
        for handler in self._marked_handlers():
            self.root.removeHandler(handler)
            handler.close()

    def _flush(self):
        for handler in self._marked_handlers():
            handler.flush()

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as fh:
            return fh.read()

    # ---------- 用例 ----------
    def test_log_file_created_and_receives_record(self):
        self.assertTrue(os.path.exists(self.path))

        logging.getLogger("study_timer.test").error("测试写入的一条错误")
        self._flush()

        content = self._read()
        self.assertIn("测试写入的一条错误", content)
        self.assertIn("ERROR", content)
        self.assertIn("study_timer.test", content)

    def test_setup_is_idempotent(self):
        logging_setup.setup_logging(log_dir=self.tmpdir)
        logging_setup.setup_logging(log_dir=self.tmpdir)
        self.assertEqual(len(self._marked_handlers()), 1)

    def test_rotating_handler_limits_size(self):
        handler = self._marked_handlers()[0]
        self.assertEqual(getattr(handler, "maxBytes", None), logging_setup.MAX_BYTES)
        self.assertEqual(getattr(handler, "backupCount", None), logging_setup.BACKUP_COUNT)

    def test_exception_hook_writes_traceback(self):
        logging_setup.install_exception_hooks()

        try:
            raise ValueError("故意触发的未捕获异常")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        self._flush()

        content = self._read()
        self.assertIn("CRITICAL", content)
        self.assertIn("Traceback", content)
        self.assertIn("故意触发的未捕获异常", content)

    def test_thread_exception_hook_writes_traceback(self):
        logging_setup.install_exception_hooks()

        try:
            raise RuntimeError("线程内异常")
        except RuntimeError:
            args = threading.ExceptHookArgs(
                (*sys.exc_info(), threading.current_thread()))
            threading.excepthook(args)
        self._flush()

        content = self._read()
        self.assertIn("CRITICAL", content)
        self.assertIn("线程内异常", content)
        self.assertEqual(threading.excepthook, logging_setup._handle_thread_exception)

    def test_zz_global_state_untouched_within_case(self):
        """本用例自身也不该留下残余 handler（跨用例由 ZGlobalStateTest 兜底）。"""
        logging_setup.install_exception_hooks()
        logging.getLogger("study_timer.test").warning("一条警告")
        self._flush()
        self.assertEqual(len(self._marked_handlers()), 1)


class ZGlobalStateTest(unittest.TestCase):
    """排在最后（类名 Z 开头）：验证整套用例跑完没有污染全局日志状态。"""

    def test_global_state_restored_after_suite(self):
        self.assertEqual(logging.getLogger().level, _BASELINE_ROOT_LEVEL)
        self.assertEqual(logging_setup._log_path, _BASELINE_LOG_PATH)
        self.assertEqual(logging_setup._hooks_installed, _BASELINE_HOOKS_INSTALLED)
        self.assertEqual(sys.excepthook, _BASELINE_EXCEPTHOOK)
        self.assertEqual(threading.excepthook, _BASELINE_THREAD_HOOK)
        # _log_path 必须指回真实日志目录，而不是已删除的临时目录
        self.assertEqual(os.path.dirname(logging_setup._log_path),
                         os.path.dirname(_BASELINE_LOG_PATH))
        self.assertEqual(
            [h for h in logging.getLogger().handlers
             if getattr(h, logging_setup.HANDLER_MARK, False)], [])


if __name__ == "__main__":
    unittest.main()
