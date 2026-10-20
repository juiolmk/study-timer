# -*- coding: utf-8 -*-
"""数据持久化：原子写入、轮转备份、导入导出（JSON / CSV）。"""

from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime

from .config import BACKUP_DIR, BACKUP_FILE, BACKUP_KEEP, DATA_FILE
from .models import Store, ValidationError


class Repository:
    """负责 Store 的读写与备份。"""

    def __init__(self, data_file: str = DATA_FILE, backup_file: str = BACKUP_FILE,
                 backup_dir: str | None = None):
        self.data_file = data_file
        self.backup_file = backup_file
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(data_file) or ".", "backups")
        #: 本次 load 是否从备份恢复（供 UI 提示）
        self.last_load_recovered = False

    # ---------- 读取 ----------
    def load(self) -> Store:
        """优先主文件；失败时回退到最近备份，并记录恢复标记。"""
        self.last_load_recovered = False

        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as fh:
                    return Store.from_dict(json.load(fh))
            except Exception:
                pass

        for path in self._fallback_paths():
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    store = Store.from_dict(json.load(fh))
                self.last_load_recovered = True
                return store
            except Exception:
                continue

        return Store()

    def _fallback_paths(self):
        paths = []
        if self.backup_file:
            paths.append(self.backup_file)
        paths.extend(self.list_backups())
        return paths

    def list_backups(self):
        """返回轮转备份文件列表（新 → 旧）。"""
        if not os.path.isdir(self.backup_dir):
            return []
        names = [
            name for name in os.listdir(self.backup_dir)
            if name.startswith("study_data-") and name.endswith(".json")
        ]
        # 文件名含时间戳，字典序即时间序
        names.sort(reverse=True)
        return [os.path.join(self.backup_dir, name) for name in names]

    # ---------- 写入（原子 + 轮转备份） ----------
    def save(self, store: Store) -> None:
        directory = os.path.dirname(self.data_file) or "."
        os.makedirs(directory, exist_ok=True)

        payload = store.to_dict()
        tmp_path = self.data_file + ".tmp"

        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())

        if os.path.exists(self.data_file):
            # 兼容旧版单份备份
            try:
                shutil.copy2(self.data_file, self.backup_file)
            except Exception:
                pass
            self._snapshot_backup()

        os.replace(tmp_path, self.data_file)

    def _snapshot_backup(self) -> None:
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = os.path.join(self.backup_dir, f"study_data-{stamp}.json")
            shutil.copy2(self.data_file, target)
            self._prune_backups()
        except Exception:
            pass

    def _prune_backups(self) -> None:
        for path in self.list_backups()[BACKUP_KEEP:]:
            try:
                os.remove(path)
            except Exception:
                pass

    # ---------- 导入 / 导出 ----------
    def export(self, store: Store, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(store.to_dict(), fh, ensure_ascii=False, indent=2)

    def export_csv(self, store: Store, path: str) -> None:
        """导出为 CSV（utf-8-sig，Excel 直接打开不乱码）。"""
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["日期", "开始", "结束", "时长(分钟)", "学习内容", "标签", "备注"])
            for record in sorted(store.records, key=lambda item: (item.date, item.start)):
                writer.writerow([
                    record.date,
                    record.start,
                    record.end,
                    record.duration_min,
                    record.title,
                    record.tag,
                    record.note,
                ])

    def import_file(self, path: str) -> Store:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            raise ValidationError(f"无法读取 JSON：{exc}")
        return Store.from_dict(data)
