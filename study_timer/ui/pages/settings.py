# -*- coding: utf-8 -*-
"""设置页：学习目标、提醒、番茄钟、外观、数据管理。"""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from ...config import DATA_DIR, VERSION
from ..widgets import Card, RoundedButton, ScrollableFrame, Segmented, make_entry


class SettingsPage(tk.Frame):
    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme
        self._build()

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p
        settings = self.app.store.settings

        self.scroll = ScrollableFrame(self, self.t)
        self.scroll.pack(fill="both", expand=True)
        self.body = self.scroll.inner

        header = tk.Frame(self.body, bg=p.bg)
        header.pack(fill="x", padx=28, pady=(22, 12))
        tk.Label(header, text="设置", font=self.t.font_h1, bg=p.bg, fg=p.text).pack(side="left")

        # 学习目标
        form = self._section("学习目标", "每天想投入的时间，用于计算完成度")
        self.goal_var = tk.StringVar(value=str(settings.goal_min))
        goal_box = tk.Frame(form, bg=p.surface)
        goal_entry = make_entry(goal_box, self.t, width=8, textvariable=self.goal_var)
        goal_entry.pack(side="left")
        tk.Label(goal_box, text="分钟 / 天", font=self.t.font_sm,
                 bg=p.surface, fg=p.muted).pack(side="left", padx=8)
        self._row(form, 0, "每日目标", goal_box)

        # 提醒
        form = self._section("提醒", "到点未达标时提醒；达成目标时也会提示")
        self.remind_var = tk.BooleanVar(value=settings.remind)
        check = tk.Checkbutton(
            form, text="启用定点提醒", variable=self.remind_var,
            font=self.t.font, bg=p.surface, fg=p.text,
            activebackground=p.surface, activeforeground=p.text,
            selectcolor=p.surface_alt, bd=0, highlightthickness=0,
        )
        self._row(form, 0, "提醒开关", check)

        self.remind_time_var = tk.StringVar(value=settings.remind_time)
        time_entry = make_entry(form, self.t, width=8, textvariable=self.remind_time_var)
        self._row(form, 1, "提醒时间", time_entry)

        # 番茄钟
        form = self._section("番茄钟", "首页选择预设后即进入倒计时")
        self.preset_var = tk.StringVar(value=str(settings.focus_preset))
        preset = ttk.Combobox(
            form, textvariable=self.preset_var, state="readonly",
            values=["25", "45", "60"], width=6, font=self.t.font,
        )
        self._row(form, 0, "默认专注时长", preset)

        # 外观
        form = self._section("外观", "切换后会立即应用")
        theme_index = 1 if settings.theme == "dark" else 0
        self.theme_seg = Segmented(
            form, self.t, ["浅色", "深色"], self._on_theme, index=theme_index,
        )
        self._row(form, 0, "主题", self.theme_seg)

        # 数据管理
        form = self._section("数据管理", "数据保存于 " + DATA_DIR)
        buttons = tk.Frame(form, bg=p.surface)
        RoundedButton(buttons, self.t, "导出", command=self._export,
                      variant="success", height=36).pack(side="left")
        RoundedButton(buttons, self.t, "导入", command=self._import,
                      height=36).pack(side="left", padx=8)
        RoundedButton(buttons, self.t, "打开文件夹", command=self._open_folder,
                      variant="ghost", height=36).pack(side="left")
        RoundedButton(buttons, self.t, "清空数据", command=self._clear,
                      variant="danger", height=36).pack(side="left", padx=8)
        self._row(form, 0, "备份 / 恢复", buttons)

        # 保存
        footer = tk.Frame(self.body, bg=p.bg)
        footer.pack(fill="x", padx=28, pady=(4, 10))
        RoundedButton(footer, self.t, "保存设置", command=self._save).pack(side="left")
        tk.Label(footer, text=f"v{VERSION}", font=self.t.font_sm,
                 bg=p.bg, fg=p.muted).pack(side="right")

        tip = tk.Label(
            self.body,
            text="提示：空格键可快速开始 / 暂停计时；记录支持自定义标签（科目）。",
            font=self.t.font_sm, bg=p.bg, fg=p.muted, justify="left",
        )
        tip.pack(anchor="w", padx=28, pady=(0, 24))

    def _section(self, title, subtitle=""):
        p = self.t.p
        card = Card(self.body, self.t)
        card.pack(fill="x", padx=28, pady=(0, 12))

        head = tk.Frame(card, bg=p.surface)
        head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(head, text=title, font=self.t.font_h2,
                 bg=p.surface, fg=p.text).pack(side="left")
        if subtitle:
            tk.Label(head, text=subtitle, font=self.t.font_sm,
                     bg=p.surface, fg=p.muted).pack(side="left", padx=8)

        form = tk.Frame(card, bg=p.surface)
        form.pack(fill="x", padx=18, pady=(8, 16))
        form.grid_columnconfigure(1, weight=1)
        return form

    def _row(self, form, row, label, widget):
        p = self.t.p
        tk.Label(form, text=label, font=self.t.font_sm, bg=p.surface,
                 fg=p.muted).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=6)
        widget.grid(row=row, column=1, sticky="w", pady=6)

    # ------------------------------------------------------------ 主题
    def _on_theme(self, index):
        self.app.set_theme("dark" if index == 1 else "light")

    # ------------------------------------------------------------ 保存
    def _save(self):
        try:
            goal = int(self.goal_var.get().strip())
            if goal <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("格式错误", "每日目标须为正整数（分钟）")
            return

        remind_time = self.remind_time_var.get().strip() or "21:00"
        try:
            datetime.strptime(remind_time, "%H:%M")
        except Exception:
            messagebox.showerror("格式错误", "提醒时间格式应为 HH:MM")
            return

        settings = self.app.store.settings
        settings.goal_min = goal
        settings.remind = bool(self.remind_var.get())
        settings.remind_time = remind_time
        try:
            settings.focus_preset = int(self.preset_var.get())
        except Exception:
            settings.focus_preset = 25

        self.app.repo.save(self.app.store)
        self.app.refresh_all()
        self.app.toast("设置已保存")

    # ------------------------------------------------------------ 数据
    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON 文件", "*.json")],
            initialfile="study_data.json",
        )
        if not path:
            return
        try:
            self.app.repo.export(self.app.store, path)
            messagebox.showinfo("导出成功", f"数据已导出到：\n{path}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            store = self.app.repo.import_file(path)
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))
            return

        if not messagebox.askyesno("确认导入", "导入将覆盖当前所有数据，确定继续？"):
            return
        self.app.replace_store(store)
        messagebox.showinfo("导入成功", "数据已导入")

    def _open_folder(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            os.startfile(DATA_DIR)
        except Exception as exc:
            messagebox.showerror("无法打开", str(exc))

    def _clear(self):
        if not messagebox.askyesno("确认清空", "将删除全部学习记录与打卡，且不可恢复！确定？"):
            return
        self.app.store.records = []
        self.app.store.checkins = set()
        self.app.store.settings.last_remind_date = ""
        self.app.store.settings.last_goal_date = ""
        self.app.repo.save(self.app.store)
        self.app.refresh_all()
        messagebox.showinfo("已清空", "所有学习记录已清空")
