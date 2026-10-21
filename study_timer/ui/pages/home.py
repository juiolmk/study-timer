# -*- coding: utf-8 -*-
"""首页：仪表盘（计时 / 今日进度 / 数据概览 / 最近记录 / 7 日趋势）。"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime

from ...config import WEEKDAY_CN
from ...tasks import PRIORITY_LABELS
from ...services import (
    MODE_COUNTDOWN,
    MODE_STOPWATCH,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    PHASE_WORK,
)
from ..widgets import Card, RingProgress, RoundedButton, Segmented, round_rect


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

        # 顶部问候
        header = tk.Frame(self, bg=p.bg)
        header.pack(fill="x", padx=32, pady=(22, 14))
        left = tk.Frame(header, bg=p.bg)
        left.pack(side="left")
        self.greeting = tk.Label(left, text="", font=self.t.font_h1,
                                 bg=p.bg, fg=p.text)
        self.greeting.pack(anchor="w")
        self.date_label = tk.Label(left, text="", font=self.t.font_sm,
                                   bg=p.bg, fg=p.muted)
        self.date_label.pack(anchor="w", pady=(3, 0))

        self.header_goal = tk.Label(
            header, text="", font=self.t.font_sm, bg=p.surface_alt,
            fg=p.primary, padx=12, pady=6,
        )
        self.header_goal.pack(side="right", pady=6)

        # 主区：计时器 + 今日进度
        hero = tk.Frame(self, bg=p.bg)
        hero.pack(fill="x", padx=32)
        hero.grid_columnconfigure(0, weight=3)
        hero.grid_columnconfigure(1, weight=1, minsize=250)
        hero.grid_rowconfigure(0, weight=1)

        timer_card = Card(hero, self.t)
        timer_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        inner = tk.Frame(timer_card, bg=p.surface)
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        top = tk.Frame(inner, bg=p.surface)
        top.pack(fill="x")
        tk.Label(top, text="专注计时", font=self.t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left")
        self.segmented = Segmented(
            top, self.t, ["自由计时", "25 分", "45 分", "60 分"], self._on_mode,
        )
        self.segmented.pack(side="right")

        self.time_label = tk.Label(inner, text="00:00:00", font=self.t.font_timer,
                                   bg=p.surface, fg=p.text)
        self.time_label.pack(pady=(14, 2))

        self.status_label = tk.Label(inner, text="未开始", font=self.t.font_sm,
                                     bg=p.surface, fg=p.muted)
        self.status_label.pack()

        actions = tk.Frame(inner, bg=p.surface)
        actions.pack(pady=(16, 0))
        self.btn_toggle = RoundedButton(actions, self.t, "开始学习", command=self.toggle)
        self.btn_toggle.pack(side="left")
        self.btn_finish = RoundedButton(actions, self.t, "结束并保存", command=self._finish,
                                        variant="ghost")
        self.btn_finish.pack(side="left", padx=10)
        self.btn_quick = RoundedButton(actions, self.t, "补记",
                                       command=self.app.open_quick_record_dialog,
                                       variant="ghost")
        self.btn_quick.pack(side="left")

        progress = Card(hero, self.t)
        progress.grid(row=0, column=1, sticky="nsew")
        pin = tk.Frame(progress, bg=p.surface)
        pin.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(pin, text="今日进度", font=self.t.font_sm,
                 bg=p.surface, fg=p.muted).pack(anchor="w")
        self.ring = RingProgress(pin, self.t, size=148, thickness=12)
        self.ring.pack(pady=(8, 6))
        self.hero_today = tk.Label(pin, text="", font=self.t.font_sm,
                                   bg=p.surface, fg=p.muted)
        self.hero_today.pack()
        self.hero_streak = tk.Label(pin, text="", font=self.t.font_sm,
                                    bg=p.surface, fg=p.muted)
        self.hero_streak.pack(pady=(4, 0))

        # 数据卡
        stats = tk.Frame(self, bg=p.bg)
        stats.pack(fill="x", padx=32, pady=(14, 0))
        for i in range(3):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
        self.card_min = self._stat(stats, 0, "今日已学", "0 分")
        self.card_streak = self._stat(stats, 1, "连续打卡", "0 天")
        self.card_goal = self._stat(stats, 2, "今日目标", "0%")

        # 底部：最近记录 + 7 日趋势
        bottom = tk.Frame(self, bg=p.bg)
        bottom.pack(fill="both", expand=True, padx=32, pady=(14, 22))
        bottom.grid_columnconfigure(0, weight=2)
        bottom.grid_columnconfigure(1, weight=1, minsize=260)
        bottom.grid_rowconfigure(0, weight=1)

        tasks_card = Card(bottom, self.t)
        tasks_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tasks_header = tk.Frame(tasks_card, bg=p.surface)
        tasks_header.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(tasks_header, text="今日任务", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        self.task_count = tk.Label(tasks_header, text="", font=self.t.font_sm,
                                   bg=p.surface, fg=p.muted)
        self.task_count.pack(side="left", padx=10)
        more = tk.Label(tasks_header, text="查看全部 ›", font=self.t.font_sm,
                        bg=p.surface, fg=p.primary, cursor="hand2")
        more.pack(side="right")
        more.bind("<Button-1>", lambda _e: self.app.show_page("tasks"))

        self.task_box = tk.Frame(tasks_card, bg=p.surface)
        self.task_box.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        trend_card = Card(bottom, self.t)
        trend_card.grid(row=0, column=1, sticky="nsew")
        trend_header = tk.Frame(trend_card, bg=p.surface)
        trend_header.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(trend_header, text="近 7 天", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        self.trend_total = tk.Label(trend_header, text="", font=self.t.font_sm,
                                    bg=p.surface, fg=p.muted)
        self.trend_total.pack(side="right")

        self.trend = tk.Canvas(trend_card, bg=p.surface,
                               highlightthickness=0, height=110)
        self.trend.pack(fill="both", expand=True, padx=16, pady=(4, 10))
        self.trend.bind("<Configure>", lambda _e: self._draw_trend())

    def _stat(self, parent, column, title, value):
        p = self.t.p
        card = Card(parent, self.t)
        card.grid(row=0, column=column,
                  padx=(0 if column == 0 else 10, 0), sticky="ew")
        tk.Label(card, text=title, font=self.t.font_sm, bg=p.surface, fg=p.muted).pack(
            anchor="w", padx=16, pady=(12, 0))
        val = tk.Label(card, text=value, font=self.t.font_num, bg=p.surface, fg=p.text)
        val.pack(anchor="w", padx=16, pady=(0, 12))
        return val

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        today = date.today()
        hour = datetime.now().hour
        if 5 <= hour < 11:
            greeting = "早上好"
        elif 11 <= hour < 14:
            greeting = "中午好"
        elif 14 <= hour < 18:
            greeting = "下午好"
        else:
            greeting = "晚上好"

        self.greeting.configure(text=f"{greeting}，今天想学点什么？")
        self.date_label.configure(
            text=today.strftime("%Y年%m月%d日") + " · 周" + WEEKDAY_CN[today.weekday()])

        today_min = self.app.stats.minutes_on(today.isoformat())
        goal = max(1, self.app.store.settings.goal_min)
        streak = self.app.stats.current_streak()

        self.header_goal.configure(text=f"今日目标 {goal} 分")
        self.card_min.configure(text=self.app.fmt(today_min))
        self.card_streak.configure(text=f"{streak} 天")
        self.card_goal.configure(text=f"{min(100, int(today_min / goal * 100))}%")
        self.hero_today.configure(text=f"已学 {today_min} 分 · 目标 {goal} 分")
        self.hero_streak.configure(text=f"连续 {streak} 天")

        self.refresh_tasks()
        self._draw_trend()
        self.update_timer_display()

    def refresh_tasks(self):
        p = self.t.p
        tasks = self.app.today_tasks()
        done = sum(1 for task in tasks if task.done)
        self.task_count.configure(text=f"{done}/{len(tasks)}")

        for widget in self.task_box.winfo_children():
            widget.destroy()

        pending = [task for task in tasks if not task.done]
        if not pending:
            text = "今天的任务都完成了" if tasks else "今天还没有任务，去写下最重要的一件"
            tk.Label(self.task_box, text=text, font=self.t.font,
                     bg=p.surface, fg=p.muted).pack(anchor="w", pady=6)
            if not tasks:
                link = tk.Label(self.task_box, text="＋ 添加任务",
                                font=self.t.font_sm, bg=p.surface,
                                fg=p.primary, cursor="hand2")
                link.pack(anchor="w")
                link.bind("<Button-1>", lambda _e: self.app.show_page("tasks"))
            return

        for task in pending[:3]:
            row = tk.Frame(self.task_box, bg=p.surface)
            row.pack(fill="x", pady=3)

            check = tk.Canvas(row, width=18, height=18, bg=p.surface,
                              highlightthickness=0, cursor="hand2")
            check.pack(side="left", padx=(0, 8))
            self._draw_check(check, task.done)
            check.bind("<Button-1>", lambda _e, t=task: self.app.toggle_task(t))

            pill = tk.Label(row, text=PRIORITY_LABELS[task.priority],
                            font=self.t.font_sm, bg=p.surface_alt,
                            fg=self._priority_color(task.priority),
                            padx=6, pady=1, cursor="hand2")
            pill.pack(side="left", padx=(0, 6))
            pill.bind("<Button-1>",
                      lambda _e, t=task: self.app.cycle_task_priority(t))

            current = task.id == self.app.current_task_id
            title = tk.Label(row, text=task.title, font=self.t.font_bold,
                             bg=p.surface, fg=p.primary if current else p.text,
                             anchor="w", width=22)
            title.pack(side="left", fill="x", expand=True)

            minutes = self.app.task_minutes(task)
            minutes_label = tk.Label(
                row, text=f"{minutes} 分" if minutes else "—",
                font=self.t.font_sm, bg=p.surface, fg=p.muted, width=6,
            )
            minutes_label.pack(side="left", padx=6)

            start = tk.Label(row, text="▶", font=self.t.font_sm,
                             bg=p.surface, fg=p.primary, cursor="hand2")
            start.pack(side="left")

            for widget in (row, title, minutes_label, start):
                widget.bind("<Button-1>", lambda _e, t=task: self._start_task(t))

    def _draw_check(self, canvas, done):
        p = self.t.p
        canvas.delete("all")
        if done:
            canvas.create_oval(1, 1, 17, 17, fill=p.success, outline="")
            canvas.create_line(5, 9, 8, 12, 13, 6, fill="#ffffff", width=2)
        else:
            canvas.create_oval(1, 1, 17, 17, outline=p.border, width=2)

    def _priority_color(self, priority):
        p = self.t.p
        return (p.danger, p.warning, p.muted)[max(0, min(2, priority))]

    def _start_task(self, task):
        if self.app.start_task(task):
            self.refresh_tasks()

    def _draw_trend(self):
        self.trend.delete("all")
        width = self.trend.winfo_width()
        if width <= 20:
            return

        p = self.t.p
        series = self.app.stats.series(7)
        maximum = max([minutes for _, minutes in series] + [1])
        chart_top, chart_bottom, gap = 8, 62, 6
        bar_w = max(8, (width - gap * 8) / 7)
        today_iso = date.today().isoformat()
        total = 0

        for index, (day, minutes) in enumerate(series):
            total += minutes
            day_obj = date.fromisoformat(day)
            x = gap + index * (bar_w + gap)
            height = int((minutes / maximum) * (chart_bottom - chart_top))
            if height > 0:
                color = (p.primary if day == today_iso
                         else self.t.mix(p.primary, p.surface_alt, 0.45))
                round_rect(self.trend, x, chart_bottom - height, x + bar_w,
                           chart_bottom, min(5, bar_w / 2), fill=color, outline="")
            else:
                round_rect(self.trend, x, chart_bottom - 3, x + bar_w,
                           chart_bottom, 2, fill=p.track, outline="")
            self.trend.create_text(
                x + bar_w / 2, chart_bottom + 14,
                text=WEEKDAY_CN[day_obj.weekday()], fill=p.muted,
                font=self.t.font_sm,
            )

        self.trend.create_line(gap, chart_bottom, width - gap, chart_bottom,
                               fill=p.border)
        self.trend_total.configure(text=f"共 {total} 分")

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

    def toggle(self, prompt=True):
        """开始 / 暂停 / 继续。"""
        timer = self.app.timer
        if timer.is_idle:
            task = self.app.current_task()
            if task and not task.done:
                self.app.start_task(task)
                return
            if task:
                self.app.current_task_id = ""
            if prompt and self.app.store.settings.ask_before_start:
                self.app.open_start_dialog(self._begin_start)
                return
            self._begin_start()
        elif timer.is_running:
            timer.pause()
        else:
            timer.resume()
        self.update_timer_display()

    def _begin_start(self):
        timer = self.app.timer
        if timer.mode == MODE_COUNTDOWN:
            # 每次从空闲启动倒计时，都视为新一轮专注
            self.app.pomodoro_phase = PHASE_WORK
        timer.start()
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
