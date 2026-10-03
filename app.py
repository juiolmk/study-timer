# -*- coding: utf-8 -*-
"""
学习计时打卡桌面软件 —— 简洁明亮版（第一版）
- 标准 Tkinter 窗口，白底卡片、简洁明亮
- 首页（计时打卡 / 今日概览）/ 记录 / 统计 / 设置
数据保存在 %APPDATA%/StudyTimer/study_data.json

运行：python app.py
打包：build.bat  （或 pyinstaller --onefile --windowed --name 学习打卡 app.py）
"""

import os
import json
import time
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

# ---------- 主题 ----------
APP_BG   = "#eef2f7"   # 应用整体背景（浅灰蓝）
CARD_BG  = "#ffffff"   # 卡片背景（白）
TEXT     = "#1f2933"
SUBTEXT  = "#52606d"
PRIMARY  = "#2f80ed"
SUCCESS  = "#27ae60"
WARNING  = "#e67e22"
DANGER   = "#e74c3c"
BORDER   = "#dbe3ec"   # 卡片/分隔边框
PANEL    = "#dbe7fb"   # 选中/高亮填充

FONT      = ("Microsoft YaHei", 10)
FONT_BOLD = ("Microsoft YaHei", 10, "bold")
FONT_TITLE= ("Microsoft YaHei", 13, "bold")
FONT_BIG  = ("Microsoft YaHei", 30, "bold")
FONT_HUGE = ("Microsoft YaHei", 46, "bold")

DATA_DIR  = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "StudyTimer")
DATA_FILE = os.path.join(DATA_DIR, "study_data.json")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("学习打卡")
        self.root.geometry("880x600")
        self.root.minsize(720, 480)
        self.root.configure(bg=APP_BG)

        self.data = self.load_data()

        self.timer_running = False
        self.timer_paused = False
        self.timer_start = 0.0
        self.timer_acc = 0.0
        self.timer_after_id = None

        self.build_ui()
        self.show_page("home")

        self.root.after(60000, self.reminder_loop)

    # ============ 数据层 ============
    def load_data(self):
        default = {
            "goal_min": 60, "remind": False, "remind_time": "21:00",
            "records": [], "checkins": {},
            "last_remind_date": "", "last_goal_date": "",
        }
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                for k, v in default.items():
                    d.setdefault(k, v)
                return d
            except Exception:
                return default
        return default

    def save_data(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入数据文件：\n{e}")

    # ============ 工具 ============
    @staticmethod
    def today_str():
        return date.today().isoformat()

    def daily_minutes(self, date_str):
        return sum(r["durationMin"] for r in self.data["records"] if r["date"] == date_str)

    def compute_streak(self):
        dates = set(self.data["checkins"].keys())
        if not dates:
            return 0
        d = date.today()
        if self.today_str() not in dates:
            d = d - timedelta(days=1)
        count = 0
        while d.isoformat() in dates:
            count += 1
            d = d - timedelta(days=1)
        return count

    def longest_streak(self):
        dates = sorted(self.data["checkins"].keys())
        if not dates:
            return 0
        best = cur = 1
        for i in range(1, len(dates)):
            prev = datetime.strptime(dates[i - 1], "%Y-%m-%d").date()
            now = datetime.strptime(dates[i], "%Y-%m-%d").date()
            if (now - prev).days == 1:
                cur += 1
                best = max(best, cur)
            else:
                cur = 1
        return best

    @staticmethod
    def fmt_duration(mins):
        mins = int(round(mins))
        h, m = divmod(mins, 60)
        if h:
            return f"{h}小时{m}分" if m else f"{h}小时"
        return f"{m}分"

    @staticmethod
    def fmt_clock(seconds):
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ============ 顶栏（装饰）+ 页面容器 + 底部导航 ============
    def build_ui(self):
        header = tk.Frame(self.root, bg=APP_BG)
        header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="📚 学习打卡", font=FONT_TITLE, bg=APP_BG, fg=PRIMARY).pack(
            side=tk.LEFT, padx=16, pady=12)

        self.pages = {}
        self.pages["home"] = tk.Frame(self.root, bg=APP_BG)
        self.pages["records"] = tk.Frame(self.root, bg=APP_BG)
        self.pages["stats"] = tk.Frame(self.root, bg=APP_BG)
        self.pages["settings"] = tk.Frame(self.root, bg=APP_BG)
        self.build_home()
        self.build_records()
        self.build_stats()
        self.build_settings()

        nav = tk.Frame(self.root, bg=APP_BG)
        nav.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 12))
        self.nav_buttons = {}
        for key, label in [("home", "首页"), ("records", "记录"), ("stats", "统计"), ("settings", "设置")]:
            b = tk.Button(nav, text=label, font=FONT_BOLD, bd=0, padx=22, pady=8,
                          bg=APP_BG, fg=SUBTEXT, activebackground="#cfe0f5",
                          command=lambda k=key: self.show_page(k))
            b.pack(side=tk.LEFT, padx=6, expand=True)
            self.nav_buttons[key] = b

    def show_page(self, key):
        for k, f in self.pages.items():
            if k == key:
                f.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
            else:
                f.pack_forget()
        for k, b in self.nav_buttons.items():
            b.configure(fg=PRIMARY if k == key else SUBTEXT,
                        bg="#cfe0f5" if k == key else APP_BG)
        if key == "home":
            self.refresh_home()
        elif key == "records":
            self.refresh_records()
        elif key == "stats":
            self.refresh_stats()

    # ============ 首页 ============
    def build_home(self):
        p = self.pages["home"]
        tk.Label(p, text="今日学习计时", font=FONT_TITLE, bg=APP_BG, fg=TEXT).pack(pady=(20, 2))
        self.clock_label = tk.Label(p, text="00:00:00", font=FONT_HUGE, bg=APP_BG, fg=PRIMARY)
        self.clock_label.pack(pady=(4, 16))

        self.btn_start = tk.Button(p, text="▶ 开始学习", font=FONT_BOLD, bg=PRIMARY, fg="white",
                                   bd=0, padx=30, pady=12, activebackground="#1f6fd6", command=self.on_start)
        self.btn_start.pack()
        self.btn_pause = tk.Button(p, text="⏸ 暂停", font=FONT_BOLD, bg=WARNING, fg="white",
                                   bd=0, padx=22, pady=10, activebackground="#cf6f17", command=self.on_pause)
        self.btn_stop = tk.Button(p, text="⏹ 结束并打卡", font=FONT_BOLD, bg=SUCCESS, fg="white",
                                  bd=0, padx=22, pady=10, activebackground="#1e9e54", command=self.on_stop)
        self._pause_stop_visible(False)

        cards = tk.Frame(p, bg=APP_BG)
        cards.pack(fill=tk.X, pady=(24, 4))
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")
        self.card_date = self.make_card(cards, "今天", "", 0)
        self.card_today = self.make_card(cards, "今日已学", "0 分", 1)
        self.card_streak = self.make_card(cards, "连续打卡", "0 天", 2)

        ring_frame = tk.Frame(p, bg=APP_BG)
        ring_frame.pack(fill=tk.X, pady=(16, 0))
        tk.Label(ring_frame, text="每日目标完成度", font=FONT_TITLE, bg=APP_BG, fg=TEXT).pack(pady=(6, 2))
        self.ring_canvas = tk.Canvas(ring_frame, width=170, height=170, bg=APP_BG, highlightthickness=0)
        self.ring_canvas.pack(pady=(0, 4))

    def make_card(self, parent, title, value, col):
        c = tk.Frame(parent, bg=CARD_BG, bd=1, relief="solid",
                     highlightbackground=BORDER, highlightthickness=1)
        c.grid(row=0, column=col, padx=8, sticky="ew")
        tk.Label(c, text=title, font=FONT, bg=CARD_BG, fg=SUBTEXT).pack(pady=(10, 0))
        val = tk.Label(c, text=value, font=("Microsoft YaHei", 20, "bold"), bg=CARD_BG, fg=PRIMARY)
        val.pack(pady=(0, 10))
        return val

    def _pause_stop_visible(self, visible):
        if visible:
            self.btn_pause.pack(pady=(10, 0))
            self.btn_stop.pack(pady=(8, 0))
        else:
            self.btn_pause.pack_forget()
            self.btn_stop.pack_forget()

    def refresh_home(self):
        self.card_date.configure(text=date.today().strftime("%Y-%m-%d"))
        self.card_today.configure(text=self.fmt_duration(self.daily_minutes(self.today_str())))
        self.card_streak.configure(text=f"{self.compute_streak()} 天")
        self.draw_ring(self.daily_minutes(self.today_str()))

    def draw_ring(self, today_min):
        c = self.ring_canvas
        c.delete("all")
        goal = max(1, int(self.data["goal_min"]))
        ratio = min(1.0, today_min / goal)
        cx, cy, r = 85, 85, 64
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=360,
                     style=tk.ARC, width=15, outline="#c7d2e0")
        color = SUCCESS if ratio >= 1 else PRIMARY
        if ratio > 0:
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-360 * ratio,
                         style=tk.ARC, width=15, outline=color)
        pct = int(ratio * 100)
        c.create_text(cx, cy - 6, text=f"{pct}%", font=("Microsoft YaHei", 22, "bold"), fill=TEXT)
        c.create_text(cx, cy + 20, text=f"{int(today_min)}/{goal} 分", font=FONT, fill=SUBTEXT)

    # ============ 计时逻辑 ============
    def on_start(self):
        if self.timer_running and not self.timer_paused:
            return
        if self.timer_paused:
            self.timer_paused = False
            self.timer_start = time.time()
        else:
            self.timer_running = True
            self.timer_acc = 0.0
            self.timer_start = time.time()
        self.btn_start.pack_forget()
        self._pause_stop_visible(True)
        self.btn_pause.configure(text="⏸ 暂停")
        self.tick()

    def on_pause(self):
        if not self.timer_running:
            return
        if self.timer_paused:
            self.timer_paused = False
            self.timer_start = time.time()
            self.btn_pause.configure(text="⏸ 暂停")
        else:
            self.timer_paused = True
            self.timer_acc += time.time() - self.timer_start
            self.btn_pause.configure(text="▶ 继续")

    def on_stop(self):
        if not self.timer_running:
            return
        if self.timer_after_id:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None
        if not self.timer_paused:
            self.timer_acc += time.time() - self.timer_start
        total = self.timer_acc
        self.timer_running = False
        self.timer_paused = False
        self.timer_acc = 0.0
        self.clock_label.configure(text="00:00:00")
        self.btn_start.pack()
        self._pause_stop_visible(False)
        if total < 5:
            messagebox.showinfo("提示", "时长太短，未记录。")
            return
        self.open_save_dialog(total)

    def tick(self):
        if self.timer_running and not self.timer_paused:
            elapsed = self.timer_acc + (time.time() - self.timer_start)
            self.clock_label.configure(text=self.fmt_clock(elapsed))
        self.timer_after_id = self.root.after(1000, self.tick)

    # ============ 保存/编辑记录弹窗 ============
    def open_save_dialog(self, total_seconds, record=None):
        dur_min = int(round(total_seconds / 60))
        win = tk.Toplevel(self.root)
        win.title("保存学习记录" if record is None else "编辑学习记录")
        win.geometry("420x330")
        win.configure(bg="#ffffff")
        win.grab_set()
        win.resizable(False, False)

        if record is None:
            rec_date = self.today_str()
            rec_start = datetime.now().strftime("%H:%M")
            rec_dur = dur_min
            rec_title = ""
            rec_note = ""
        else:
            rec_date = record["date"]
            rec_start = (record.get("start") or rec_date + " 00:00")[-5:]
            rec_dur = record["durationMin"]
            rec_title = record.get("title", "")
            rec_note = record.get("note", "")

        tk.Label(win, text="日期 (YYYY-MM-DD)", font=FONT, bg="#ffffff", fg=TEXT).pack(anchor="w", padx=20, pady=(14, 2))
        e_date = tk.Entry(win, font=FONT); e_date.insert(0, rec_date); e_date.pack(fill=tk.X, padx=20)
        tk.Label(win, text="开始时间 (HH:MM)", font=FONT, bg="#ffffff", fg=TEXT).pack(anchor="w", padx=20, pady=(8, 2))
        e_start = tk.Entry(win, font=FONT); e_start.insert(0, rec_start); e_start.pack(fill=tk.X, padx=20)
        tk.Label(win, text="学习时长 (分钟)", font=FONT, bg="#ffffff", fg=TEXT).pack(anchor="w", padx=20, pady=(8, 2))
        e_dur = tk.Entry(win, font=FONT); e_dur.insert(0, str(rec_dur)); e_dur.pack(fill=tk.X, padx=20)
        tk.Label(win, text="学习内容标题", font=FONT, bg="#ffffff", fg=TEXT).pack(anchor="w", padx=20, pady=(8, 2))
        e_title = tk.Entry(win, font=FONT); e_title.insert(0, rec_title); e_title.pack(fill=tk.X, padx=20)
        tk.Label(win, text="备注", font=FONT, bg="#ffffff", fg=TEXT).pack(anchor="w", padx=20, pady=(8, 2))
        e_note = tk.Entry(win, font=FONT); e_note.insert(0, rec_note); e_note.pack(fill=tk.X, padx=20)

        def save():
            try:
                d = e_date.get().strip()
                datetime.strptime(d, "%Y-%m-%d")
            except Exception:
                messagebox.showerror("格式错误", "日期格式应为 YYYY-MM-DD", parent=win)
                return
            try:
                dm = int(e_dur.get().strip() or 0)
                if dm <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("格式错误", "时长须为正整数（分钟）", parent=win)
                return
            st = e_start.get().strip() or "00:00"
            start_full = f"{d} {st}"
            try:
                sdt = datetime.strptime(start_full, "%Y-%m-%d %H:%M")
            except Exception:
                messagebox.showerror("格式错误", "开始时间格式应为 HH:MM", parent=win)
                return
            end_dt = sdt + timedelta(minutes=dm)
            title = e_title.get().strip()
            note = e_note.get().strip()
            if record is None:
                self.data["records"].append({
                    "id": str(uuid.uuid4()), "date": d, "start": start_full,
                    "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                    "durationMin": dm, "title": title, "note": note,
                })
            else:
                record["date"] = d
                record["start"] = start_full
                record["end"] = end_dt.strftime("%Y-%m-%d %H:%M")
                record["durationMin"] = dm
                record["title"] = title
                record["note"] = note
            self.data["checkins"][d] = True
            self.save_data()
            win.destroy()
            messagebox.showinfo("已保存", "学习记录已保存，今日打卡 +1 👍")
            self.refresh_home()
            self.refresh_records()

        row = tk.Frame(win, bg="#ffffff")
        row.pack(fill=tk.X, padx=20, pady=(16, 10))
        tk.Button(row, text="保存", font=FONT_BOLD, bg=SUCCESS, fg="white", bd=0, padx=18, pady=8,
                  activebackground="#1e9e54", command=save).pack(side=tk.RIGHT, padx=6)
        tk.Button(row, text="取消", font=FONT_BOLD, bg="#b2bec3", fg="white", bd=0, padx=18, pady=8,
                  activebackground="#95a5a6", command=win.destroy).pack(side=tk.RIGHT)

    # ============ 记录页 ============
    def build_records(self):
        p = self.pages["records"]
        bar = tk.Frame(p, bg=APP_BG)
        bar.pack(fill=tk.X, pady=(6, 8))
        tk.Label(bar, text="搜索", font=FONT, bg=APP_BG, fg=TEXT).pack(side=tk.LEFT)
        self.rec_search = tk.Entry(bar, font=FONT, bg="#ffffff", bd=1, relief="solid",
                                   highlightthickness=1, highlightcolor=PRIMARY)
        self.rec_search.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        tk.Button(bar, text="查询", font=FONT_BOLD, bg=PRIMARY, fg="white", bd=0, padx=14, pady=5,
                  activebackground="#1f6fd6", command=self.refresh_records).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="＋", font=FONT_BOLD, bg=SUCCESS, fg="white", bd=0, padx=12, pady=5,
                  activebackground="#1e9e54", command=lambda: self.open_save_dialog(0)).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="✎", font=FONT_BOLD, bg="#b2bec3", fg="white", bd=0, padx=12, pady=5,
                  activebackground="#95a5a6", command=self.edit_selected).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="🗑", font=FONT_BOLD, bg=DANGER, fg="white", bd=0, padx=12, pady=5,
                  activebackground="#c0392b", command=self.delete_selected).pack(side=tk.RIGHT, padx=3)

        self.rec_canvas = tk.Canvas(p, bg=APP_BG, highlightthickness=0)
        sb = ttk.Scrollbar(p, orient=tk.VERTICAL, command=self.rec_canvas.yview)
        self.rec_canvas.configure(yscrollcommand=sb.set)
        self.rec_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_canvas.bind("<MouseWheel>", self.on_rec_wheel)
        self.rec_canvas.bind("<Button-1>", self.on_rec_click)
        self.rec_canvas.bind("<Double-1>", lambda e: self.edit_selected())
        self.rec_filtered = []
        self.rec_selected = None

    def refresh_records(self):
        kw = self.rec_search.get().strip().lower()
        recs = sorted(self.data["records"], key=lambda r: (r["date"], r.get("start", "")), reverse=True)
        if kw:
            recs = [r for r in recs if kw in (r.get("title", "") + r.get("note", "") + r["date"]).lower()]
        self.rec_filtered = recs
        self.draw_rows()

    def draw_rows(self):
        c = self.rec_canvas
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width() or 800
        ROW_H = 58
        for i, r in enumerate(self.rec_filtered):
            y0 = i * ROW_H
            if self.rec_selected == r["id"]:
                c.create_rectangle(0, y0, W, y0 + ROW_H - 6, fill=PANEL, outline="")
            title = r.get("title") or "(未命名)"
            sub = f"{r['date']}  {r.get('start', '-')} ~ {r.get('end', '-')}   ·   {r['durationMin']} 分"
            c.create_text(14, y0 + 14, text="📘 " + title, font=FONT_BOLD, fill=TEXT, anchor="w")
            c.create_text(14, y0 + 38, text=sub, font=FONT, fill=SUBTEXT, anchor="w")
            note = r.get("note", "")
            if note:
                c.create_text(W - 14, y0 + 38, text="备注:" + note, font=FONT, fill=SUBTEXT, anchor="e")
        total_h = max(len(self.rec_filtered) * ROW_H, 1)
        c.configure(scrollregion=(0, 0, W, total_h))

    def on_rec_wheel(self, e):
        self.rec_canvas.yview_scroll(-1 * (e.delta // 120), "units")

    def on_rec_click(self, e):
        if not self.rec_filtered:
            return
        region = self.rec_canvas.cget("scrollregion").split()
        H = int(region[3]) if len(region) == 4 else 0
        top = self.rec_canvas.yview()[0] * H
        idx = int((e.y + top) // 58)
        if 0 <= idx < len(self.rec_filtered):
            self.rec_selected = self.rec_filtered[idx]["id"]
            self.draw_rows()

    def get_selected_record(self):
        if not self.rec_selected:
            messagebox.showinfo("提示", "请先选择一条记录")
            return None
        for r in self.data["records"]:
            if r["id"] == self.rec_selected:
                return r
        return None

    def edit_selected(self):
        r = self.get_selected_record()
        if r:
            self.open_save_dialog(0, record=r)

    def delete_selected(self):
        r = self.get_selected_record()
        if not r:
            return
        if not messagebox.askyesno("确认删除", f"确定删除「{r.get('title') or r['date']}」这条记录吗？"):
            return
        self.data["records"].remove(r)
        d = r["date"]
        if self.daily_minutes(d) == 0:
            self.data["checkins"].pop(d, None)
        self.save_data()
        self.rec_selected = None
        self.refresh_records()
        self.refresh_home()
        messagebox.showinfo("已删除", "记录已删除")

    # ============ 统计页 ============
    def build_stats(self):
        p = self.pages["stats"]
        bar = tk.Frame(p, bg=APP_BG)
        bar.pack(fill=tk.X, pady=(6, 8))
        tk.Label(bar, text="时间范围", font=FONT, bg=APP_BG, fg=TEXT).pack(side=tk.LEFT)
        self.range_var = tk.StringVar(value="7")
        ttk.Combobox(bar, textvariable=self.range_var, values=["7", "14", "30"],
                     width=6, state="readonly", font=FONT).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="刷新", font=FONT_BOLD, bg=PRIMARY, fg="white", bd=0, padx=14, pady=5,
                  activebackground="#1f6fd6", command=self.refresh_stats).pack(side=tk.LEFT, padx=4)

        sumf = tk.Frame(p, bg=APP_BG)
        sumf.pack(fill=tk.X, pady=(0, 8))
        sumf.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="s")
        self.s_total = self.make_card(sumf, "累计时长", "0", 0)
        self.s_avg = self.make_card(sumf, "日均时长", "0", 1)
        self.s_met = self.make_card(sumf, "达标天数", "0", 2)
        self.s_streak = self.make_card(sumf, "最长连续", "0 天", 3)

        self.chart = tk.Canvas(p, bg=APP_BG, highlightthickness=0)
        self.chart.pack(fill=tk.BOTH, expand=True)

    def refresh_stats(self):
        n = int(self.range_var.get())
        goal = max(1, int(self.data["goal_min"]))
        today = date.today()
        days = [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]
        vals = [self.daily_minutes(d) for d in days]
        total = sum(vals)
        met = sum(1 for v in vals if v >= goal)
        avg = total / n if n else 0
        self.s_total.configure(text=self.fmt_duration(total))
        self.s_avg.configure(text=self.fmt_duration(avg))
        self.s_met.configure(text=f"{met} 天")
        self.s_streak.configure(text=f"{self.longest_streak()} 天")
        self.draw_chart(days, vals, goal)

    def draw_chart(self, days, vals, goal):
        c = self.chart
        c.update_idletasks()
        w = c.winfo_width() or 700
        h = c.winfo_height() or 300
        c.delete("all")
        pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 40
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b
        maxv = max(vals + [goal, 1])
        for i in range(5):
            y = pad_t + plot_h * i / 4
            c.create_line(pad_l, y, w - pad_r, y, fill="#c7d2e0")
            c.create_text(pad_l - 6, y, text=str(int(maxv * (4 - i) / 4)),
                          font=FONT, fill=SUBTEXT, anchor="e")
        n = len(days)
        gap = plot_w / n
        bw = gap * 0.6
        for i, (d, v) in enumerate(zip(days, vals)):
            x = pad_l + gap * i + (gap - bw) / 2
            bh = plot_h * v / maxv if maxv else 0
            y0 = pad_t + plot_h
            color = SUCCESS if v >= goal else PRIMARY
            c.create_rectangle(x, y0 - bh, x + bw, y0, fill=color, outline="")
            if n <= 14 or i % 3 == 0 or i == n - 1:
                c.create_text(x + bw / 2, y0 + 12, text=d[5:], font=("Microsoft YaHei", 8), fill=SUBTEXT)
            if v > 0:
                c.create_text(x + bw / 2, y0 - bh - 8, text=str(int(v)), font=("Microsoft YaHei", 8), fill=TEXT)
        gy = pad_t + plot_h * (1 - goal / maxv) if maxv else pad_t
        c.create_line(pad_l, gy, w - pad_r, gy, fill=WARNING, dash=(6, 4))
        c.create_text(w - pad_r + 2, gy, text="目标", font=FONT, fill=WARNING, anchor="w")

    # ============ 设置页 ============
    def build_settings(self):
        p = self.pages["settings"]
        tk.Label(p, text="每日目标（分钟）", font=FONT_BOLD, bg=APP_BG, fg=TEXT).pack(anchor="w", padx=4, pady=(8, 2))
        self.goal_entry = tk.Entry(p, font=FONT, bg="#ffffff", bd=1, relief="solid",
                                   highlightthickness=1, highlightcolor=PRIMARY, width=12)
        self.goal_entry.insert(0, str(self.data["goal_min"]))
        self.goal_entry.pack(anchor="w", padx=4)

        self.remind_var = tk.BooleanVar(value=bool(self.data["remind"]))
        rrow = tk.Frame(p, bg=APP_BG)
        rrow.pack(anchor="w", padx=4, pady=(14, 2))
        tk.Checkbutton(rrow, text="启用定点提醒", variable=self.remind_var, font=FONT_BOLD,
                       bg=APP_BG, fg=TEXT, activebackground=APP_BG).pack(side=tk.LEFT)
        tk.Label(rrow, text="提醒时间", font=FONT, bg=APP_BG, fg=TEXT).pack(side=tk.LEFT, padx=(10, 2))
        self.remind_time = tk.Entry(rrow, font=FONT, bg="#ffffff", bd=1, relief="solid",
                                    highlightthickness=1, highlightcolor=PRIMARY, width=8)
        self.remind_time.insert(0, self.data["remind_time"])
        self.remind_time.pack(side=tk.LEFT)

        tk.Button(p, text="保存设置", font=FONT_BOLD, bg=PRIMARY, fg="white", bd=0, padx=18, pady=9,
                  activebackground="#1f6fd6", command=self.save_settings).pack(anchor="w", padx=4, pady=(16, 4))

        tk.Label(p, text="数据管理", font=FONT_BOLD, bg=APP_BG, fg=TEXT).pack(anchor="w", padx=4, pady=(14, 4))
        drow = tk.Frame(p, bg=APP_BG)
        drow.pack(anchor="w", padx=4)
        tk.Button(drow, text="导出数据", font=FONT_BOLD, bg=SUCCESS, fg="white", bd=0, padx=14, pady=8,
                  activebackground="#1e9e54", command=self.export_data).pack(side=tk.LEFT, padx=4)
        tk.Button(drow, text="导入数据", font=FONT_BOLD, bg=PRIMARY, fg="white", bd=0, padx=14, pady=8,
                  activebackground="#1f6fd6", command=self.import_data).pack(side=tk.LEFT, padx=4)
        tk.Button(drow, text="清空数据", font=FONT_BOLD, bg=DANGER, fg="white", bd=0, padx=14, pady=8,
                  activebackground="#c0392b", command=self.clear_data).pack(side=tk.LEFT, padx=4)

        tk.Label(p, text="提示：数据位于 " + DATA_FILE,
                 font=("Microsoft YaHei", 9), bg=APP_BG, fg=SUBTEXT, justify="left").pack(anchor="w", padx=4, pady=(14, 0))

    def save_settings(self):
        try:
            g = int(self.goal_entry.get().strip() or 0)
            if g <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("格式错误", "目标须为正整数（分钟）")
            return
        self.data["goal_min"] = g
        self.data["remind"] = self.remind_var.get()
        self.data["remind_time"] = self.remind_time.get().strip() or "21:00"
        self.save_data()
        self.refresh_home()
        messagebox.showinfo("已保存", "设置已保存")

    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON 文件", "*.json")], initialfile="study_data.json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"数据已导出到：\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not messagebox.askyesno("确认导入", "导入将覆盖当前所有数据，确定继续？"):
                return
            self.data = d
            self.save_data()
            self.refresh_home()
            self.refresh_records()
            self.refresh_stats()
            messagebox.showinfo("导入成功", "数据已导入")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def clear_data(self):
        if not messagebox.askyesno("确认清空", "将删除全部学习记录与打卡，且不可恢复！确定？"):
            return
        self.data["records"] = []
        self.data["checkins"] = {}
        self.data["last_remind_date"] = ""
        self.data["last_goal_date"] = ""
        self.save_data()
        self.rec_selected = None
        self.refresh_home()
        self.refresh_records()
        self.refresh_stats()
        messagebox.showinfo("已清空", "所有数据已清空")

    # ============ 提醒 ============
    def reminder_loop(self):
        self.check_reminders()
        self.root.after(60000, self.reminder_loop)

    def check_reminders(self):
        try:
            today = self.today_str()
            now = datetime.now()
            goal = max(1, int(self.data["goal_min"]))
            if self.data.get("remind"):
                rt = datetime.strptime(self.data.get("remind_time", "21:00"), "%H:%M").time()
                if now.time() >= rt and self.data.get("last_remind_date") != today:
                    if self.daily_minutes(today) < goal:
                        self.data["last_remind_date"] = today
                        self.save_data()
                        messagebox.showinfo("学习提醒 🔔",
                            f"今天还没完成目标哦~\n目标 {goal} 分钟，目前仅 {int(self.daily_minutes(today))} 分钟。")
            if self.daily_minutes(today) >= goal and self.data.get("last_goal_date") != today:
                self.data["last_goal_date"] = today
                self.save_data()
                messagebox.showinfo("达成目标 🎉", f"今天已学习 {int(self.daily_minutes(today))} 分钟，达标！继续保持~")
        except Exception:
            pass


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
