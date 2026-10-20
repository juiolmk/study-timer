# -*- coding: utf-8 -*-
"""全局配置：应用信息、数据路径、常量。"""

import os

APP_NAME = "学习打卡"
APP_NAME_EN = "StudyTimer"
VERSION = "2.0.0"

SCHEMA_VERSION = 2

# 数据目录：%APPDATA%/StudyTimer
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "StudyTimer")
DATA_FILE = os.path.join(DATA_DIR, "study_data.json")
BACKUP_FILE = os.path.join(DATA_DIR, "study_data.bak.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# 轮转备份保留份数
BACKUP_KEEP = 7

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 番茄钟预设（分钟）
FOCUS_PRESETS = [25, 45, 60]
DEFAULT_FOCUS = 25
DEFAULT_GOAL = 60

# 快速补记的时长预设（分钟）
QUICK_PRESETS = [15, 25, 45, 60]

# 少于该秒数不记录
MIN_RECORD_SECONDS = 5
