# NewAPI Guardian Bot - 更新日志

## [v2.2.0] - 2026-05-06

### ✨ 交互体验

- 将 Telegram 主菜单整理为二级结构：状态概览、统计报表、渠道管理、数据安全、AI 设置。
- 统计、渠道、数据和 AI 相关按钮下沉到分类页，减少主菜单按钮拥挤。

### 📊 状态概览增强

- 状态页新增健康度评分、最近 1 小时成功率、今日请求量、今日消耗和 Token 总量。
- 新增渠道摘要：启用 / 禁用、异常渠道、慢渠道、疑似余额问题。
- 新增模型异常 Top、失败渠道 Top 和当前建议，让状态页更像值班首页。

### 🔧 稳定性修复

- 修复批量测试在 Telegram Bot 事件循环内可能触发 `coroutine was never awaited` 的问题。
- 修复一键禁用失败渠道确认按钮的 callback 解析问题。
- Agent 确认按钮改为短 ID + 内存 pending store，避免 Telegram callback_data 超长。
- 数据库恢复确认改为短 ID，并校验备份文件名必须来自备份列表。

---

## [v2.1.0] - 2026-05-02

### 🔧 Bug 修复

#### 1. 修复禁用渠道功能失败 (Critical)
- **问题**: `/disable` 和 `/enable` 命令一直失败，返回 404 错误
- **根因**: 使用了不存在的 API 端点 `POST /api/channel/{id}/status`
- **修复**: 改用正确的 NewAPI 接口流程
  - 先通过 `GET /api/channel/{id}` 获取渠道完整信息
  - 修改 `status` 字段
  - 通过 `PUT /api/channel/` 更新整个渠道对象
- **影响文件**: `newapi_client.py` - `set_channel_status()` 函数

#### 2. 修复 import 顺序问题
- **问题**: `test_channel()` 函数中 `import urllib.parse` 在使用之后
- **修复**: 将 import 语句移到函数开头
- **影响文件**: `newapi_client.py` - `test_channel()` 函数

### ✨ 新功能

#### 1. 批量测试渠道
- **功能**: 支持一次测试多个渠道
- **用法**: 
  - `/test 105` - 测试单个渠道（保留原有详细输出）
  - `/test 105 106 107` - 批量测试多个渠道
- **输出**: 
  - 汇总统计（成功/失败数量）
  - 失败渠道列表（带错误信息）
  - 成功渠道列表（带响应时间）
- **实现**: 
  - 新增 `test_channels_batch()` API 函数
  - 修改 `cmd_test()` 命令处理逻辑
  - 自动间隔 0.5 秒避免请求过快
- **影响文件**: 
  - `newapi_client.py` - 新增 `test_channels_batch()` 函数
  - `bot.py` - 修改 `cmd_test()` 函数

### 🔄 代码优化

#### 1. 统一 import 管理
- 将 `newapi_client` 的函数统一在文件顶部 import
- 移除函数内部的重复 import
- **影响文件**: `bot.py`

#### 2. 清理冗余代码
- 删除重复的 `test_channel_fixed()` 函数
- 统一使用 `test_channel()` 函数
- **影响文件**: `newapi_client.py`

### 📝 文档更新

- 更新 `/test` 命令帮助文本，说明批量测试用法
- 添加 `set_channel_status()` 函数注释，说明修复原因
- 添加 `test_channels_batch()` 函数完整文档字符串

---

## 后续优化建议 (Phase 3)

### 🎯 高优先级

1. **操作确认机制**
   - 禁用/启用渠道前增加确认步骤（参考官方文档的 10 秒等待）
   - 批量操作前显示影响范围并要求确认
   - 实现方式：使用 Telegram InlineKeyboard 确认按钮

2. **错误处理增强**
   - 增加 API 请求重试机制（最多 3 次，指数退避）
   - 更详细的错误信息分类（网络错误、权限错误、业务错误）
   - 失败时提供可能的解决方案提示

3. **批量操作扩展**
   - 批量启用/禁用渠道：`/enable 105 106 107`
   - 按条件批量操作：`/disable_failed` 禁用所有失败渠道
   - 按分组批量操作：`/test_group default`

### 🔧 中优先级

4. **性能优化**
   - 批量测试改用并发（asyncio.gather）而不是串行
   - 增加测试超时配置（当前硬编码 60 秒）
   - 缓存渠道列表，减少数据库查询

5. **统计增强**
   - 渠道健康度评分（基于成功率、响应时间、失败频率）
   - 渠道可用性趋势图（7 天/30 天）
   - 模型 → 渠道映射关系可视化

6. **通知优化**
   - 渠道连续失败 N 次后自动通知
   - 每日健康报告增加对比分析（与昨日/上周对比）
   - 支持自定义通知规则

### 💡 低优先级

7. **高级功能**
   - 渠道测试历史记录（保存到数据库）
   - 导出测试报告（CSV/JSON）
   - Web Dashboard（可选，如果需要更丰富的可视化）

8. **用户体验**
   - 命令自动补全提示
   - 更丰富的 emoji 和格式化
   - 支持自然语言查询（"最近一小时失败最多的渠道"）

---

## 技术债务

- [ ] 统一错误处理模式（当前部分函数返回 dict，部分抛异常）
- [ ] 增加单元测试覆盖
- [ ] 配置文件验证（启动时检查必需配置项）
- [ ] 日志级别可配置化
- [ ] API 客户端支持连接池复用

---

## 已知限制

1. **NewAPI API 限制**
   - 更新渠道需要传递完整对象，无法只更新单个字段
   - 测试接口无法指定超时时间
   - 批量操作需要逐个调用 API

2. **Telegram Bot 限制**
   - 单条消息最大 4096 字符
   - 批量测试结果过多时需要分页或截断
   - 按钮数量限制（每行最多 8 个，总共最多 100 个）

---

## 升级指南

### 从 v2.0 升级到 v2.1

1. 停止服务
```bash
sudo systemctl stop newapi-guardian.service
```

2. 更新代码
```bash
cd /root/.openclaw/workspace/services/newapi-guardian
# 代码已更新
```

3. 重启服务
```bash
sudo systemctl restart newapi-guardian.service
```

4. 验证
```bash
# 检查服务状态
sudo systemctl status newapi-guardian.service

# 测试禁用功能（替换为实际渠道 ID）
# /disable 105
# /enable 105

# 测试批量测试功能
# /test 105 106 107
```

### 配置变更

本次更新无需修改配置文件。

---

## 贡献者

- Rem 💕 - 主要开发与维护
