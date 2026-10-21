# -*- coding: utf-8 -*-
"""界面行为回归测试：热键免询问、记录分页保留、设置文案、图标降级。

- 热键用例用轻量假对象直接驱动 ``App._on_hotkey``，不需要真的 Tk 窗口与热键。
- 其余用例需要真实 Tk 窗口；无可用 GUI 环境时自动跳过（不伪造通过）。
"""

import contextlib
import os
import shutil
import tempfile
import tkinter as tk
import types
import unittest
from pathlib import Path
from tkinter import messagebox
from unittest import mock

import study_timer.ui.app as ui_app
from study_timer.models import Record, Store
from study_timer.resources import resource_path as project_resource_path
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
class _TkAppFixture(unittest.TestCase):
    """真实 Tk + 临时数据目录的 App 夹具（子类只加自己的断言）。"""

    #: 预置记录条数；轻量用例可改小以缩短初始化时间
    RECORDS = 0

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        data_file = os.path.join(self.tmpdir, "study_data.json")
        backup_file = os.path.join(self.tmpdir, "study_data.bak.json")
        self.repo = Repository(data_file, backup_file)
        self.repo.save(_build_store(self.RECORDS))

        self._stack = contextlib.ExitStack()
        self._stack.enter_context(
            mock.patch.object(ui_app, "Repository", lambda: self.repo))
        self._stack.enter_context(
            mock.patch.object(ui_app, "HotkeyManager", _StubHotkey))

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = ui_app.App(self.root)
        self.root.update()

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


class RecordsPaginationTest(_TkAppFixture):
    TOTAL = 120
    RECORDS = 120

    def setUp(self):
        super().setUp()
        self.app.show_page("records")
        self.root.update()
        self.page = self.app.pages["records"]

    # ---------- 辅助 ----------
    def _rows(self):
        return len(self.page._rows)

    # ---------- 用例 ----------
    def test_initial_page_is_one_screen(self):
        self.assertEqual(self.page._limit, PAGE_SIZE)
        self.assertEqual(self._rows(), PAGE_SIZE)
        self.assertIsNotNone(self.page._footer_box)
        self.assertIn("加载更多", self.page._footer_text)
        self.assertEqual(self.page.count_label.cget("text"), f"共 {self.TOTAL} 条")

    def test_load_more_extends_visible_rows(self):
        self.page._load_more()
        self.root.update()

        self.assertEqual(self.page._limit, PAGE_SIZE * 2)
        self.assertEqual(self._rows(), PAGE_SIZE * 2)
        self.assertIsNotNone(self.page._footer_box)

    def test_load_more_twice_reaches_total(self):
        self.page._load_more()
        self.page._load_more()
        self.root.update()
        self.assertEqual(self.page._limit, self.TOTAL)
        self.assertEqual(self._rows(), self.TOTAL)
        self.assertIsNone(self.page._footer_box)
        self.assertIn("已显示全部", self.page._footer_text)

        self.page._load_more()  # 已到底：不追加
        self.assertEqual(self.page._limit, self.TOTAL)
        self.assertEqual(self._rows(), self.TOTAL)

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
        self.assertEqual(self._rows(), PAGE_SIZE * 2)
        self.assertEqual(self.page.count_label.cget("text"), f"共 {before - 1} 条")

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
        self.assertEqual(self._rows(), 1)
        self.assertIsNone(self.page._footer_box)
        self.assertIn("已显示全部", self.page._footer_text)

    def test_edit_hitbox_opens_dialog(self):
        row = self.page._rows[0]
        box = row["edit"]
        calls = []
        self.app.open_record_dialog = lambda record=None: calls.append(record)

        self.page._on_click(types.SimpleNamespace(
            x=int((box[0] + box[2]) / 2),
            y=int((box[1] + box[3]) / 2),
        ))
        self.assertEqual(calls, [row["record"]])

    def test_canvas_draws_items(self):
        self.assertTrue(self.page.canvas.find_all())

    def test_dashboard_and_top_nav(self):
        # 趋势图按画布实际宽度绘制，需要窗口真正映射后才能断言图元
        self.root.deiconify()
        self.root.update()
        self.app.show_page("home")
        self.root.update()
        home = self.app.pages["home"]
        self.assertEqual(set(self.app.nav_buttons),
                         {"home", "tasks", "records", "stats", "settings"})
        self.assertGreaterEqual(len(home.trend.find_all()), 15)
        self.assertTrue(home.time_label.cget("text"))

    def test_start_dialog_centered(self):
        self.root.deiconify()
        self.root.update()
        self.app.open_start_dialog(lambda: None)
        self.root.update()
        wins = [w for w in self.root.winfo_children()
                if isinstance(w, tk.Toplevel)]
        win = wins[-1]
        expected_x = self.root.winfo_rootx() + (
            self.root.winfo_width() - 430) // 2
        expected_y = self.root.winfo_rooty() + (
            self.root.winfo_height() - 300) // 2
        self.assertLessEqual(abs(win.winfo_x() - expected_x), 5)
        self.assertLessEqual(abs(win.winfo_y() - expected_y), 5)
        win.destroy()

    def test_task_page_and_start_task(self):
        task = self.app.add_task("写论文", 0, "论文")
        self.assertIsNotNone(task)

        self.app.show_page("tasks")
        self.root.update()
        self.assertIn(task, self.app.pages["tasks"].app.today_tasks())

        self.assertTrue(self.app.start_task(task))
        self.assertTrue(self.app.timer.is_running)
        self.assertEqual(self.app.current_task_id, task.id)
        self.assertEqual(self.app.session_title, "写论文")
        self.assertEqual(self.app.session_tag, "论文")

        self.app.timer.stop()
        self.app.current_task_id = ""


# ---------------------------------------------------------------- 设置文案
class SettingsWordingTest(_TkAppFixture):
    """锁住“开始前询问”文案：说明只在按钮启动时询问，快捷键不询问。"""

    PROMPT_TEXT = "开始计时前询问学习内容（仅按钮启动；快捷键不询问）"
    OLD_TEXT = "开始计时前询问学习内容（可跳过）"

    def _collect_checktexts(self, widget):
        """递归收集该页面下所有 Checkbutton 的文案。"""
        texts = []
        for child in widget.winfo_children():
            if isinstance(child, tk.Checkbutton):
                texts.append(child.cget("text"))
            texts.extend(self._collect_checktexts(child))
        return texts

    def test_prompt_checkbox_wording(self):
        self.app.show_page("settings")
        self.root.update()

        texts = self._collect_checktexts(self.app.pages["settings"])
        self.assertIn(self.PROMPT_TEXT, texts)
        self.assertNotIn(self.OLD_TEXT, texts, "旧文案不应残留")


# ---------------------------------------------------------------- 图标降级
class WindowIconTest(_TkAppFixture):
    """窗口图标是装饰：正常时静默设置，缺失 / 损坏时只 warning，绝不阻断启动。"""

    def test_present_icon_is_applied_silently(self):
        with mock.patch.object(ui_app.logger, "warning") as warn:
            self.app._apply_window_icon()  # 真实 assets/study_timer.ico
        warn.assert_not_called()
        self.assertTrue(Path(project_resource_path("assets/study_timer.ico")).is_file())

    def test_missing_or_broken_icon_only_warns(self):
        missing = os.path.join(self.tmpdir, "assets", "study_timer.ico")

        # 场景 1：图标文件不存在（resource_path 指向不存在的 ico）
        with mock.patch.object(ui_app, "resource_path", lambda _rel: missing):
            with mock.patch.object(ui_app.logger, "warning") as warn:
                self.app._apply_window_icon()  # 不应抛异常
        self.assertEqual(warn.call_count, 1)
        self.assertIn("设置窗口图标失败", warn.call_args[0][0])
        self.assertTrue(warn.call_args[1].get("exc_info"), "降级日志应带堆栈线索")

        # 场景 2：文件在但 Tk 拒绝加载（用假 root 稳定复现 TclError，
        # 同时说明 _apply_window_icon 只依赖 self.root.iconbitmap）
        fake_root = mock.Mock()
        fake_root.iconbitmap.side_effect = tk.TclError("not a valid icon")
        original_root = self.app.root
        self.app.root = fake_root
        try:
            with mock.patch.object(ui_app, "resource_path", project_resource_path):
                with mock.patch.object(ui_app.logger, "warning") as warn:
                    self.app._apply_window_icon()
        finally:
            self.app.root = original_root
        self.assertEqual(warn.call_count, 1)
        self.assertIn("设置窗口图标失败", warn.call_args[0][0])
        fake_root.iconbitmap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
