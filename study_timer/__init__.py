# -*- coding: utf-8 -*-
"""学习打卡（StudyTimer）—— 学习计时与习惯记录桌面应用。"""

import logging

from .config import VERSION

# 库形态使用时不向 stderr 抛日志；应用启动时由 setup_logging() 挂真实 handler。
# 该 NullHandler 同时避免未配置日志时 logging 的 lastResort 输出污染测试。
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["VERSION"]
