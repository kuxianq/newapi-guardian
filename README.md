# NewAPI Guardian Bot

<div align="center">

**🤖 智能 NewAPI 渠道监控与管理 Telegram Bot**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)

一个基于 Telegram 的智能 Agent，用于监控和管理 [NewAPI](https://github.com/Calcium-Ion/new-api) 渠道。

</div>

---

## ✨ 核心特性

### 🤖 智能 Agent 模式
- **三层记忆系统**：工作记忆 + 短期记忆（20轮）+ 长期记忆
- **自主学习**：AI 可以记住重要事实和用户偏好
- **多轮推理**：最多 10 轮思考，自由组合工具
- **上下文记忆**：记住最近对话，不用重复说明

### 📊 渠道监控
- 实时渠道状态监控
- 失败渠道自动检测和告警
- 慢渠道排行
- 渠道健康度评分
- 自动异常通知

### 🔧 渠道管理
- 启用/禁用渠道
- 批量操作
- 单渠道/批量/按模型测试
- 一键禁用失败渠道

### 📈 数据统计
- 今日/昨日统计对比
- 模型使用排行
- 用户使用排行
- Token 使用排行
- 使用日志查询
- Console 综合面板

### 💾 数据安全
- 数据库自动备份
- 备份文件管理
- 一键恢复

---

## 📦 快速开始

### 前置要求

- **Python 3.11+**
- **MySQL 5.7+**（NewAPI 数据库，只读权限即可）
- **Telegram Bot Token**（从 [@BotFather](https://t.me/BotFather) 获取）
- **NewAPI Admin Token**（从 NewAPI 后台获取）

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/newapi-guardian.git
cd newapi-guardian
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
nano .env  # 或使用你喜欢的编辑器
```

**必填配置项**：

```bash
# Telegram Bot Token (从 @BotFather 获取)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 授权用户 ID (多个用逗号分隔)
# 获取方式：给 @userinfobot 发消息
AUTHORIZED_TELEGRAM_IDS=123456789,987654321

# MySQL 连接 (连接到 NewAPI 数据库)
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=newapi_guardian
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=newapi

# NewAPI Admin API
NEWAPI_BASE_URL=http://127.0.0.1:3000
NEWAPI_ADMIN_TOKEN=your_admin_token_here
```

### 5. 创建 MySQL 只读账号（推荐）

```sql
-- 连接到 MySQL
mysql -u root -p

-- 创建只读账号
CREATE USER 'newapi_guardian'@'localhost' IDENTIFIED BY 'your_password_here';
GRANT SELECT ON newapi.* TO 'newapi_guardian'@'localhost';
FLUSH PRIVILEGES;
```

### 6. 初始化数据目录

```bash
mkdir -p data/agent_memory backups
```

### 7. 运行

```bash
python bot.py
```

如果一切正常，你会看到：

```
2026-05-02 13:00:00 [guardian] INFO: NewAPI Guardian Bot v2 starting...
2026-05-02 13:00:01 [guardian] INFO: Bot commands registered.
```

现在可以在 Telegram 给你的 Bot 发送 `/start` 了！

---

## 🚀 生产部署

### 方式 1：systemd 服务（推荐）

1. 复制服务模板：

```bash
sudo cp newapi-guardian.service.example /etc/systemd/system/newapi-guardian.service
```

2. 编辑服务文件：

```bash
sudo nano /etc/systemd/system/newapi-guardian.service
```

修改以下内容：
- `User=your_user` → 你的用户名
- `WorkingDirectory=/path/to/newapi-guardian` → 项目路径
- `Environment="PATH=..."` → 虚拟环境路径

3. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable newapi-guardian
sudo systemctl start newapi-guardian
sudo systemctl status newapi-guardian
```

4. 查看日志：

```bash
sudo journalctl -u newapi-guardian -f
```

### 方式 2：Screen/Tmux

```bash
screen -S guardian
source .venv/bin/activate
python bot.py
# Ctrl+A+D 分离
```

恢复会话：

```bash
screen -r guardian
```

---

## 🎮 使用指南

### 基础命令

- `/start` - 启动 Bot，显示主菜单
- `/menu` - 显示主菜单
- `/status` - 查看总览 + 快捷入口
- `/help` - 查看完整帮助

### 监控查询

- `/console` - Console 综合面板
- `/today` - 今日统计
- `/models` - 模型排行
- `/users` - 用户排行
- `/tokens` - Token 排行
- `/model <名称>` - 按模型查询
- `/channel <ID>` - 按渠道查询
- `/slow` - 慢渠道排行
- `/logs` - 最近 10 条使用日志

### 渠道测试

- `/test <ID>` - 测试单个渠道
- `/test_model <名称>` - 按模型测试所有渠道
- `/test_all` - 测试全部启用渠道

### 渠道操作

- `/enable <ID> [ID...]` - 启用渠道
- `/disable <ID> [ID...]` - 禁用渠道（需确认）
- `/disable_failed [阈值]` - 一键禁用失败渠道

### 数据安全

- `/backup` - 备份数据库
- `/backup_list` - 备份列表
- `/restore <文件名>` - 恢复数据库

### AI 功能

- `/ai_mode on|off` - AI 对话模式开关
- `/ai_config` - AI 配置管理
- `@ai <消息>` - 直接对话（AI 模式关闭时）
- `清空上下文` - 清空 AI 对话历史

---

## 🤖 AI Agent 模式

### 什么是 Agent 模式？

NewAPI Guardian 不是简单的工具调用机器人，而是一个**真正的智能 Agent**：

1. **会记忆**：记住你说过的话，不用重复
2. **会思考**：多步推理，主动分析问题
3. **会学习**：从对话中学习你的习惯和偏好
4. **会建议**：不只返回数据，还给出可行建议

### 示例对话

**上下文记忆**：

```
你：@ai 帮我看下渠道 42
AI：渠道 42 目前正常，最近 1 小时成功率 98%...

你：测试一下
AI：（知道你说的是渠道 42）好的，我来测试渠道 42...
```

**学习偏好**：

```
你：@ai 简单点，别废话
AI：（记住了）好的，以后我会更简洁。

[下次对话]
你：@ai 看下统计
AI：今日 1.2w 次，99.2% 成功。
```

**多步推理**：

```
你：@ai 为什么今天请求量这么低
AI：我看了一下：
    1. 今日请求量 5000 次，比昨天少 50%
    2. 发现有 3 个主力渠道被禁用了
    3. 禁用时间是今天凌晨 2 点
    
    是你手动禁用的吗？还是自动禁用的？
```

### AI 配置

AI 功能需要配置 OpenAI 兼容的 API：

```bash
/ai_config set_url https://your-api.com/v1
/ai_config set_key sk-your-api-key
/ai_config set_model gpt-4
/ai_config enable
```

---

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | ✅ | - |
| `AUTHORIZED_TELEGRAM_IDS` | 授权用户 ID（逗号分隔） | ✅ | - |
| `MYSQL_HOST` | MySQL 主机 | ✅ | `127.0.0.1` |
| `MYSQL_PORT` | MySQL 端口 | ❌ | `3306` |
| `MYSQL_USER` | MySQL 用户 | ✅ | - |
| `MYSQL_PASSWORD` | MySQL 密码 | ✅ | - |
| `MYSQL_DATABASE` | MySQL 数据库名 | ✅ | `newapi` |
| `NEWAPI_BASE_URL` | NewAPI API 地址 | ✅ | `http://127.0.0.1:3000` |
| `NEWAPI_ADMIN_TOKEN` | NewAPI Admin Token | ✅ | - |
| `CHECK_INTERVAL_MINUTES` | 监控检查间隔（分钟） | ❌ | `60` |
| `DAILY_REPORT_HOUR` | 每日报告时间（小时） | ❌ | `9` |
| `BACKUP_DIR` | 备份目录 | ❌ | `./backups` |

### 工具权限

权限配置文件：`data/permissions.json`

- **safe**：安全操作，AI 可自由调用
  - 所有查询类工具（`get_*`）
  - 所有测试类工具（`test_*`）
  - 启用渠道（`enable_channel`）

- **confirm**：需要用户确认
  - 禁用渠道（`disable_channel`）
  - 批量禁用（`batch_disable`）

- **forbidden**：禁止操作
  - 删除渠道（`delete_channel`）

---

## 📁 项目结构

```
newapi-guardian/
├── bot.py                  # Bot 主入口
├── config.py               # 配置管理
├── db.py                   # 数据库查询
├── formatter.py            # 消息格式化
├── monitor.py              # 监控逻辑
├── backup.py               # 备份管理
├── newapi_client.py        # NewAPI API 客户端
├── cache.py                # 缓存管理
├── agent_core.py           # Agent 核心（记忆系统）
├── agent_brain.py          # Agent AI 大脑
├── agent_handler.py        # Agent 消息处理
├── ai_config.py            # AI 配置管理
├── ai_tools.py             # AI 工具注册表
├── requirements.txt        # Python 依赖
├── .env.example            # 配置模板
└── data/                   # 数据目录
    ├── permissions.json    # 工具权限配置
    ├── tool_registry.json  # 工具注册表
    └── agent_memory/       # Agent 记忆文件（自动创建）
```

---

## 🔧 常见问题

### 1. 如何获取 Telegram Bot Token？

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`
3. 按提示设置 Bot 名称和用户名
4. 获取 Token

### 2. 如何获取我的 Telegram ID？

1. 在 Telegram 搜索 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息
3. 获取你的 ID

### 3. 如何获取 NewAPI Admin Token？

1. 登录 NewAPI 后台
2. 进入"设置" → "系统设置"
3. 找到"Root 用户令牌"或创建管理员令牌

### 4. Bot 不回复消息？

检查：
- Bot Token 是否正确
- 你的 Telegram ID 是否在 `AUTHORIZED_TELEGRAM_IDS` 中
- 服务是否正常运行：`systemctl status newapi-guardian`

### 5. 数据库连接失败？

检查：
- MySQL 是否运行
- 用户名密码是否正确
- 数据库名是否正确
- 用户是否有 SELECT 权限

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot 框架
- [NewAPI](https://github.com/Calcium-Ion/new-api) - API 管理系统
- [OpenAI](https://openai.com/) - AI 能力支持

---

<div align="center">

**Made with ❤️ by Rem**

如果这个项目对你有帮助，请给个 ⭐ Star！

</div>
