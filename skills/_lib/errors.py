#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
errors.py — Agent OS 统一错误分层 (C2 / Phase 1 Foundation)

【背景】此前错误处理散落: 各模块直接 raise ValueError / RuntimeError /
TimeoutError, persistence 的 "Corrupt→ERROR 而非 default=[]" 契约也只是
隐式 try/except。缺少统一异常类型, 调用方无法按"可重试/不可重试/数据损坏"
分级处理。

本模块定义统一异常层级, 供 skills/_lib 及各 skill 共用:

   AgentOSError                      (基类)
   ├── StateError                    # 状态机/状态不一致 (非法跳转等)
   ├── InvariantError                # 状态-事实不变量缺失 (derived field)
   ├── DataIntegrityError            # 数据损坏/校验失败 (Corrupt)
   │     └── CorruptRecordError      # 具体记录损坏
   ├── PersistenceError              # 持久化失败 (IO/锁/原子写)
   │     └── LockTimeoutError        # 文件/锁超时 (可重试)
   └── SubprocessError               # 子进程/外部调用失败

【retryable 语义】所有异常带 .retryable 属性:
   - 明确可重试: LockTimeoutError, SubprocessError
   - 明确不可重试: StateError, InvariantError, DataIntegrityError/Corrupt
   - 默认(基类): False (安全默认, 不无限重试 —— 冻结原则 #9)

【Code = Enforcement】
   - 数据损坏 → 抛 DataIntegrityError, 绝不能"Corrupt → default=[] 覆盖原数据"
     (冻结方案 Commit 4 契约)
   - 状态非法 → 抛 StateError (由 transitions.py 中央门抛出)
   - 不变量缺失 → 抛 InvariantError

【用法】
   from errors import StateError, DataIntegrityError, CorruptRecordError
   raise StateError("非法跳转 RUNNING->COMPLETED", code="ILLEGAL_TRANSITION")
   try: ...
   except PersistenceError as e:
       if e.retryable: retry()   # LockTimeout
       else: escalate()
"""


class AgentOSError(Exception):
    """所有 Agent OS 错误的基类。"""
    retryable = False
    # 稳定的错误码, 用于诊断/测试 (默认用类名 + 自定义 code)
    default_code = "AGENTOS_ERROR"

    def __init__(self, message="", code=None, *, retryable=None,
                 details=None):
        super().__init__(message)
        self.message = str(message)
        self.code = code or self.__class__.default_code
        # MAJOR fix (B-1): retryable 是类级契约, 不允许实例级覆写 ——
        # 否则 StateError(..., retryable=True) 能把不可重试错误改成可重试,
        # 诱导无限重试。只有类-派生的子类 (LockTimeoutError/SubprocessError)
        # 能在类属性层面定义 retryable=True。
        if retryable not in (None, self.__class__.retryable):
            raise TypeError(
                "retryable 是类级只读契约, 不可实例覆写 (class=%s, retryable=%s)"
                % (self.__class__.__name__, retryable))
        self.details = details or {}

    def __repr__(self):
        return "%s(code=%s, retryable=%s): %s" % (
            self.__class__.__name__, self.code, self.retryable, self.message)


class StateError(AgentOSError, ValueError):
    """状态机/状态不一致。非法跳转、未知状态。不可重试(需人工/策略修正)。

    设计: 同时继承 ValueError —— 向后兼容 C1 时代 `except ValueError` 捕获
    中央门异常的全部调用点 (_core/rollback/recovery/test_transitions)。
    新增代码可改用 `except StateError` 精细捕获。
    """
    default_code = "STATE_ERROR"


class InvariantError(AgentOSError, ValueError):
    """状态-事实不变量缺失。进入某状态缺少必要事实字段(如 COMPLETED 缺
    completed_at)。不可重试。同样兼容 except ValueError。"""
    default_code = "INVARIANT_ERROR"


class DataIntegrityError(AgentOSError):
    """数据损坏/校验失败。绝不静默降级(default=[])或覆盖原数据。
    需要人工审查或从备份恢复，不可自动重试。"""
    default_code = "DATA_INTEGRITY_ERROR"


class CorruptRecordError(DataIntegrityError):
    """具体某条记录损坏 (JSON 解析失败/字段缺失/校验和不符)。"""
    default_code = "CORRUPT_RECORD"


class PersistenceError(AgentOSError):
    """持久化失败 (IO / 文件锁 / 原子写失败)。LockTimeout 子类可重试。"""
    default_code = "PERSISTENCE_ERROR"


class LockTimeoutError(PersistenceError):
    """文件/分布式锁获取超时。可重试 (等锁释放)。"""
    default_code = "LOCK_TIMEOUT"
    retryable = True


class SubprocessError(AgentOSError):
    """子进程/外部命令调用失败。网络/进程层，可重试(有上限)。"""
    default_code = "SUBPROCESS_ERROR"
    retryable = True


# --- 便捷构建: 把普通 Exception 包装为 Agent OS 分级错误 -----------------
def as_data_integrity(exc, message="corrupt data", **kw):
    """把任意异常包装为 DataIntegrityError (保留 cause)。"""
    err = DataIntegrityError(message, **kw)
    err.__cause__ = exc
    return err


def as_state_error(exc, message="state error", **kw):
    err = StateError(message, **kw)
    err.__cause__ = exc
    return err
