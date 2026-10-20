# 学习打卡（StudyTimer）

一个用于**学习计时与习惯记录**的 Windows 桌面应用。现代化布局，支持浅色/深色主题，零第三方运行时依赖。

## 功能

- **计时 / 番茄钟**：自由正向计时，或 25 / 45 / 60 分钟倒计时；结束时自动弹出记录窗口，倒计时结束有提示音。
- **快速补记**：不启动计时也能 10 秒补一条记录；时长预设 15 / 25 / 45 / 60 分钟，自动带出上次标签，首页与记录页均可进入。
- **今日概览**：今日已学、连续打卡、目标完成度进度环、最近记录。
- **学习记录**：标题、标签（科目）、备注、起止时间；关键字搜索 + 标签筛选；补记 / 编辑 / 删除。
- **统计**：区间汇总（累计 / 日均 / 达标 / 最长连续）、趋势柱状图（7 / 14 / 30 天）、近 12 周学习热力图、科目分布。
- **设置**：每日目标、定点提醒、达成提醒、默认番茄钟时长、浅色 / 深色主题、全局快捷键开关、数据导出 JSON / CSV、导入 / 打开目录 / 清空。
- **全局快捷键**：`Ctrl+Alt+S` 在任意窗口（含应用最小化或失去焦点时）开始 / 暂停 / 继续计时，零第三方依赖，可在设置页关闭。
- **数据安全**：原子写入（临时文件 + 替换）、自动轮转备份（保留最近 7 份）、导入校验、旧版数据自动迁移；主文件损坏时启动自动从备份恢复并提示。

快捷键：`空格`（应用内）＋ `Ctrl+Alt+S`（全局）开始 / 暂停 / 继续计时。若 `Ctrl+Alt+S` 被其他程序占用，应用会自动降级为仅应用内快捷键，并在界面提示一次。

## 运行

需要 Python 3.10+（含 Tkinter，Windows 自带）。

```bash
python app.py
```

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖：计时器（秒表 / 倒计时 / 暂停 / 恢复）、统计（时长 / 连续 / 最长 / 序列 / 热力图 / 标签汇总）、存储（往返、v1 迁移、损坏回退、轮转备份保留 7 份、从轮转备份恢复、CSV 导出含中文/空数据、非法导入）、全局快捷键（注册 / 事件投递 / 幂等启动 / 停止后重启 / 重复停止 / 被占用降级）。当前共 27 项。

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name 学习打卡 --collect-submodules study_timer app.py
```

也可双击 `build.bat` 一键打包。产物：`dist/学习打卡.exe`。

## 数据

- 主文件：`%APPDATA%/StudyTimer/study_data.json`
- 单份备份：`%APPDATA%/StudyTimer/study_data.bak.json`（兼容旧版本）
- 轮转备份：`%APPDATA%/StudyTimer/backups/study_data-时间戳.json`，自动保留最近 7 份
- 启动时若主文件损坏或缺失，会依次回退到单份备份与最新轮转备份，并在界面提示“已从备份恢复”。
- 结构版本 `version: 2`；旧版（平铺 settings、`durationMin`、字典形式 checkins）读取时自动迁移。
- 设置页可导出 JSON 与 CSV（`utf-8-sig`，Excel 直接打开不乱码）、导入 JSON（含字段校验）。

## 目录结构

```
.
├── app.py                   # 入口（薄封装）
├── study_timer/
│   ├── config.py            # 路径与常量
│   ├── hotkey.py            # 全局快捷键（ctypes 调用 Win32，零依赖）
│   ├── models.py            # Record / Settings / Store + 校验与迁移
│   ├── storage.py           # 原子写入、备份、导入导出
│   ├── services.py          # TimerService / StatsService
│   └── ui/
│       ├── app.py           # 主窗口与页面调度
│       ├── theme.py         # 浅色 / 深色主题
│       ├── widgets.py       # 圆角按钮、卡片、进度环、热力图等
│       └── pages/
│           ├── home.py
│           ├── records.py
│           ├── stats.py
│           └── settings.py
├── tests/                   # unittest 测试
├── build.bat
├── requirements.txt
└── README.md
```

## 技术栈

- Python 3 + `tkinter`（界面）、`json` / `csv`（存储与导出）、`dataclasses`、`unittest`
- PyInstaller（打包为单文件 exe）
- 无第三方运行时依赖
