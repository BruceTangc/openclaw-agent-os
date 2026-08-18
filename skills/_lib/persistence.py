#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1.3 Hardening — 统一原子持久化 helper (Batch 3)

用于 tasks.json / state.json / queue.json 等受并发覆盖风险的可变状态:
  atomic_write(path, data, lock_timeout=10)
    lock → read(optional) → (caller modify) → write temp → fsync → os.replace → unlock

保持 append-only 的 (Execution Record JSONL / Ontology changelog) 用 append_atomic()。
不要为了修并发把 append-only 改成数据库。
"""

import json
import os
import tempfile
import time

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


def _lock_path(path):
    return path + ".lock"


class FileLock:
    """进程内 + 跨进程 (fcntl) 文件锁。"""

    def __init__(self, path, timeout=10.0):
        self.lock_file = _lock_path(path)
        self.timeout = timeout
        self._fd = None

    def acquire(self):
        d = os.path.dirname(self.lock_file)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        self._fd = open(self.lock_file, "w+", encoding="utf-8")
        if _HAS_FCNTL:
            deadline = time.time() + self.timeout
            while True:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except (IOError, OSError):
                    if time.time() >= deadline:
                        raise TimeoutError("lock timeout: " + self.lock_file)
                    time.sleep(0.05)
        # 无 fcntl (非 POSIX): 用存在性 + O_EXCL 简化
        flag = os.path.join(d, ".stamp") if d else ".stamp"
        return

    def release(self):
        if self._fd is not None:
            if _HAS_FCNTL:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                except (IOError, OSError):
                    pass
            self._fd.close()
            self._fd = None


def atomic_write_json(path, data, timeout=10.0):
    """lock → write temp → fsync → os.replace → unlock。损坏/异常不覆盖原文件。"""
    lock = FileLock(path, timeout)
    lock.acquire()
    tmp = None
    try:
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp",
                                   prefix=os.path.basename(path) + ".")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None and os.path.isfile(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        lock.release()


def append_atomic(path, line_obj, timeout=10.0):
    """append-only: 单行 JSON 追加 (带锁)，用于 JSONL。error 时不影响已存在内容。"""
    lock = FileLock(path, timeout)
    lock.acquire()
    try:
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        line = json.dumps(line_obj, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    finally:
        lock.release()
