# NewAPI Guardian Bot

## 项目简介
NewAPI Guardian 是一个用于监控、管理和备份 NewAPI 渠道的 Telegram 机器人，能够实时检测渠道健康、提供备份恢复、以及基于 AI 的智能交互。

## 新架构说明
该项目采用通用 **Agent 架构**，主要分为以下层次：

- **core/** 核心能力层
  - `database/`：数据库抽象与操作
  - `http_client/`：统一的 HTTP 请求封装（基于 `requests`）
  - `formatter/`：输出格式化与 UI 生成

- **skills/** 技能插件层
  - 目前实现 `newapi` 技能，提供针对 NewAPI 的业务查询、监控与管理 API 封装。

- **tools_new/** 动态工具系统
  - 可通过配置动态加载工具，实现灵活的功能扩展。

- **agent** 层（`agent_core.py`, `agent_handler.py`）
  - 负责调度、上下文管理以及与 Telegram Bot 的交互。

- **AI 能力**
  - 通过 `ai_config.py` 与 OpenAI API 集成，支持在对话中直接生成 SQL 查询或 HTTP 请求。

## 功能特性
- 实时监控 NewAPI 渠道状态并提供报警
- 备份/恢复 MySQL 数据库
- 支持每日/定时报告
- 基于 AI 的自然语言交互与查询
- 完整的 Telegram Bot 界面与快捷键按钮

## 安装步骤
```bash
# 克隆仓库（已在 /tmp/newapi-guardian-repo）
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制 .env.example 并填入实际值）
cp .env.example .env
# 编辑 .env
nano .env
```

## 配置说明
- 详见 `.env.example`，包括 Telegram Bot Token、MySQL 只读账号、NewAPI 接口信息以及可选的 OpenAI 配置。
- `config.py` 会加载这些变量并在运行时使用。

## 使用方法
```bash
python -m bot
```
- 通过 Telegram 与 Bot 交互，使用 `/start` 查看主菜单。
- 通过快捷按钮快速查看概览、渠道管理、备份等功能。

## 开发指南
- **核心代码** 位于 `core/`，如需修改数据库或 HTTP 逻辑，请在对应子模块中实现。
- **新增技能** 在 `skills/` 目录下创建子目录并实现对应的业务函数，注册到 `tools_new/registry.py`。
- **AI 扩展** 可在 `ai_config.py` 中添加新的模型或提示模板。
- 代码遵循 PEP8 与 type hints，建议使用 `ruff` 或 `black` 进行格式化。

---

💖 Made with love by **Rem** (蕾姆) for **昴君**.

---
