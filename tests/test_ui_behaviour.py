# -*- coding: utf-8 -*-
"""界面行为回归测试：热键免询问、记录分页保留。

- 热键用例用轻量假对象直接驱动 ``App._on_hotkey``，不需要真的 Tk 窗口与热键。
- 分页用例需要 Tk；无可用 GUI 环境时自动跳过（不伪造通过）。
"""

import contextlib
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from tkinter import messagebox
from unittest import mock

import study_timer.ui.app as ui_app
from study_timer.models import Record, Store
from study_timer.storage import Repository
from study_timer.ui.pages.records import PAGE_SIZE


# ---------------------------------------------------------------- 假对象
class _FakeRoot:
    """模拟 Tk root：无模态窗口。"""

    def grab_current(self):
        return None


class _FakeTimer:
    def __init__(self, idle=True, running=False):
        self.is_idle = idle
        self.is_running = running


class _FakeHome:
    """记录 toggle 的 prompt 参数。"""

    def __init__(self):
        self.calls = []

    def toggle(self, prompt=True):
        self.calls.append(prompt)


class _FakeApp:
    def __init__(self, timer, home):
        self.root = _FakeRoot()
        self.timer = timer
        self.pages = {"home": home}
        self.current_key = "home"
        self.toasts = []

    def toast(self, message, duration_ms=1600):
        self.toasts.append(message)


class HotkeyPromptTest(unittest.TestCase):
    """Ctrl+Alt+S 必须即时开始，不弹“这次学什么”。"""

    def test_hotkey_idle_starts_without_prompt(self):
        home = _FakeHome()
        app = _FakeApp(_FakeTimer(idle=True, running=False), home)
        ui_app.App._on_hotkey(app)
        self.assertEqual(home.calls, [False])
        self.assertEqual(app.toasts, ["已开始专注"])

    def test_hotkey_running_pauses_without_prompt(self):
        home = _FakeHome()
        app = _FakeApp(_FakeTimer(idle=False, running=True), home)
        ui_app.App._on_hotkey(app)
        self.assertEqual(home.calls, [False])
        self.assertEqual(app.toasts, ["已暂停"])

    def test_hotkey_paused_resumes_without_prompt(self):
        home = _FakeHome()
        app = _FakeApp(_FakeTimer(idle=False, running=False), home)
        ui_app.App._on_hotkey(app)
        self.assertEqual(home.calls, [False])
        self.assertEqual(app.toasts, ["继续专注"])

    def test_hotkey_ignored_when_modal_open(self):
        home = _FakeHome()
        app = _FakeApp(_FakeTimer(idle=True, running=False), home)
        app.root.grab_current = lambda: object()  # 有模态弹窗
        ui_app.App._on_hotkey(app)
        self.assertEqual(home.calls, [])

    def test_space_keeps_inline_semantics(self):
        """空格键沿用既有实现（prompt=False），本次不改其行为。"""
        home = _FakeHome()
        app = _FakeApp(_FakeTimer(idle=True, running=False), home)
        app.root.focus_get = lambda: None
        ui_app.App._on_space(app, None)
        self.assertEqual(home.calls, [False])


# ---------------------------------------------------------------- 分页
def _build_store(count):
    store = Store()
    for i in range(count):
        day = f"2026-{1 + (i // 28) % 12:02d}-{1 + i % 28:02d}"
        store.records.append(Record(
            id=f"r{i}", date=day,
            start=f"{day} 09:{i % 60:02d}", end=f"{day} 10:{i % 60:02d}",
            duration_min=25, title=f"学习内容 {i}",
            tag=["数学", "英语", "编程", ""][i % 4], note="",
        ))
        store.checkins.add(day)
    return store


def _tk_available():
    try:
        root = tk.Tk()
    except Exception:
        return False
    try:
        root.withdraw()
        root.update_idletasks()
    finally:
        root.destroy()
    return True


TK_AVAILABLE = _tk_available()


class _StubHotkey:
    """避免测试真的注册 Ctrl+Alt+S。"""

    def __init__(self, *args, **kwargs):
        self.is_running = False

    def start(self):
        return False

    def stop(self):
        pass

    def poll(self):
        return False


@unittest.skipUnless(TK_AVAILABLE, "无可用 GUI 环境（Tk 初始化失败）")
class RecordsPaginationTest(unittest.TestCase):
    TOTAL = 120

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        data_file = os.path.join(self.tmpdir, "study_data.json")
        backup_file = os.path.join(self.tmpdir, "study_data.bak.json")
        self.repo = Repository(data_file, backup_file)
        self.repo.save(_build_store(self.TOTAL))

        self._stack = contextlib.ExitStack()
        self._stack.enter_context(
            mock.patch.object(ui_app, "Repository", lambda: self.repo))
        self._stack.enter_context(
            mock.patch.object(ui_app, "HotkeyManager", _StubHotkey))

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = ui_app.App(self.root)
        self.root.update()
        self.app.show_page("records")
        self.root.update()
        self.page = self.app.pages["records"]

    def tearDown(self):
        self.app._alive = False
        try:
            self.app.hotkey.stop()
        except Exception:
            pass
        try:
            # 取消 App 排下的 after 回调，避免销毁后 Tcl 打印 invalid command name
            for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
                self.root.tk.call("after", "cancel", job)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        self._stack.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- 辅助 ----------
    def _rows(self):
        return len(self.page.list.inner.winfo_children())

    # ---------- 用例 ----------
    def test_initial_page_is_one_screen(self):
        self.assertEqual(self.page._limit, PAGE_SIZE)
        self.assertEqual(self._rows(), PAGE_SIZE + 1)  # 50 行 + 页脚
        self.assertEqual(self.page.count_label.cget("text"), f"共 {self.TOTAL} 条")

    def test_load_more_appends_without_rebuild(self):
        first_card = self.page.list.inner.winfo_children()[0]
        self.page._load_more()
        self.root.update()

        self.assertEqual(self.page._limit, PAGE_SIZE * 2)
        self.assertTrue(first_card.winfo_exists(), "已渲染的行不应被销毁重建")
        self.assertEqual(self._rows(), PAGE_SIZE * 2 + 1)

    def test_load_more_twice_reaches_total(self):
        self.page._load_more()
        self.page._load_more()
        self.root.update()
        self.assertEqual(self.page._limit, self.TOTAL)
        self.assertEqual(self._rows(), self.TOTAL + 1)

        self.page._load_more()  # 已到底：不追加
        self.assertEqual(self.page._limit, self.TOTAL)
        self.assertEqual(self._rows(), self.TOTAL + 1)

    def test_delete_keeps_loaded_page(self):
        self.page._load_more()
        self.root.update()
        self.assertEqual(self.page._limit, PAGE_SIZE * 2)

        before = len(self.app.store.records)
        with mock.patch.object(messagebox, "askyesno", lambda *a, **k: True):
            self.page._delete(self.page.rec_filtered[0])
        self.root.update()

        self.assertEqual(len(self.app.store.records), before - 1)
        self.assertEqual(self.page._limit, PAGE_SIZE * 2, "删除后不应回落到首屏")
        self.assertEqual(self._rows(), PAGE_SIZE * 2 + 1)

    def test_search_resets_to_first_page(self):
        self.page._load_more()
        self.root.update()

        self.page.search_var.set("学习内容 11")
        self.page.refresh(reset_limit=True)  # 与 KeyRelease 绑定的调用一致
        self.root.update()

        expected = len([r for r in self.app.store.records if "学习内容 11" in r.title])
        self.assertEqual(len(self.page.rec_filtered), expected)
        self.assertEqual(self.page._limit, PAGE_SIZE)

    def test_switch_page_resets_to_first_page(self):
        self.page._load_more()
        self.app.show_page("stats")
        self.app.show_page("records")
        self.root.update()
        self.assertEqual(self.page._limit, PAGE_SIZE)

    def test_limit_clamped_when_result_shrinks(self):
        self.page._load_more()
        self.page.search_var.set("学习内容 119")
        self.page.refresh()  # 不重置，但仍需夹到结果总数
        self.root.update()
        self.assertEqual(len(self.page.rec_filtered), 1)
        self.assertEqual(self.page._limit, 1)
        self.assertEqual(self._rows(), 2)  # 1 行 + 页脚


if __name__ == "__main__":
    unittest.main()
