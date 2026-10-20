# 学习打卡（StudyTimer）

一个用于**学习计时与习惯记录**的 Windows 桌面应用。现代化布局，支持浅色/深色主题，零第三方运行时依赖。

## 功能

- **计时 / 番茄钟**：自由正向计时，或 25 / 45 / 60 分钟倒计时；结束时自动弹出记录窗口，倒计时结束有提示音。
- **今日概览**：今日已学、连续打卡、目标完成度进度环、最近记录。
- **学习记录**：标题、标签（科目）、备注、起止时间；关键字搜索 + 标签筛选；新增 / 编辑 / 删除。
- **统计**：区间汇总（累计 / 日均 / 达标 / 最长连续）、趋势柱状图（7 / 14 / 30 天）、近 12 周学习热力图、科目分布。
- **设置**：每日目标、定点提醒、达成提醒、默认番茄钟时长、浅色 / 深色主题、数据导出 / 导入 / 打开目录 / 清空。
- **数据安全**：原子写入（临时文件 + 替换）、自动备份、导入校验、旧版数据自动迁移。

快捷键：`空格` 开始 / 暂停 / 继续计时。

## 运行

需要 Python 3.10+（含 Tkinter，Windows 自带）。

```bash
python app.py
```

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖：计时器（秒表 / 倒计时 / 暂停 / 恢复）、统计（时长 / 连续 / 最长 / 序列 / 热力图 / 标签汇总）、存储（往返、v1 迁移、损坏回退备份、非法导入）。

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name 学习打卡 --collect-submodules study_timer app.py
```

也可双击 `build.bat` 一键打包。产物：`dist/学习打卡.exe`。

## 数据

- 主文件：`%APPDATA%/StudyTimer/study_data.json`
- 备份：`%APPDATA%/StudyTimer/study_data.bak.json`
- 结构版本 `version: 2`；旧版（平铺 settings、`durationMin`、字典形式 checkins）读取时自动迁移。
- 设置页可导出 / 导入 JSON，导入会做字段校验。

## 目录结构

```
.
├── app.py                   # 入口（薄封装）
├── study_timer/
│   ├── config.py            # 路径与常量
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

- Python 3 + `tkinter`（界面）、`json`（存储）、`dataclasses`、`unittest`
- PyInstaller（打包为单文件 exe）
- 无第三方运行时依赖
