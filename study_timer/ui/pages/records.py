# -*- coding: utf-8 -*-
"""记录页：搜索、按标签筛选、增删改。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..widgets import Card, RoundedButton, ScrollableFrame, make_entry


class RecordsPage(tk.Frame):
    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme
        self._build()
        self.refresh()

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p

        header = tk.Frame(self, bg=p.bg)
        header.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(header, text="学习记录", font=self.t.font_h1, bg=p.bg, fg=p.text).pack(side="left")
        self.count_label = tk.Label(header, text="", font=self.t.font_sm, bg=p.bg, fg=p.muted)
        self.count_label.pack(side="left", padx=12, pady=(10, 0))

        toolbar = tk.Frame(self, bg=p.bg)
        toolbar.pack(fill="x", padx=28, pady=(0, 10))

        self.search_var = tk.StringVar()
        search = make_entry(toolbar, self.t, textvariable=self.search_var)
        search.pack(side="left", fill="x", expand=True)
        search.bind("<KeyRelease>", lambda _e: self.refresh())

        self.tag_var = tk.StringVar(value="全部标签")
        self.tag_combo = ttk.Combobox(
            toolbar, textvariable=self.tag_var, state="readonly",
            font=self.t.font, width=12,
        )
        self.tag_combo.pack(side="left", padx=8)
        self.tag_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        RoundedButton(toolbar, self.t, "＋ 补记", command=self.app.open_quick_record_dialog,
                      variant="success", height=38).pack(side="left")

        self.list = ScrollableFrame(self, self.t)
        self.list.pack(fill="both", expand=True, padx=28, pady=(0, 18))

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        p = self.t.p
        self._update_tag_values()

        keyword = self.search_var.get().strip().lower()
        tag = self.tag_var.get()

        records = sorted(self.app.store.records,
                         key=lambda r: (r.date, r.start), reverse=True)
        if keyword:
            records = [
                r for r in records
                if keyword in f"{r.title} {r.note} {r.tag} {r.date}".lower()
            ]
        if tag and tag != "全部标签":
            records = [r for r in records if (r.tag.strip() or "未分类") == tag]

        self.count_label.configure(text=f"共 {len(records)} 条")

        for widget in self.list.inner.winfo_children():
            widget.destroy()

        if not records:
            empty = tk.Label(
                self.list.inner, text="没有匹配的记录", font=self.t.font,
                bg=p.bg, fg=p.muted, pady=40,
            )
            empty.pack(fill="x")
            return

        for record in records:
            self._row(record)

    def _update_tag_values(self):
        tags = ["全部标签"] + self.app.store.tags()
        self.tag_combo.configure(values=tags)
        if self.tag_var.get() not in tags:
            self.tag_var.set("全部标签")

    def _row(self, record):
        p = self.t.p
        card = Card(self.list.inner, self.t)
        card.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(card, bg=p.surface)
        inner.pack(fill="x", padx=16, pady=12)

        left = tk.Frame(inner, bg=p.surface)
        left.pack(side="left", fill="x", expand=True)

        top = tk.Frame(left, bg=p.surface)
        top.pack(anchor="w")
        tk.Label(top, text=record.title or "(未命名)", font=self.t.font_bold,
                 bg=p.surface, fg=p.text).pack(side="left")
        tk.Label(top, text=record.tag.strip() or "未分类", font=self.t.font_sm,
                 bg=p.surface_alt, fg=p.primary, padx=8, pady=1).pack(side="left", padx=8)

        subtitle = f"{record.date}  {self._hhmm(record.start)} - {self._hhmm(record.end)}"
        if record.note:
            subtitle += f"  ·  {record.note}"
        tk.Label(left, text=subtitle, font=self.t.font_sm, bg=p.surface, fg=p.muted).pack(
            anchor="w", pady=(4, 0))

        right = tk.Frame(inner, bg=p.surface)
        right.pack(side="right")
        tk.Label(right, text=self.app.fmt(record.duration_min), font=self.t.font_bold,
                 bg=p.surface, fg=p.primary).pack(side="left", padx=(0, 14))

        edit = tk.Label(right, text="编辑", font=self.t.font_sm, bg=p.surface,
                        fg=p.muted, cursor="hand2", padx=6)
        edit.pack(side="left")
        edit.bind("<Button-1>", lambda _e: self.app.open_record_dialog(record=record))

        delete = tk.Label(right, text="删除", font=self.t.font_sm, bg=p.surface,
                          fg=p.danger, cursor="hand2", padx=6)
        delete.pack(side="left")
        delete.bind("<Button-1>", lambda _e: self._delete(record))

    @staticmethod
    def _hhmm(text):
        if not text:
            return "-"
        return text[-5:] if len(text) >= 5 else text

    # ------------------------------------------------------------ 删除
    def _delete(self, record):
        label = record.title or record.date
        if not messagebox.askyesno("确认删除", f"确定删除「{label}」这条记录吗？"):
            return

        self.app.store.records.remove(record)
        day = record.date
        if self.app.stats.minutes_on(day) == 0:
            self.app.store.checkins.discard(day)

        self.app.repo.save(self.app.store)
        self.app.refresh_all()
