# -*- coding: utf-8 -*-
"""数据持久化：原子写入、自动备份、导入导出。"""

from __future__ import annotations

import json
import os
import shutil

from .config import BACKUP_FILE, DATA_FILE
from .models import Store, ValidationError


class Repository:
    """负责 Store 的读写。"""

    def __init__(self, data_file: str = DATA_FILE, backup_file: str = BACKUP_FILE):
        self.data_file = data_file
        self.backup_file = backup_file

    # ---------- 读取 ----------
    def load(self) -> Store:
        """优先读主文件，失败则回退到备份，再失败返回空数据。"""
        for path in (self.data_file, self.backup_file):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return Store.from_dict(json.load(fh))
            except Exception:
                continue
        return Store()

    # ---------- 写入（原子 + 备份） ----------
    def save(self, store: Store) -> None:
        directory = os.path.dirname(self.data_file) or "."
        os.makedirs(directory, exist_ok=True)

        payload = store.to_dict()
        tmp_path = self.data_file + ".tmp"

        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())

        # 覆盖前把旧文件留作备份
        if os.path.exists(self.data_file):
            try:
                shutil.copy2(self.data_file, self.backup_file)
            except Exception:
                pass

        os.replace(tmp_path, self.data_file)

    # ---------- 导入 / 导出 ----------
    def export(self, store: Store, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(store.to_dict(), fh, ensure_ascii=False, indent=2)

    def import_file(self, path: str) -> Store:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            raise ValidationError(f"无法读取 JSON：{exc}")
        return Store.from_dict(data)
