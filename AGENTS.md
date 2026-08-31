# Agent OS Repository Instructions

## Scope

- 本仓库是 OpenClaw 原生运行时之上的治理、决策与工作流策略层。
- OpenClaw 负责 agent loop、session、scheduler、tools、sub-agents 与最终 policy/approval；不要在本仓库另建并行 runtime、scheduler、event bus、memory engine 或 permission runtime。
- 优先做增量修复并复用现有 Skill、脚本和协议；不要无关重构。

## Working Rules

- 开始前检查工作区状态，保留用户已有和无关改动。
- 搜索优先使用 `rg`；修改文件使用小而清晰的补丁。
- 状态损坏不得当作空状态；可变状态写入须保持原子性和状态机约束。
- Permission 必须 fail-closed；工具成功不等于任务完成；验证结论必须有证据。
- 涉及外发、生产、资金、权限、删除或其他不可逆影响时，先取得明确授权。
- 不自动修改安全边界、协议规则或本文件；此类变更必须由用户明确要求。

## Verification

- 代码变更至少运行与改动相关的定向测试。
- 提交前运行第一阶段统一检查：`python scripts/quality_gate.py`。
- 无法运行的检查必须在交付中说明；不要把未验证结果表述为完成。

## Documentation

- 详细协议以 `docs/PROTOCOL.md`、`docs/ACTION-PROTOCOL.md`、`docs/VERIFICATION-PROTOCOL.md`、`docs/MEMORY-PROTOCOL.md` 和各 Skill 的 `SKILL.md` 为准。
- 行为、命令或安装方式变化时，同步更新最邻近的文档。

## Git

- 不自行 commit、push、创建 PR 或发布，除非用户明确要求。
- 仓库不强制指定 reviewer；根据变更风险使用常规代码审查和自动化检查。
