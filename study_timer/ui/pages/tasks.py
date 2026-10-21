# -*- coding: utf-8 -*-
"""任务页：今日任务清单，按优先级排序，点击任务直接开始计时。"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

from ...tasks import PRIORITY_LABELS
from ..widgets import Card, RoundedButton, ScrollableFrame, Segmented, make_entry


class TaskPage(tk.Frame):
    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme
        self._font_done = tkfont.Font(font=theme.font_bold)
        self._font_done.configure(overstrike=1)
        self._build()
        self.refresh()

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p

        header = tk.Frame(self, bg=p.bg)
        header.pack(fill="x", padx=32, pady=(22, 12))
        tk.Label(header, text="今日任务", font=self.t.font_h1,
                 bg=p.bg, fg=p.text).pack(side="left")
        self.count_label = tk.Label(header, text="", font=self.t.font_sm,
                                    bg=p.bg, fg=p.muted)
        self.count_label.pack(side="left", padx=12, pady=(10, 0))
        tk.Label(header, text="未完成的任务会自动顺延到明天",
                 font=self.t.font_sm, bg=p.bg, fg=p.muted).pack(
            side="right", pady=(10, 0))

        form_card = Card(self, self.t)
        form_card.pack(fill="x", padx=32, pady=(0, 12))
        form = tk.Frame(form_card, bg=p.surface)
        form.pack(fill="x", padx=18, pady=14)

        self.title_var = tk.StringVar()
        self.title_entry = make_entry(form, self.t, textvariable=self.title_var)
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.title_entry.bind("<Return>", lambda _e: self._add())

        self.priority_seg = Segmented(
            form, self.t, list(PRIORITY_LABELS), index=1)
        self.priority_seg.pack(side="left", padx=10)

        self.tag_var = tk.StringVar()
        tag_entry = make_entry(form, self.t, width=12, textvariable=self.tag_var)
        tag_entry.pack(side="left")
        tag_entry.bind("<Return>", lambda _e: self._add())

        RoundedButton(form, self.t, "添加任务", command=self._add,
                      variant="success", height=38, padx=16).pack(
            side="left", padx=10)

        self.list = ScrollableFrame(self, self.t)
        self.list.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        tasks = self.app.today_tasks()
        done = sum(1 for task in tasks if task.done)
        self.count_label.configure(text=f"{done}/{len(tasks)} 已完成")

        for widget in self.list.inner.winfo_children():
            widget.destroy()

        if not tasks:
            tk.Label(self.list.inner,
                     text="今天还没有任务，先写下最重要的一件。",
                     font=self.t.font, bg=self.t.p.bg,
                     fg=self.t.p.muted, pady=40).pack()
            return

        for task in tasks:
            self._task_row(task)

    def _task_row(self, task):
        p = self.t.p
        card = Card(self.list.inner, self.t)
        card.pack(fill="x", pady=(0, 8))

        row = tk.Frame(card, bg=p.surface)
        row.pack(fill="x", padx=14, pady=10)

        check = tk.Canvas(row, width=20, height=20, bg=p.surface,
                          highlightthickness=0, cursor="hand2")
        check.pack(side="left", padx=(0, 10))
        self._draw_check(check, task.done)
        check.bind("<Button-1>", lambda _e, t=task: self.app.toggle_task(t))

        color = self._priority_color(task.priority)
        pill = tk.Label(row, text=PRIORITY_LABELS[task.priority],
                        font=self.t.font_sm, bg=p.surface_alt, fg=color,
                        padx=8, pady=2, cursor="hand2")
        pill.pack(side="left", padx=(0, 8))
        pill.bind("<Button-1>", lambda _e, t=task: self.app.cycle_task_priority(t))

        title = tk.Label(
            row, text=task.title,
            font=self._font_done if task.done else self.t.font_bold,
            bg=p.surface, fg=p.muted if task.done else p.text,
            anchor="w", width=36,
        )
        title.pack(side="left", fill="x", expand=True)

        widgets_to_start = [row, title]

        if task.tag:
            tag = tk.Label(row, text=task.tag, font=self.t.font_sm,
                           bg=p.surface_alt, fg=p.primary, padx=8, pady=1)
            tag.pack(side="left", padx=6)
            widgets_to_start.append(tag)

        minutes = self.app.task_minutes(task)
        minutes_label = tk.Label(
            row, text=f"{minutes} 分" if minutes else "—",
            font=self.t.font_sm, bg=p.surface, fg=p.muted, width=7,
        )
        minutes_label.pack(side="left", padx=8)
        widgets_to_start.append(minutes_label)

        if task.done:
            tk.Label(row, text="已完成", font=self.t.font_sm,
                     bg=p.surface, fg=p.muted).pack(side="left", padx=8)
        else:
            start = tk.Label(row, text="▶ 开始", font=self.t.font_sm,
                             bg=p.surface, fg=p.primary, cursor="hand2")
            start.pack(side="left", padx=8)
            widgets_to_start.append(start)

        delete = tk.Label(row, text="删除", font=self.t.font_sm,
                          bg=p.surface, fg=p.muted, cursor="hand2")
        delete.pack(side="right", padx=(8, 0))
        delete.bind("<Button-1>", lambda _e, t=task: self._delete(t))

        for widget in widgets_to_start:
            widget.bind("<Button-1>", lambda _e, t=task: self._start(t))

    def _draw_check(self, canvas, done):
        p = self.t.p
        canvas.delete("all")
        if done:
            canvas.create_oval(2, 2, 18, 18, fill=p.success, outline="")
            canvas.create_line(6, 10, 9, 13, 14, 7, fill="#ffffff", width=2)
        else:
            canvas.create_oval(2, 2, 18, 18, outline=p.border, width=2)

    def _priority_color(self, priority):
        p = self.t.p
        return (p.danger, p.warning, p.muted)[max(0, min(2, priority))]

    # ------------------------------------------------------------ 操作
    def _add(self):
        title = self.title_var.get().strip()
        if not title:
            self.app.toast("先写任务内容")
            return
        if self.app.add_task(title, self.priority_seg.index,
                             self.tag_var.get().strip()):
            self.title_var.set("")
            self.tag_var.set("")
            self.title_entry.focus_set()
            self.app.toast("任务已添加")

    def _start(self, task):
        if self.app.start_task(task):
            self.app.show_page("home")

    def _delete(self, task):
        if messagebox.askyesno("删除任务",
                               f"删除「{task.title}」？\n已保存的学习记录不会删除。"):
            self.app.delete_task(task)
