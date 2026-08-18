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
import contextlib
import threading

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


def _lock_path(path):
    return path + ".lock"


class FileLock:
    """进程内 + 跨进程 (fcntl) 文件锁，支持线程级可重入。

    P1-2/修复: 增加真事务用法——把 read→modify→write 整体包进同一把锁：
        with FileLock(path) as lock:
            data = _do_read()      # 锁内读
            data = mutate(data)    # 锁内改
            _do_write(data)        # 锁内写（内部 atomic 写也应复用同一把锁）
    进程内重入用 thread-local 持锁计数实现：同一线程再次 acquire 同一 lock 直接返回，
    不会对已持有的 fcntl 锁重复加锁导致死锁。
    atomic_write_json 仍是便捷单写（可单独用，也可在事务锁内复用）。
    """

    _tl = threading.local()

    def __init__(self, path, timeout=10.0):
        self.lock_file = _lock_path(path)
        self.timeout = timeout
        self._fd = None
        self._id = self.lock_file

    def _hold_count(self):
        c = getattr(self._tl, "counts", None)
        return (c or {}).get(self._id, 0)

    def _inc_hold(self):
        c = getattr(self._tl, "counts", None)
        if c is None:
            c = {}
            self._tl.counts = c
        c[self._id] = c.get(self._id, 0) + 1

    def _dec_hold(self):
        c = getattr(self._tl, "counts", None)
        if not c:
            return
        if c.get(self._id, 0) > 0:
            c[self._id] -= 1
        if c.get(self._id, 0) == 0:
            c.pop(self._id, None)

    def acquire(self):
        # 线程内可重入：已持有同锁则只计数，不重复加 fcntl/file stamp 锁
        if self._hold_count() > 0:
            self._inc_hold()
            return
        d = os.path.dirname(self.lock_file)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        self._fd = open(self.lock_file, "w+", encoding="utf-8")
        if _HAS_FCNTL:
            deadline = time.time() + self.timeout
            while True:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (IOError, OSError):
                    if time.time() >= deadline:
                        raise TimeoutError("lock timeout: " + self.lock_file)
                    time.sleep(0.05)
        else:
            # P2-1/修复: 无 fcntl (非 POSIX) 时，用 O_EXCL 独占创建 .stamp 实现真锁。
            stamp = self.lock_file + ".stamp"
            deadline = time.time() + self.timeout
            while True:
                try:
                    sfd = os.open(stamp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(sfd, str(os.getpid()).encode())
                    os.close(sfd)
                    self._stamp = stamp
                    break
                except FileExistsError:
                    if time.time() >= deadline:
                        raise TimeoutError("lock timeout (stamp): " + stamp)
                    time.sleep(0.05)
        self._inc_hold()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

    def release(self):
        if self._hold_count() <= 0:
            return
        self._dec_hold()
        # 仍有外层持有 → 不真正释放底层锁（重入）
        if self._hold_count() > 0:
            return
        if self._fd is not None:
            if _HAS_FCNTL:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                except (IOError, OSError):
                    pass
            self._fd.close()
            self._fd = None
        if not _HAS_FCNTL:
            stamp = getattr(self, "_stamp", None)
            if stamp and os.path.exists(stamp):
                try:
                    os.unlink(stamp)
                except OSError:
                    pass
            self._stamp = None


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
