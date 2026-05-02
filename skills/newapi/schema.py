"""NewAPI 数据库 Schema 文档"""

DATABASE_SCHEMA = """
# NewAPI 数据库结构

## 表：channels（渠道表）
存储所有 API 渠道的配置信息。

字段：
- id (int): 渠道 ID，主键
- name (varchar): 渠道名称
- type (int): 渠道类型（1=OpenAI, 14=Anthropic, 等）
- status (int): 状态（1=启用, 0=禁用, 2=自动禁用）
- test_model (varchar): 测试用模型名称
- used_quota (bigint): 已使用额度（单位：1/500000 美元）
- response_time (int): 平均响应时间（毫秒）
- priority (int): 优先级（数字越大优先级越高）
- weight (int): 权重（用于负载均衡）
- auto_ban (int): 自动禁用开关（1=开启）
- base_url (varchar): API 基础 URL
- models (text): 支持的模型列表（JSON 数组字符串）
- `group` (varchar): 渠道分组
- tag (varchar): 渠道标签
- remark (text): 备注信息

常用查询：
- 查看所有启用的渠道：SELECT * FROM channels WHERE status=1
- 查看禁用的渠道：SELECT * FROM channels WHERE status!=1
- 查看某个渠道详情：SELECT * FROM channels WHERE id=?
- 查看支持某模型的渠道：SELECT * FROM channels WHERE models LIKE '%model_name%'

## 表：logs（请求日志表）
存储所有 API 请求的日志记录。

字段：
- id (int): 日志 ID，主键
- type (int): 日志类型（1=充值, 2=消费, 3=管理, 4=系统）
- is_stream (int): 是否流式请求（1=是, 0=否）
- channel_id (int): 渠道 ID
- channel_name (varchar): 渠道名称
- user_id (int): 用户 ID
- username (varchar): 用户名
- token_name (varchar): Token 名称
- model_name (varchar): 模型名称
- use_time (float): 请求耗时（秒）
- prompt_tokens (int): 输入 token 数
- completion_tokens (int): 输出 token 数
- quota (bigint): 消耗额度（单位：1/500000 美元）
- ip (varchar): 请求 IP
- content (text): 请求/响应内容或错误信息
- created_at (bigint): 创建时间（UNIX 时间戳，秒）

常用查询：
- 查看最近的请求：SELECT * FROM logs ORDER BY created_at DESC LIMIT 10
- 查看成功的请求：SELECT * FROM logs WHERE type=2 ORDER BY created_at DESC
- 查看失败的请求：SELECT * FROM logs WHERE type!=2 ORDER BY created_at DESC
- 查看某渠道的日志：SELECT * FROM logs WHERE channel_id=? ORDER BY created_at DESC
- 查看某用户的日志：SELECT * FROM logs WHERE username=? ORDER BY created_at DESC
- 查看某 Token 的日志：SELECT * FROM logs WHERE token_name=? ORDER BY created_at DESC
- 查看最近 1 小时：SELECT * FROM logs WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
- 统计模型使用：SELECT model_name, COUNT(*) as calls FROM logs WHERE type=2 GROUP BY model_name ORDER BY calls DESC

## 表：tokens（Token 表）
存储所有 API Token 的信息。

字段：
- id (int): Token ID，主键
- name (varchar): Token 名称
- key (varchar): Token 密钥（加密存储）
- status (int): 状态（1=启用, 2=禁用, 3=过期, 4=耗尽）
- remain_quota (bigint): 剩余额度（单位：1/500000 美元）
- used_quota (bigint): 已用额度（单位：1/500000 美元）
- unlimited_quota (int): 是否无限额度（1=是, 0=否）
- expired_time (bigint): 过期时间（UNIX 时间戳，秒，-1=永不过期）
- created_time (bigint): 创建时间（UNIX 时间戳，秒）

常用查询：
- 查看所有 Token：SELECT * FROM tokens
- 查看某个 Token 详情：SELECT * FROM tokens WHERE name=?
- 查看余额不足的 Token：SELECT * FROM tokens WHERE remain_quota < 1000000 AND unlimited_quota=0
- 查看即将过期的 Token：SELECT * FROM tokens WHERE expired_time > 0 AND expired_time < UNIX_TIMESTAMP(NOW() + INTERVAL 7 DAY)

## 表：users（用户表）
存储所有用户的信息。

字段：
- id (int): 用户 ID，主键
- username (varchar): 用户名
- password (varchar): 密码（加密存储）
- display_name (varchar): 显示名称
- role (int): 角色（1=普通用户, 10=管理员, 100=超级管理员）
- status (int): 状态（1=启用, 2=禁用）
- email (varchar): 邮箱
- quota (bigint): 额度（单位：1/500000 美元）
- used_quota (bigint): 已用额度
- request_count (int): 请求次数

常用查询：
- 查看所有用户：SELECT * FROM users
- 查看某个用户详情：SELECT * FROM users WHERE username=?
- 查看用户使用排行：SELECT username, used_quota, request_count FROM users ORDER BY used_quota DESC

## 额度单位说明
NewAPI 的额度单位是 1/500000 美元，即：
- 1 美元 = 500,000 额度单位
- 1 额度单位 = 0.000002 美元

转换公式：
- 额度 → 美元：quota / 500000
- 美元 → 额度：dollars * 500000
"""

# 常用 SQL 模板
SQL_TEMPLATES = {
    "token_balance": "SELECT name, remain_quota, used_quota, unlimited_quota, status FROM tokens WHERE name = %s",
    "token_logs": "SELECT created_at, model_name, quota, use_time FROM logs WHERE token_name = %s AND type = 2 ORDER BY created_at DESC LIMIT %s",
    "channel_health": "SELECT channel_id, COUNT(*) as total, SUM(CASE WHEN type=2 THEN 1 ELSE 0 END) as success FROM logs WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) GROUP BY channel_id",
    "recent_failures": "SELECT channel_id, channel_name, model_name, content, created_at FROM logs WHERE type != 2 ORDER BY created_at DESC LIMIT %s",
    "model_usage": "SELECT model_name, COUNT(*) as calls, SUM(quota) as total_quota FROM logs WHERE type=2 GROUP BY model_name ORDER BY calls DESC LIMIT %s",
}
