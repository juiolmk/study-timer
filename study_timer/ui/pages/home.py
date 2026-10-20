# -*- coding: utf-8 -*-
"""首页：计时 / 番茄钟 / 今日概览 / 最近记录。"""

from __future__ import annotations

import tkinter as tk
from datetime import date

from ...config import WEEKDAY_CN
from ...services import (
    MODE_COUNTDOWN,
    MODE_STOPWATCH,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    PHASE_WORK,
)
from ..widgets import Card, RingProgress, RoundedButton, Segmented


class HomePage(tk.Frame):
    # 索引 -> (模式, 分钟)
    MODES = [
        (MODE_STOPWATCH, 0),
        (MODE_COUNTDOWN, 25),
        (MODE_COUNTDOWN, 45),
        (MODE_COUNTDOWN, 60),
    ]

    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme
        self._mode_index = 0
        self._build()
        self.refresh()

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p

        header = tk.Frame(self, bg=p.bg)
        header.pack(fill="x", padx=28, pady=(22, 12))
        tk.Label(header, text="今日学习", font=self.t.font_h1, bg=p.bg, fg=p.text).pack(side="left")
        self.date_label = tk.Label(header, text="", font=self.t.font_sm, bg=p.bg, fg=p.muted)
        self.date_label.pack(side="left", padx=12, pady=(10, 0))

        # 计时卡片
        card = Card(self, self.t)
        card.pack(fill="x", padx=28, pady=(0, 14))
        inner = tk.Frame(card, bg=p.surface)
        inner.pack(fill="x", padx=24, pady=20)

        left = tk.Frame(inner, bg=p.surface)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="专注计时", font=self.t.font_sm, bg=p.surface, fg=p.muted).pack(anchor="w")

        self.segmented = Segmented(
            left, self.t, ["自由计时", "25 分", "45 分", "60 分"], self._on_mode,
        )
        self.segmented.pack(anchor="w", pady=(8, 10))

        self.time_label = tk.Label(left, text="00:00:00", font=self.t.font_timer,
                                   bg=p.surface, fg=p.text)
        self.time_label.pack(anchor="w")

        self.status_label = tk.Label(left, text="未开始", font=self.t.font_sm,
                                     bg=p.surface, fg=p.muted)
        self.status_label.pack(anchor="w", pady=(0, 14))

        actions = tk.Frame(left, bg=p.surface)
        actions.pack(anchor="w")
        self.btn_toggle = RoundedButton(actions, self.t, "开始学习", command=self.toggle)
        self.btn_toggle.pack(side="left")
        self.btn_finish = RoundedButton(actions, self.t, "结束并保存", command=self._finish,
                                        variant="ghost")
        self.btn_finish.pack(side="left", padx=10)
        self.btn_quick = RoundedButton(actions, self.t, "补记",
                                       command=self.app.open_quick_record_dialog,
                                       variant="ghost")
        self.btn_quick.pack(side="left")

        right = tk.Frame(inner, bg=p.surface)
        right.pack(side="right")
        self.ring = RingProgress(right, self.t)
        self.ring.pack()

        # 概览卡片
        stats = tk.Frame(self, bg=p.bg)
        stats.pack(fill="x", padx=28)
        for i in range(3):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
        self.card_min = self._stat(stats, 0, "今日已学", "0 分")
        self.card_streak = self._stat(stats, 1, "连续打卡", "0 天")
        self.card_goal = self._stat(stats, 2, "今日目标", "0%")

        # 最近记录
        recent = Card(self, self.t)
        recent.pack(fill="both", expand=True, padx=28, pady=14)
        recent_header = tk.Frame(recent, bg=p.surface)
        recent_header.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(recent_header, text="最近记录", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        more = tk.Label(recent_header, text="查看全部 ›", font=self.t.font_sm,
                        bg=p.surface, fg=p.primary, cursor="hand2")
        more.pack(side="right")
        more.bind("<Button-1>", lambda _e: self.app.show_page("records"))

        self.recent_box = tk.Frame(recent, bg=p.surface)
        self.recent_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))

    def _stat(self, parent, column, title, value):
        p = self.t.p
        card = Card(parent, self.t)
        card.grid(row=0, column=column,
                  padx=(0 if column == 0 else 10, 0), sticky="ew")
        tk.Label(card, text=title, font=self.t.font_sm, bg=p.surface, fg=p.muted).pack(
            anchor="w", padx=14, pady=(12, 0))
        val = tk.Label(card, text=value, font=self.t.font_num, bg=p.surface, fg=p.text)
        val.pack(anchor="w", padx=14, pady=(0, 12))
        return val

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        today = date.today()
        self.date_label.configure(
            text=today.strftime("%Y年%m月%d日") + " · 周" + WEEKDAY_CN[today.weekday()])

        today_min = self.app.stats.minutes_on(today.isoformat())
        goal = max(1, self.app.store.settings.goal_min)
        self.card_min.configure(text=self.app.fmt(today_min))
        self.card_streak.configure(text=f"{self.app.stats.current_streak()} 天")
        self.card_goal.configure(text=f"{min(100, int(today_min / goal * 100))}%")

        self._refresh_recent()
        self.update_timer_display()

    def _refresh_recent(self):
        p = self.t.p
        for widget in self.recent_box.winfo_children():
            widget.destroy()

        records = sorted(self.app.store.records,
                         key=lambda r: (r.date, r.start), reverse=True)[:3]
        if not records:
            tk.Label(self.recent_box, text="还没有记录，开始第一次专注吧",
                     font=self.t.font, bg=p.surface, fg=p.muted).pack(anchor="w", pady=8)
            return

        for record in records:
            row = tk.Frame(self.recent_box, bg=p.surface)
            row.pack(fill="x", pady=4)
            tk.Label(row, text="📘", font=self.t.font, bg=p.surface, fg=p.primary).pack(side="left")
            tk.Label(row, text=record.title or "(未命名)", font=self.t.font_bold,
                     bg=p.surface, fg=p.text).pack(side="left", padx=6)
            if record.tag:
                tk.Label(row, text=record.tag, font=self.t.font_sm, bg=p.surface_alt,
                         fg=p.primary, padx=8, pady=1).pack(side="left", padx=4)
            tk.Label(row, text=record.date[5:], font=self.t.font_sm,
                     bg=p.surface, fg=p.muted).pack(side="left", padx=6)
            tk.Label(row, text=self.app.fmt(record.duration_min), font=self.t.font_bold,
                     bg=p.surface, fg=p.success).pack(side="right")

    # ------------------------------------------------------------ 计时交互
    def _on_mode(self, index):
        if self.app.timer.is_active:
            self.segmented.select(self._mode_index, notify=False)
            self.app.toast("请先结束当前计时再切换模式")
            return

        self._mode_index = index
        mode, minutes = self.MODES[index]
        if mode == MODE_COUNTDOWN:
            self.app.timer.configure(MODE_COUNTDOWN, minutes)
            self.app.store.settings.focus_preset = minutes
            self.app.repo.save(self.app.store)
        else:
            self.app.timer.configure(MODE_STOPWATCH)
        self.update_timer_display()

    def set_preset(self, minutes):
        """外部（如休息结束）同步分段控件到指定专注时长。"""
        for index, (mode, value) in enumerate(self.MODES):
            if mode == MODE_COUNTDOWN and value == minutes:
                self._mode_index = index
                self.segmented.select(index, notify=False)
                break
        self.update_timer_display()

    def toggle(self):
        """开始 / 暂停 / 继续。"""
        timer = self.app.timer
        if timer.is_idle:
            if timer.mode == MODE_COUNTDOWN:
                # 每次从空闲启动倒计时，都视为新一轮专注
                self.app.pomodoro_phase = PHASE_WORK
            timer.start()
        elif timer.is_running:
            timer.pause()
        else:
            timer.resume()
        self.update_timer_display()

    def _finish(self):
        self.app.finish_session()

    def update_timer_display(self):
        timer = self.app.timer
        p = self.t.p
        today = date.today()
        today_min = self.app.stats.minutes_on(today.isoformat())
        goal = max(1, self.app.store.settings.goal_min)
        phase = getattr(self.app, "pomodoro_phase", PHASE_WORK)
        is_break = phase in (PHASE_SHORT_BREAK, PHASE_LONG_BREAK)

        if timer.mode == MODE_COUNTDOWN:
            remaining = timer.remaining() or 0
            self.time_label.configure(text=self.app.fmt_clock(remaining))
            ratio = (timer.elapsed() / timer.target) if timer.target else 0
            if is_break:
                label = "长休" if phase == PHASE_LONG_BREAK else "短休"
                self.ring.set(
                    ratio,
                    f"{int(min(1.0, ratio) * 100)}%",
                    label,
                    p.warning,
                )
            else:
                self.ring.set(
                    ratio,
                    f"{int(min(1.0, ratio) * 100)}%",
                    "本次专注",
                    p.success if ratio >= 1 else p.primary,
                )
        else:
            self.time_label.configure(text=self.app.fmt_clock(timer.elapsed()))
            ratio = today_min / goal
            self.ring.set(
                min(1.0, ratio),
                f"{min(100, int(ratio * 100))}%",
                f"{int(today_min)}/{goal} 分",
                p.success if ratio >= 1 else p.primary,
            )

        if timer.is_running:
            if is_break:
                text = "长休中" if phase == PHASE_LONG_BREAK else "短休中"
                self.status_label.configure(text=text, fg=p.warning)
            else:
                self.status_label.configure(text="专注中", fg=p.success)
            self.btn_toggle.set_text("暂停")
        elif timer.is_paused:
            self.status_label.configure(text="已暂停", fg=p.warning)
            self.btn_toggle.set_text("继续")
        else:
            self.status_label.configure(
                text="准备开始" if timer.mode == MODE_COUNTDOWN else "未开始", fg=p.muted)
            self.btn_toggle.set_text("开始学习")

        self.btn_finish.set_text("结束休息" if is_break else "结束并保存")
        self.btn_finish.set_enabled(timer.is_active)
