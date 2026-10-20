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
    VERSION,
)
from ..models import Record
from ..services import MODE_COUNTDOWN, StatsService, TimerService
from ..storage import Repository
from .pages.home import HomePage
from .pages.records import RecordsPage
from .pages.settings import SettingsPage
from .pages.stats import StatsPage
from .theme import Theme, configure_ttk
from .widgets import Card, RoundedButton, SidebarButton, make_entry


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.repo = Repository()
        self.store = self.repo.load()
        self.stats = StatsService(self.store)
        self.timer = TimerService()

        self._alive = True
        self._finishing = False
        self.current_key = "home"
        self._theme = Theme(self.store.settings.theme)

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

        mode = timer.mode
        seconds = timer.stop()
        self.refresh_all()

        if seconds < MIN_RECORD_SECONDS:
            if not auto:
                self.toast("时长太短，未记录")
            return

        if auto:
            self._beep()

        default_title = "番茄专注" if mode == MODE_COUNTDOWN else ""
        self.open_record_dialog(duration_seconds=seconds, default_title=default_title)

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
