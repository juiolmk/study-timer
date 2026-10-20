# -*- coding: utf-8 -*-
"""单实例守护的单元测试。

测试必须使用唯一互斥量名（uuid），否则会与真实运行的 App 抢同一把锁，
导致测试互相干扰或在开发机上误判。
"""

import sys
import unittest
import uuid
from unittest import mock

from study_timer.single_instance import SingleInstance


class SingleInstanceTest(unittest.TestCase):
    def setUp(self):
        # 每次用全新名字：Local\ 前缀 + uuid，绝不与真实 App 的锁冲突
        self.name = "Local\\StudyTimer_Test_" + uuid.uuid4().hex
        self._guards = []

    def tearDown(self):
        for guard in self._guards:
            guard.release()

    def _guard(self):
        guard = SingleInstance(self.name)
        self._guards.append(guard)
        return guard

    def test_second_acquire_rejected_then_release_allows(self):
        first = self._guard()
        self.assertTrue(first.acquire())
        self.assertTrue(first.is_acquired)

        second = self._guard()
        self.assertFalse(second.acquire())
        self.assertFalse(second.is_acquired)

        first.release()
        self.assertTrue(second.acquire())
        self.assertTrue(second.is_acquired)

    def test_release_is_idempotent(self):
        guard = self._guard()
        self.assertTrue(guard.acquire())
        guard.release()
        guard.release()  # 重复释放不应抛异常
        self.assertFalse(guard.is_acquired)
        # 释放后可再次获取
        self.assertTrue(guard.acquire())

    def test_acquire_twice_same_object_is_true(self):
        guard = self._guard()
        self.assertTrue(guard.acquire())
        self.assertTrue(guard.acquire())

    def test_custom_name_isolated(self):
        other_name = "Local\\StudyTimer_Test_" + uuid.uuid4().hex
        first = self._guard()
        first.acquire()
        other = SingleInstance(other_name)
        self._guards.append(other)
        self.assertTrue(other.acquire())  # 不同名字互不影响

    def test_non_windows_always_acquires(self):
        with mock.patch("study_timer.single_instance.sys.platform", "linux"):
            guard = SingleInstance(self.name)
            self._guards.append(guard)
            self.assertTrue(guard.acquire())
            guard.release()  # 非 Windows 下 release 是空操作


if __name__ == "__main__":
    unittest.main()
