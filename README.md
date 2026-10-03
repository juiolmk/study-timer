# 学习打卡（StudyTimer）

一个用于**学习计时打卡**的 Windows 桌面软件：每天记录学习了什么、学了多久，并查看统计与目标完成情况。

- 简洁明亮的原生界面（Tkinter），无需联网。
- 单文件打包为 `学习打卡.exe`，双击即用。

## 功能

- **计时打卡**：一键开始 / 暂停 / 继续 / 结束，结束填写学习内容即自动打卡。
- **今日概览**：今日日期、今日已学时长、连续打卡天数、每日目标完成度进度环。
- **记录**：按日期展示学习内容（标题 / 备注 / 起止 / 时长），支持新增 / 编辑 / 删除 / 搜索。
- **统计**：近 7 / 14 / 30 天学习时长柱状图 + 目标线，汇总累计时长、日均、达标天数、最长连续打卡。
- **设置**：每日目标分钟、定点提醒、数据导出 / 导入、清空。

## 运行（开发模式）

需要 Python 3.8+（含 Tkinter，Windows 自带）。

```bash
python app.py
```

## 打包为 exe

使用 PyInstaller 打包为单个可执行文件：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name 学习打卡 app.py
```

打包结果在 `dist/学习打卡.exe`。也可直接双击 `build.bat` 一键打包（需已安装 PyInstaller）。

## 数据位置

学习记录保存在：

```
%APPDATA%/StudyTimer/study_data.json
```

可在「设置 → 数据管理」中导出 / 导入备份。

## 目录结构

```
.
├── app.py            # 应用源码（全部逻辑与界面）
├── build.bat         # 一键打包脚本
├── requirements.txt  # 构建依赖（仅打包时需要）
├── README.md         # 说明文档
├── .gitignore
└── dist/             # 打包产物（学习打卡.exe），由构建生成
```

## 技术栈

- Python 3 + 标准库 `tkinter`（界面）、`json`（存储）
- PyInstaller（打包为单文件 exe）
- 无第三方运行时依赖
