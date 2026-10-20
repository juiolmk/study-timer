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


class LoggingSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = logging.getLogger()
        self._original_excepthook = sys.excepthook
        self._original_thread_hook = threading.excepthook
        # 从干净状态开始：移除其他模块可能安装的 handler
        self._remove_marked_handlers()
        self.path = logging_setup.setup_logging(log_dir=self.tmpdir)

    def tearDown(self):
        sys.excepthook = self._original_excepthook
        threading.excepthook = self._original_thread_hook
        logging_setup._hooks_installed = False
        self._remove_marked_handlers()
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


if __name__ == "__main__":
    unittest.main()
