# NewAPI Guardian Bot

NewAPI Guardian Bot 是一个用于 NewAPI 日常运维的 Telegram 机器人，支持渠道监控、查询、测试、备份恢复和 AI 辅助分析。

## 功能

- 状态概览：渠道数量、成功率、失败渠道、慢渠道、今日用量
- 渠道查询：按渠道 ID / 模型名查看渠道与近期日志
- 渠道测试：单渠道测试、按模型测试、全量启用渠道测试
- 渠道操作：启用 / 禁用渠道、批量禁用失败渠道（带确认）
- 数据安全：MySQL 备份、备份列表、恢复确认
- 日报与告警：每日汇总、连续失败提醒、恢复提醒
- AI Agent：自然语言查询、失败归因、只读分析和带确认的管理操作

## 部署

### 1. 准备环境

```bash
git clone https://github.com/kuxianq/newapi-guardian.git
cd newapi-guardian
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
```

至少需要配置：

- `TELEGRAM_BOT_TOKEN`
- `AUTHORIZED_TELEGRAM_IDS`
- `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE`
- `NEWAPI_BASE_URL`
- `NEWAPI_ADMIN_TOKEN`

### 3. 启动

```bash
python bot.py
```

首次启动后，在 Telegram 中发送：

```text
/start
```

## systemd 运行

可以参考示例文件：

```text
deploy/newapi-guardian.service.example
```

示例流程：

```bash
sudo cp deploy/newapi-guardian.service.example /etc/systemd/system/newapi-guardian.service
sudo systemctl daemon-reload
sudo systemctl enable --now newapi-guardian
sudo systemctl status newapi-guardian
```

请根据实际安装路径修改 `WorkingDirectory`、`EnvironmentFile` 和 `ExecStart`。

## 常用命令

```text
/start                  主菜单
/status                 状态概览
/model <模型名>          按模型查询渠道
/channel <渠道ID>        查看渠道详情
/test <渠道ID>           测试渠道
/test_model <模型名>     测试某模型所有渠道
/test_all               测试全部启用渠道
/backup                 备份数据库
/backup_list            查看备份列表
/restore <文件名>        恢复数据库
/ai_mode on|off         开关 AI 对话模式
/ai_config              配置 AI 能力
```

## 本地验证

```bash
. .venv/bin/activate
python -m compileall -q .
python -m unittest discover -v tests
bash scripts/secret-scan.sh
```

## 注意事项

- 不要提交 `.env`、`data/`、数据库文件或备份文件。
- 恢复数据库、批量禁用渠道等操作会要求确认。
- 建议为 Bot 使用只读 MySQL 用户；需要备份 / 恢复时再单独配置具备权限的账号。
