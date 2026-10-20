# -*- coding: utf-8 -*-
"""统计页：汇总卡片、趋势柱状图、学习热力图、科目分布。"""

from __future__ import annotations

import tkinter as tk

from ..widgets import Card, Heatmap, ScrollableFrame, Segmented, round_rect


class StatsPage(tk.Frame):
    RANGES = [7, 14, 30]

    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme
        self._range_index = 0
        self._series = []
        self._goal = 1
        self._build()
        self.refresh()

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p
        self.scroll = ScrollableFrame(self, self.t)
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll.inner

        header = tk.Frame(body, bg=p.bg)
        header.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(header, text="学习统计", font=self.t.font_h1, bg=p.bg, fg=p.text).pack(side="left")

        summary = tk.Frame(body, bg=p.bg)
        summary.pack(fill="x", padx=28)
        for i in range(4):
            summary.grid_columnconfigure(i, weight=1, uniform="s")
        self.s_total = self._stat(summary, 0, "累计时长", "0")
        self.s_avg = self._stat(summary, 1, "日均时长", "0")
        self.s_met = self._stat(summary, 2, "达标天数", "0 天")
        self.s_streak = self._stat(summary, 3, "最长连续", "0 天")

        # 趋势图
        chart_card = Card(body, self.t)
        chart_card.pack(fill="x", padx=28, pady=(14, 0))
        chart_head = tk.Frame(chart_card, bg=p.surface)
        chart_head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(chart_head, text="学习趋势", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        self.range_seg = Segmented(
            chart_head, self.t, ["7 天", "14 天", "30 天"], self._on_range,
        )
        self.range_seg.pack(side="right")

        self.chart = tk.Canvas(chart_card, height=210, bg=p.surface, highlightthickness=0)
        self.chart.pack(fill="x", padx=10, pady=(4, 12))
        self.chart.bind("<Configure>", lambda _e: self._draw_chart())

        # 热力图
        heat_card = Card(body, self.t)
        heat_card.pack(fill="x", padx=28, pady=14)
        heat_head = tk.Frame(heat_card, bg=p.surface)
        heat_head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(heat_head, text="学习热力图", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        tk.Label(heat_head, text="近 12 周", font=self.t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left", padx=8)
        self.heat_hint = tk.Label(heat_head, text=" ", font=self.t.font_sm,
                                  bg=p.surface, fg=p.muted)
        self.heat_hint.pack(side="right")

        self.heatmap = Heatmap(heat_card, self.t, on_hover=self._on_heat_hover)
        self.heatmap.pack(anchor="w", padx=18, pady=(6, 16))

        # 科目分布
        tag_card = Card(body, self.t)
        tag_card.pack(fill="x", padx=28, pady=(0, 24))
        tag_head = tk.Frame(tag_card, bg=p.surface)
        tag_head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(tag_head, text="科目分布", font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        tk.Label(tag_head, text="当前时间范围", font=self.t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left", padx=8)

        self.tag_box = tk.Frame(tag_card, bg=p.surface)
        self.tag_box.pack(fill="x", padx=18, pady=(8, 16))

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
        days = self.RANGES[self._range_index]
        series = self.app.stats.series(days)
        values = [minutes for _, minutes in series]
        goal = max(1, self.app.store.settings.goal_min)
        total = sum(values)
        average = total / len(values) if values else 0
        met = sum(1 for value in values if value >= goal)

        self.s_total.configure(text=self.app.fmt(total))
        self.s_avg.configure(text=self.app.fmt(average))
        self.s_met.configure(text=f"{met} 天")
        self.s_streak.configure(text=f"{self.app.stats.longest_streak()} 天")

        self._series = series
        self._goal = goal
        self._draw_chart()
        self.heatmap.render(self.app.stats.heatmap_cells(12), goal)
        self._render_tags(series)

    def _on_range(self, index):
        self._range_index = index
        self.refresh()

    # ------------------------------------------------------------ 趋势图
    def _draw_chart(self):
        canvas = self.chart
        canvas.delete("all")
        if not self._series:
            return

        canvas.update_idletasks()
        width = canvas.winfo_width() or 700
        height = int(canvas.cget("height"))
        p = self.t.p

        pad_l, pad_r, pad_t, pad_b = 38, 16, 16, 30
        plot_w = width - pad_l - pad_r
        plot_h = height - pad_t - pad_b
        if plot_w <= 20 or plot_h <= 20:
            return

        values = [minutes for _, minutes in self._series]
        max_value = max(values + [self._goal, 1])

        for i in range(4):
            y = pad_t + plot_h * i / 3
            canvas.create_line(pad_l, y, width - pad_r, y, fill=p.border)
            canvas.create_text(pad_l - 6, y, text=str(int(max_value * (3 - i) / 3)),
                               anchor="e", fill=p.muted, font=self.t.font_sm)

        count = len(self._series)
        slot = plot_w / count
        bar_w = min(30, slot * 0.55)

        for i, (day, value) in enumerate(self._series):
            x = pad_l + slot * i + (slot - bar_w) / 2
            base_y = pad_t + plot_h
            bar_h = plot_h * value / max_value
            color = p.success if value >= self._goal else p.primary

            if value > 0:
                round_rect(canvas, x, base_y - bar_h, x + bar_w, base_y,
                           6, fill=color, outline="")
                canvas.create_text(x + bar_w / 2, base_y - bar_h - 8, text=str(int(value)),
                                   fill=p.text, font=self.t.font_sm)
            if count <= 14 or i % 3 == 0 or i == count - 1:
                canvas.create_text(x + bar_w / 2, base_y + 12, text=day[5:],
                                   fill=p.muted, font=self.t.font_sm)

        goal_y = pad_t + plot_h * (1 - self._goal / max_value)
        canvas.create_line(pad_l, goal_y, width - pad_r, goal_y,
                           fill=p.warning, dash=(6, 4))

    # ------------------------------------------------------------ 热力图提示
    def _on_heat_hover(self, day, minutes):
        if not day:
            self.heat_hint.configure(text=" ")
        elif minutes is None:
            self.heat_hint.configure(text=f"{day} · 未到")
        else:
            self.heat_hint.configure(text=f"{day} · {self.app.fmt(minutes)}")

    # ------------------------------------------------------------ 科目分布
    def _render_tags(self, series):
        p = self.t.p
        for widget in self.tag_box.winfo_children():
            widget.destroy()

        day_set = {day for day, _ in series}
        totals = self.app.stats.tag_totals(day_set)
        if not totals:
            tk.Label(self.tag_box, text="当前范围暂无数据", font=self.t.font,
                     bg=p.surface, fg=p.muted).pack(anchor="w", pady=8)
            return

        max_value = max(totals.values()) or 1
        for tag, value in sorted(totals.items(), key=lambda item: -item[1])[:6]:
            row = tk.Frame(self.tag_box, bg=p.surface)
            row.pack(fill="x", pady=4)

            tk.Label(row, text=tag, font=self.t.font_sm, bg=p.surface,
                     fg=p.text, width=10, anchor="w").pack(side="left")

            bar = tk.Canvas(row, width=200, height=10, bg=p.surface, highlightthickness=0)
            bar.pack(side="left", padx=8)
            round_rect(bar, 0, 1, 200, 9, 5, fill=p.surface_alt, outline="")
            round_rect(bar, 0, 1, max(8, int(200 * value / max_value)), 9, 5,
                       fill=p.primary, outline="")

            tk.Label(row, text=self.app.fmt(value), font=self.t.font_sm,
                     bg=p.surface, fg=p.muted).pack(side="left")
