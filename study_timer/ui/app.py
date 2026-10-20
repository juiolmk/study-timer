# -*- coding: utf-8 -*-
"""主窗口：侧边栏导航、页面调度、计时循环、提醒与数据操作。"""

from __future__ import annotations

import tkinter as tk
import uuid
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from ..config import (
    APP_NAME,
    APP_NAME_EN,
    MIN_RECORD_SECONDS,
    QUICK_PRESETS,
    VERSION,
)
from ..hotkey import HOTKEY_TEXT, POLL_INTERVAL_MS, HotkeyManager
from ..models import Record
from ..services import (
    MODE_COUNTDOWN,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    PHASE_WORK,
    StatsService,
    TimerService,
    choose_break,
)
from ..storage import Repository
from .pages.home import HomePage
from .pages.records import RecordsPage
from .pages.settings import SettingsPage
from .pages.stats import StatsPage
from .theme import Theme, configure_ttk
from .widgets import Card, RoundedButton, Segmented, SidebarButton, make_entry


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.repo = Repository()
        self.store = self.repo.load()
        self._recovered_from_backup = self.repo.last_load_recovered
        self.stats = StatsService(self.store)
        self.timer = TimerService()
        self.pomodoro_phase = PHASE_WORK
        self.completed_rounds = 0

        self._alive = True
        self._finishing = False
        self.current_key = "home"
        self._theme = Theme(self.store.settings.theme)
        # 全局快捷键挂在 App 上：主题重建（rebuild）时不重启，跨重建存活
        self.hotkey = HotkeyManager()

        root.title(f"{APP_NAME} · {VERSION}")
        root.geometry("980x660")
        root.minsize(860, 580)
        root.configure(bg=self._theme.p.bg)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_ui()
        self.show_page("home")

        root.bind("<space>", self._on_space)
        root.after(200, self._tick)
        root.after(60000, self._reminder_loop)

        if self._recovered_from_backup:
            root.after(800, lambda: self.toast(
                "检测到数据文件异常，已从备份恢复", duration_ms=3200))

        # 全局快捷键：按设置启动；失败（被占用 / 非 Windows）静默降级并提示一次
        if self.store.settings.hotkey_enabled:
            if not self.hotkey.start():
                root.after(600, self._notify_hotkey_unavailable)
        root.after(POLL_INTERVAL_MS, self._poll_hotkey)

    # ------------------------------------------------------------ 布局
    def build_ui(self):
        self._theme = Theme(self.store.settings.theme)
        configure_ttk(self.root, self._theme.p)
        p = self._theme.p
        self.root.configure(bg=p.bg)

        self.sidebar = tk.Frame(self.root, bg=p.surface, width=192)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.content = tk.Frame(self.root, bg=p.bg)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {
            "home": HomePage(self.content, self, self._theme),
            "records": RecordsPage(self.content, self, self._theme),
            "stats": StatsPage(self.content, self, self._theme),
            "settings": SettingsPage(self.content, self, self._theme),
        }

    def _build_sidebar(self):
        p = self._theme.p

        brand = tk.Frame(self.sidebar, bg=p.surface)
        brand.pack(fill="x", padx=18, pady=(22, 18))
        tk.Label(brand, text="📚", font=("Segoe UI Emoji", 20),
                 bg=p.surface, fg=p.text).pack(side="left")

        brand_text = tk.Frame(brand, bg=p.surface)
        brand_text.pack(side="left", padx=8)
        tk.Label(brand_text, text=APP_NAME, font=self._theme.font_h2,
                 bg=p.surface, fg=p.text).pack(anchor="w")
        tk.Label(brand_text, text=APP_NAME_EN, font=self._theme.font_sm,
                 bg=p.surface, fg=p.muted).pack(anchor="w")

        nav = tk.Frame(self.sidebar, bg=p.surface)
        nav.pack(fill="x")

        self.nav_buttons = {}
        items = [
            ("home", "🏠  首页"),
            ("records", "🗂  记录"),
            ("stats", "📊  统计"),
            ("settings", "⚙  设置"),
        ]
        for key, text in items:
            button = SidebarButton(nav, self._theme, text,
                                   lambda k=key: self.show_page(k))
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        bottom = tk.Frame(self.sidebar, bg=p.surface)
        bottom.pack(side="bottom", fill="x", padx=18, pady=18)
        self.streak_mini = tk.Label(bottom, text="", font=self._theme.font_sm,
                                    bg=p.surface, fg=p.muted)
        self.streak_mini.pack(anchor="w")
        tk.Label(bottom, text=f"v{VERSION}", font=self._theme.font_sm,
                 bg=p.surface, fg=p.muted).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------ 页面调度
    def show_page(self, key):
        if key not in self.pages:
            return
        self.current_key = key

        for name, page in self.pages.items():
            if name == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

        for name, button in self.nav_buttons.items():
            button.set_active(name == key)

        page = self.pages[key]
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                pass

        self._update_streak_badge()

    def refresh_all(self):
        for page in self.pages.values():
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception:
                    pass
        self._update_streak_badge()

    def _update_streak_badge(self):
        try:
            self.streak_mini.configure(text=f"🔥 连续 {self.stats.current_streak()} 天")
        except Exception:
            pass

    # ------------------------------------------------------------ 计时循环
    def _tick(self):
        if not self._alive:
            return
        try:
            self._update_timer()
        except Exception:
            pass
        self.root.after(200, self._tick)

    def _update_timer(self):
        timer = self.timer

        # 倒计时结束：自动收尾
        if (timer.is_running and timer.mode == MODE_COUNTDOWN
                and (timer.remaining() or 0) <= 0 and not self._finishing):
            self._finishing = True
            try:
                self.finish_session(auto=True)
            finally:
                self._finishing = False
            return

        if self.current_key == "home" and "home" in getattr(self, "pages", {}):
            try:
                self.pages["home"].update_timer_display()
            except Exception:
                pass

    def finish_session(self, auto: bool = False):
        timer = self.timer
        if not timer.is_active:
            return

        phase = self.pomodoro_phase
        mode = timer.mode
        seconds = timer.stop()
        self.refresh_all()

        # 休息结束：回到待开始的专注模式，不写记录
        if phase in (PHASE_SHORT_BREAK, PHASE_LONG_BREAK):
            self._prepare_work_mode()
            if auto:
                self._beep()
                self.toast("休息结束，开始下一轮吧", duration_ms=2600)
            else:
                self.toast("已结束休息")
            return

        if seconds < MIN_RECORD_SECONDS:
            if not auto:
                self.toast("时长太短，未记录")
            return

        settings = self.store.settings
        if auto and mode == MODE_COUNTDOWN and settings.auto_break:
            self._auto_record_work(seconds)
            self.completed_rounds += 1
            self._start_break()
            return

        if auto:
            self._beep()

        default_title = "番茄专注" if mode == MODE_COUNTDOWN else ""
        self.open_record_dialog(duration_seconds=seconds, default_title=default_title)

    def _auto_record_work(self, seconds: float):
        """番茄钟完成时自动落一条默认记录，避免休息打断记录流程。"""
        minutes = max(1, int(round(seconds / 60)))
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(seconds=seconds)
        record = Record(
            id=str(uuid.uuid4()),
            date=end_dt.strftime("%Y-%m-%d"),
            start=start_dt.strftime("%Y-%m-%d %H:%M"),
            end=end_dt.strftime("%Y-%m-%d %H:%M"),
            duration_min=minutes,
            title="番茄专注",
            tag=self.last_used_tag(),
            note="",
        )
        self.store.records.append(record)
        self.store.checkins.add(record.date)
        self.repo.save(self.store)
        self.refresh_all()

    def _start_break(self):
        """按已完成轮数自动开始短休或长休。"""
        settings = self.store.settings
        phase, minutes = choose_break(
            self.completed_rounds,
            settings.rounds_per_long_break,
            settings.short_break_min,
            settings.long_break_min,
        )
        self.pomodoro_phase = phase
        self.timer.configure(MODE_COUNTDOWN, minutes)
        self.timer.start()
        self.refresh_all()
        self._beep()
        label = "长休" if phase == PHASE_LONG_BREAK else "短休"
        self.toast(f"本轮已记录，开始 {minutes} 分钟{label}", duration_ms=2800)

    def _prepare_work_mode(self):
        """休息结束后回到默认专注时长，等待用户开始下一轮。"""
        self.pomodoro_phase = PHASE_WORK
        preset = max(1, int(self.store.settings.focus_preset))
        self.timer.configure(MODE_COUNTDOWN, preset)
        home = getattr(self, "pages", {}).get("home")
        if home is not None and hasattr(home, "set_preset"):
            try:
                home.set_preset(preset)
            except Exception:
                pass
        self.refresh_all()

    @staticmethod
    def _beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    # ------------------------------------------------------------ 记录弹窗
    def open_record_dialog(self, duration_seconds: float = 0, record=None, default_title: str = ""):
        t = self._theme
        p = t.p

        win = tk.Toplevel(self.root)
        win.title("编辑记录" if record else "记录学习")
        win.configure(bg=p.bg)
        win.geometry("480x510")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        now = datetime.now()
        if record:
            date_value = record.date
            start_value = (record.start or "")[-5:] or now.strftime("%H:%M")
            duration_value = record.duration_min
            title_value = record.title
            tag_value = record.tag
            note_value = record.note
        else:
            duration_value = max(1, int(round(duration_seconds / 60))) if duration_seconds else 0
            start_day = now - timedelta(minutes=duration_value)
            date_value = now.strftime("%Y-%m-%d")
            start_value = start_day.strftime("%H:%M")
            title_value = default_title
            tag_value = ""
            note_value = ""

        card = Card(win, t)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        form = tk.Frame(card, bg=p.surface)
        form.pack(fill="both", expand=True, padx=20, pady=18)
        form.grid_columnconfigure(1, weight=1)

        def add_row(row, label, widget):
            tk.Label(form, text=label, font=t.font_sm, bg=p.surface, fg=p.muted).grid(
                row=row, column=0, sticky="w", pady=7, padx=(0, 14))
            widget.grid(row=row, column=1, sticky="ew", pady=7)

        e_date = make_entry(form, t)
        e_date.insert(0, date_value)
        add_row(0, "日期", e_date)

        e_start = make_entry(form, t)
        e_start.insert(0, start_value)
        add_row(1, "开始时间", e_start)

        e_duration = make_entry(form, t)
        e_duration.insert(0, str(duration_value))
        add_row(2, "时长（分钟）", e_duration)

        e_title = make_entry(form, t)
        e_title.insert(0, title_value)
        add_row(3, "学习内容", e_title)

        e_tag = ttk.Combobox(form, values=self.store.tags(), font=t.font, state="normal")
        e_tag.set(tag_value)
        add_row(4, "标签 / 科目", e_tag)

        e_note = make_entry(form, t)
        e_note.insert(0, note_value)
        add_row(5, "备注", e_note)

        def save():
            day = e_date.get().strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except Exception:
                messagebox.showerror("格式错误", "日期格式应为 YYYY-MM-DD", parent=win)
                return

            try:
                minutes = int(e_duration.get().strip())
                if minutes <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("格式错误", "时长须为正整数（分钟）", parent=win)
                return

            start_text = e_start.get().strip() or "00:00"
            try:
                start_dt = datetime.strptime(f"{day} {start_text}", "%Y-%m-%d %H:%M")
            except Exception:
                messagebox.showerror("格式错误", "开始时间格式应为 HH:MM", parent=win)
                return

            end_dt = start_dt + timedelta(minutes=minutes)
            title = e_title.get().strip()
            tag = e_tag.get().strip()
            note = e_note.get().strip()

            if record:
                record.date = day
                record.start = start_dt.strftime("%Y-%m-%d %H:%M")
                record.end = end_dt.strftime("%Y-%m-%d %H:%M")
                record.duration_min = minutes
                record.title = title
                record.tag = tag
                record.note = note
            else:
                self.store.records.append(Record(
                    id=str(uuid.uuid4()),
                    date=day,
                    start=start_dt.strftime("%Y-%m-%d %H:%M"),
                    end=end_dt.strftime("%Y-%m-%d %H:%M"),
                    duration_min=minutes,
                    title=title,
                    tag=tag,
                    note=note,
                ))

            self.store.checkins.add(day)
            self.repo.save(self.store)
            win.destroy()
            self.refresh_all()
            self.toast("记录已保存")

        buttons = tk.Frame(card, bg=p.surface)
        buttons.pack(fill="x", padx=20, pady=(0, 18))
        RoundedButton(buttons, t, "保存", command=save, variant="success").pack(side="right")
        RoundedButton(buttons, t, "取消", command=win.destroy, variant="ghost").pack(
            side="right", padx=8)

        win.bind("<Escape>", lambda _e: win.destroy())

    # ------------------------------------------------------------ 快速补记
    def last_used_tag(self) -> str:
        """最近一条记录的标签，用于快速补记预填。"""
        if not self.store.records:
            return ""
        latest = max(self.store.records, key=lambda item: (item.date, item.start))
        return latest.tag.strip()

    def open_quick_record_dialog(self):
        """快速补记：不启动计时，用最少步骤记录刚才的学习。"""
        t = self._theme
        p = t.p

        win = tk.Toplevel(self.root)
        win.title("快速补记")
        win.configure(bg=p.bg)
        win.geometry("470x540")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        now = datetime.now()
        default_minutes = QUICK_PRESETS[1] if len(QUICK_PRESETS) > 1 else QUICK_PRESETS[0]
        default_start = now - timedelta(minutes=default_minutes)

        card = Card(win, t)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        body = tk.Frame(card, bg=p.surface)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(body, text="快速补记", font=t.font_h2,
                 bg=p.surface, fg=p.text).pack(anchor="w")
        tk.Label(body, text="不启动计时，直接记录刚才的学习",
                 font=t.font_sm, bg=p.surface, fg=p.muted).pack(anchor="w", pady=(2, 12))

        tk.Label(body, text="时长", font=t.font_sm,
                 bg=p.surface, fg=p.muted).pack(anchor="w")
        preset_row = tk.Frame(body, bg=p.surface)
        preset_row.pack(fill="x", pady=(4, 10))

        duration_var = tk.StringVar(value=str(default_minutes))
        start_var = tk.StringVar(value=default_start.strftime("%H:%M"))

        def apply_preset(index):
            minutes = QUICK_PRESETS[index]
            duration_var.set(str(minutes))
            start_var.set((datetime.now() - timedelta(minutes=minutes)).strftime("%H:%M"))

        presets = Segmented(
            preset_row, t, [f"{m} 分" for m in QUICK_PRESETS], apply_preset,
            index=QUICK_PRESETS.index(default_minutes),
        )
        presets.pack(side="left")

        duration_entry = make_entry(preset_row, t, width=6, textvariable=duration_var)
        tk.Label(preset_row, text="或", font=t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left", padx=8)
        duration_entry.pack(side="left")
        tk.Label(preset_row, text="分钟", font=t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left", padx=4)

        form = tk.Frame(body, bg=p.surface)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)

        def add_row(row, label, widget):
            tk.Label(form, text=label, font=t.font_sm,
                     bg=p.surface, fg=p.muted).grid(
                row=row, column=0, sticky="w", pady=6, padx=(0, 14))
            widget.grid(row=row, column=1, sticky="ew", pady=6)

        date_entry = make_entry(form, t)
        date_entry.insert(0, now.strftime("%Y-%m-%d"))
        add_row(0, "日期", date_entry)

        start_entry = make_entry(form, t, textvariable=start_var)
        add_row(1, "开始时间", start_entry)

        title_entry = make_entry(form, t)
        add_row(2, "学习内容", title_entry)

        tag_entry = ttk.Combobox(form, values=self.store.tags(), font=t.font, state="normal")
        tag_entry.set(self.last_used_tag())
        add_row(3, "标签 / 科目", tag_entry)

        note_entry = make_entry(form, t)
        add_row(4, "备注", note_entry)

        def save(_event=None):
            day = date_entry.get().strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except Exception:
                messagebox.showerror("格式错误", "日期格式应为 YYYY-MM-DD", parent=win)
                return

            try:
                minutes = int(duration_var.get().strip())
                if minutes <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("格式错误", "时长须为正整数（分钟）", parent=win)
                return

            start_text = start_var.get().strip() or "00:00"
            try:
                start_dt = datetime.strptime(f"{day} {start_text}", "%Y-%m-%d %H:%M")
            except Exception:
                messagebox.showerror("格式错误", "开始时间格式应为 HH:MM", parent=win)
                return

            end_dt = start_dt + timedelta(minutes=minutes)
            self.store.records.append(Record(
                id=str(uuid.uuid4()),
                date=day,
                start=start_dt.strftime("%Y-%m-%d %H:%M"),
                end=end_dt.strftime("%Y-%m-%d %H:%M"),
                duration_min=minutes,
                title=title_entry.get().strip(),
                tag=tag_entry.get().strip(),
                note=note_entry.get().strip(),
            ))
            self.store.checkins.add(day)
            self.repo.save(self.store)
            win.destroy()
            self.refresh_all()
            self.toast("已补记")

        buttons = tk.Frame(body, bg=p.surface)
        buttons.pack(fill="x", pady=(16, 0))
        RoundedButton(buttons, t, "保存补记", command=save,
                      variant="success").pack(side="right")
        RoundedButton(buttons, t, "取消", command=win.destroy,
                      variant="ghost").pack(side="right", padx=8)

        win.bind("<Return>", save)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.after(60, title_entry.focus_set)

    # ------------------------------------------------------------ 主题 / 数据
    def set_theme(self, name: str):
        name = "dark" if name == "dark" else "light"
        if name == self.store.settings.theme:
            return
        self.store.settings.theme = name
        self.repo.save(self.store)
        self.rebuild()

    def rebuild(self):
        current = self.current_key
        for widget in self.root.winfo_children():
            widget.destroy()
        self.build_ui()
        self.show_page(current)
        try:
            self._update_timer()
        except Exception:
            pass

    def replace_store(self, store):
        self.store = store
        self.stats = StatsService(store)
        self.repo.save(store)
        self.refresh_all()
        try:
            self._update_timer()
        except Exception:
            pass

    # ------------------------------------------------------------ 交互辅助
    def toast(self, message: str, duration_ms: int = 1600):
        try:
            p = self._theme.p
            label = tk.Label(
                self.root, text=message, font=self._theme.font_sm,
                bg=p.text, fg=p.surface, padx=14, pady=7,
            )
            label.place(relx=0.5, rely=1.0, anchor="s", y=-16)
            self.root.after(duration_ms, label.destroy)
        except Exception:
            pass

    def _on_space(self, _event):
        widget = self.root.focus_get()
        try:
            if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
                return
        except Exception:
            pass
        if self.current_key == "home" and "home" in getattr(self, "pages", {}):
            self.pages["home"].toggle()

    # ------------------------------------------------------------ 全局快捷键
    def apply_hotkey_setting(self) -> bool:
        """按设置启动 / 停止全局快捷键，返回目标状态是否达成。

        - 设置为启用：尝试注册热键，成功返回 True，被占用返回 False。
        - 设置为关闭：注销热键并返回 True（关闭这一目标已完成）。
        """
        if self.store.settings.hotkey_enabled:
            return self.hotkey.start()
        self.hotkey.stop()
        return True

    def _poll_hotkey(self):
        """Tk 主线程轮询热键事件（后台线程只写队列，不直接碰 Tk）。"""
        if not self._alive:
            return
        try:
            if self.hotkey.poll():
                self._on_hotkey()
        except Exception:
            pass
        if self._alive:
            self.root.after(POLL_INTERVAL_MS, self._poll_hotkey)

    def _on_hotkey(self):
        """热键命中：切换计时状态并给出轻提示（不弹窗、不强制切页）。"""
        try:
            if self.root.grab_current() is not None:
                return  # 有模态弹窗（如记录编辑）时忽略
        except Exception:
            return

        home = getattr(self, "pages", {}).get("home")
        if home is None:
            return

        was_idle = self.timer.is_idle
        was_running = self.timer.is_running
        home.toggle()

        if was_idle:
            self.toast("已开始专注")
        elif was_running:
            self.toast("已暂停")
        else:
            self.toast("继续专注")

    def _notify_hotkey_unavailable(self):
        """热键不可用时的一次性提示（延迟执行，避免遮挡首屏）。"""
        if not self._alive:
            return
        self.toast(f"全局快捷键 {HOTKEY_TEXT} 不可用（可能被占用）", duration_ms=2600)

    # ------------------------------------------------------------ 提醒
    def _reminder_loop(self):
        try:
            self.check_reminders()
        except Exception:
            pass
        if self._alive:
            self.root.after(60000, self._reminder_loop)

    def check_reminders(self):
        settings = self.store.settings
        today = date.today().isoformat()
        goal = max(1, settings.goal_min)
        minutes = self.stats.minutes_on(today)

        if settings.remind:
            try:
                remind_at = datetime.strptime(settings.remind_time, "%H:%M").time()
            except Exception:
                remind_at = datetime.strptime("21:00", "%H:%M").time()

            if (datetime.now().time() >= remind_at
                    and settings.last_remind_date != today
                    and minutes < goal):
                settings.last_remind_date = today
                self.repo.save(self.store)
                messagebox.showinfo(
                    "学习提醒 🔔",
                    f"今天还没完成目标哦～\n目标 {goal} 分钟，目前 {int(minutes)} 分钟。",
                )

        if minutes >= goal and settings.last_goal_date != today:
            settings.last_goal_date = today
            self.repo.save(self.store)
            messagebox.showinfo(
                "达成目标 🎉",
                f"今天已学习 {int(minutes)} 分钟，达标！继续保持～",
            )

    # ------------------------------------------------------------ 关闭
    def on_close(self):
        if self.timer.is_active:
            close = messagebox.askyesno(
                "退出", "正在计时，退出后本次时长不会保存，确定退出吗？")
            if not close:
                return
        self._alive = False
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self.root.destroy()

    # ------------------------------------------------------------ 格式化
    @staticmethod
    def fmt(minutes):
        minutes = int(round(minutes))
        hours, rest = divmod(minutes, 60)
        if hours:
            return f"{hours}小时{rest}分" if rest else f"{hours}小时"
        return f"{rest}分"

    @staticmethod
    def fmt_clock(seconds):
        seconds = int(seconds)
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _enable_dpi_awareness():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def run():
    _enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()
