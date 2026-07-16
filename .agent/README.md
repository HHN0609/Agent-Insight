# Agent-Insight AI Agent 工作规则

本目录是 AI Agent（如 Trae / Cursor / Copilot 等）在本仓库工作时**必须遵守**的规则集合。所有规则均基于真实代码路径与已落地的设计决策，非泛泛而谈。

## 如何使用

- **接手任何任务前**：先读 [project-overview.md](./project-overview.md)，建立对系统全貌的认知。
- **动代码前**：必读 [invariants.md](./invariants.md)。这里列出的是**不可破坏的硬约束**，违反会直接导致数据错乱、服务崩溃或链路断裂。若某条规则阻碍了正当需求，应先与维护者确认，而非擅自绕过。
- **写代码时**：遵循 [coding-conventions.md](./coding-conventions.md) 的分层风格与扩展范式。
- **写/改测试时**：遵循 [testing.md](./testing.md)。
- **提交前**：按 [workflow.md](./workflow.md) 的检查清单自检，尤其是跨模块改动。

## 规则文件索引

| 文件 | 内容 | 何时读 |
|------|------|--------|
| [project-overview.md](./project-overview.md) | 项目定位、架构图、数据流、技术栈、模块边界 | 接手任务前 |
| [invariants.md](./invariants.md) | 不可破坏的硬约束（定价同步、非阻塞、重试语义等） | **动任何代码前必读** |
| [coding-conventions.md](./coding-conventions.md) | Python（SDK/backend）/ TypeScript（frontend）代码风格与扩展范式 | 写代码时 |
| [testing.md](./testing.md) | 各层测试规范、命名约定、mock 策略 | 写/改测试时 |
| [workflow.md](./workflow.md) | 改动流程、跨模块同步检查清单、提交前自检 | 提交前 |

## 优先级

当规则之间出现冲突，或规则与现实代码出现冲突时，按以下优先级判断：

1. **正确性与数据一致性**（invariants.md）最高优先级。
2. **现实代码现状**：规则描述的是"应有状态"，若代码与规则不符，优先修正代码使之符合规则；若规则本身过时，应更新规则文件并说明原因。
3. **风格统一**：在满足前两者的前提下，保持与周边代码风格一致。

## 范围说明

本规则覆盖仓库的三个交付层 + 基础设施：

- `sdk/` — Python 探针 SDK（用户侧，非侵入式埋点）
- `backend/` — FastAPI 服务（采集 + 查询）
- `frontend/` — React + TypeScript Dashboard
- `docker/` + `docker-compose.yml` — Kafka + ClickHouse 基础设施

> 根目录的 `README.md` 与 `ARCHITECTURE.md` 是面向人类的项目文档；本目录是面向 AI Agent 的工作准则，二者互补，不互相替代。
