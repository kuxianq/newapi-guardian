"""NewAPI Guardian Bot - 消息格式化"""
import html
from datetime import datetime


def safe_text(s: str | None) -> str:
    """清理 Telegram Markdown 中容易破坏格式的字符。"""
    if not s:
        return ""
    return str(s).replace("`", "ʼ").replace("*", "＊").replace("[", "［").replace("]", "］")


def ts_to_str(ts: int | None) -> str:
    if not ts:
        return "N/A"
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def truncate(s: str, max_len: int = 60) -> str:
    s = safe_text(s)
    if not s:
        return ""
    return s[:max_len] + "…" if len(s) > max_len else s


def fmt_overview(stats: dict, fail_channels: list, fail_models: list) -> str:
    enabled = stats.get("enabled_channels", 0)
    disabled = stats.get("disabled_channels", 0)
    reqs = stats.get("recent_requests", 0)
    success = stats.get("recent_success", 0)
    fail = reqs - success if reqs and success else 0
    rate = f"{fail/reqs*100:.1f}%" if reqs else "N/A"

    lines = [
        "📊 *NewAPI 总览*（最近 1 小时）",
        "",
        f"✅ 启用渠道：{enabled}",
        f"⛔ 禁用渠道：{disabled}",
        f"📨 请求总数：{reqs}",
        f"❌ 失败数：{fail}（{rate}）",
    ]

    if fail_channels:
        lines.append("")
        lines.append("🔥 *失败最多的渠道 Top 5*")
        for i, ch in enumerate(fail_channels[:5], 1):
            name = truncate(ch.get("channel_name") or f"ID:{ch['channel_id']}", 30)
            lines.append(f"  {i}. `{name}` — {ch['fail_count']}次")

    if fail_models:
        # 按模型聚合
        model_agg: dict[str, int] = {}
        for row in fail_models:
            m = row["model_name"]
            model_agg[m] = model_agg.get(m, 0) + row["fail_count"]
        top_models = sorted(model_agg.items(), key=lambda x: -x[1])[:5]
        if top_models:
            lines.append("")
            lines.append("🧩 *失败最多的模型 Top 5*")
            for i, (m, cnt) in enumerate(top_models, 1):
                lines.append(f"  {i}. `{truncate(m, 35)}` — {cnt}次")

    return "\n".join(lines)


def fmt_bad_channels(fail_stats: list) -> str:
    if not fail_stats:
        return "✅ 最近 1 小时没有异常渠道。"

    lines = ["🚨 *异常渠道*（最近 1 小时）", ""]
    for ch in fail_stats[:15]:
        name = truncate(ch.get("channel_name") or f"ID:{ch['channel_id']}", 30)
        models = truncate(ch.get("models", ""), 50)
        status_icon = "🟢" if ch.get("status") == 1 else "🔴"
        lines.append(
            f"{status_icon} `{name}` (ID:{ch['channel_id']})\n"
            f"   失败 {ch['fail_count']}次 | 模型: {models}\n"
            f"   最后失败: {ts_to_str(ch.get('last_fail_time'))}"
        )
        lines.append("")
    return "\n".join(lines)


def fmt_model_query(model_name: str, channels: list, fail_stats: list) -> str:
    lines = [f"🧩 *模型: `{model_name}`*", ""]

    if not channels:
        lines.append("未找到支持该模型的启用渠道。")
        return "\n".join(lines)

    # 构建失败映射
    fail_map: dict[int, dict] = {}
    for row in fail_stats:
        if row["model_name"] == model_name:
            fail_map[row["channel_id"]] = row

    lines.append(f"📡 *挂载渠道*（{len(channels)}个启用）")
    for ch in channels:
        cid = ch["id"]
        name = truncate(ch.get("name", ""), 30)
        rt = ch.get("response_time", 0) or 0
        fail_info = fail_map.get(cid)
        if fail_info:
            lines.append(
                f"  🔴 `{name}` (ID:{cid}) — "
                f"失败{fail_info['fail_count']}次 | {rt}ms"
            )
        else:
            lines.append(f"  🟢 `{name}` (ID:{cid}) — {rt}ms")

    return "\n".join(lines)


def fmt_channel_detail(ch: dict, recent_logs: list) -> str:
    if not ch:
        return "❌ 未找到该渠道。"

    status_icon = "🟢" if ch.get("status") == 1 else "🔴"
    # 计算健康度（如果已有 health_score 则直接使用）
    health_score = ch.get("health_score")
    if health_score is None:
        # 简易估算：基于响应时间（越低越好）
        rt = ch.get('response_time') or 0
        # 将响应时间映射到 0-100 区间，假设 0ms => 100, 10s => 0
        health_score = max(0, 100 - int(rt * 10))
    health_display = fmt_health_score(health_score) if isinstance(health_score, int) else str(health_score)
    lines = [
        f"🔌 *渠道详情*",
        "",
        f"ID: `{ch['id']}`",
        f"名称: `{truncate(ch.get('name', ''), 40)}`",
        f"状态: {status_icon} {'启用' if ch.get('status') == 1 else '禁用'}",
        f"健康度: {health_display}",
        f"响应时间: {ch.get('response_time', 'N/A')}ms",
        f"优先级: {ch.get('priority', 0)} | 权重: {ch.get('weight', 0)}",
        f"已用额度: {ch.get('used_quota', 0)}",
        f"自动禁用: {'是' if ch.get('auto_ban') == 1 else '否'}",
    ]

    if ch.get("test_model"):
        lines.append(f"测试模型: `{ch['test_model']}`")
    if ch.get("remark"):
        lines.append(f"备注: {truncate(ch['remark'], 60)}")

    if recent_logs:
        lines.append("")
        lines.append("📋 *最近日志*")
        for log in recent_logs[:10]:
            icon = "✅" if log.get("type") == 2 and not log.get("content") else "❌"
            model = truncate(log.get("model_name", ""), 25)
            content = truncate(log.get("content", ""), 40)
            time_str = ts_to_str(log.get("created_at"))
            line = f"  {icon} {time_str} `{model}` {log.get('use_time', 0)}s"
            if content:
                line += f"\n     {content}"
            lines.append(line)

    return "\n".join(lines)


def fmt_balance_suspects(suspects: list) -> str:
    if not suspects:
        return "✅ 最近 2 小时没有疑似余额不足的渠道。"

    lines = ["💸 *疑似无余额渠道*（最近 2 小时）", ""]
    for ch in suspects[:15]:
        name = truncate(ch.get("channel_name") or f"ID:{ch['channel_id']}", 30)
        models = truncate(ch.get("models", ""), 50)
        lines.append(
            f"  ⚠️ `{name}` (ID:{ch['channel_id']})\n"
            f"     余额相关失败 {ch['balance_fail_count']}次\n"
            f"     涉及模型: {models}"
        )
        lines.append("")
    return "\n".join(lines)


def fmt_slow_channels(slow: list) -> str:
    if not slow:
        return "✅ 最近 1 小时没有特别慢的渠道。"

    lines = ["🐢 *慢渠道排行*（最近 1 小时，平均 >5s）", ""]
    for i, ch in enumerate(slow[:10], 1):
        name = truncate(ch.get("channel_name") or f"ID:{ch['channel_id']}", 30)
        avg_t = ch.get("avg_time", 0) or 0
        max_t = ch.get("max_time", 0) or 0
        cnt = ch.get("request_count", 0)
        lines.append(
            f"  {i}. `{name}` (ID:{ch['channel_id']})\n"
            f"     平均 {avg_t:.1f}s | 最慢 {max_t:.1f}s | {cnt}次请求"
        )
        lines.append("")
    return "\n".join(lines)


def fmt_alert(channel_id: int, channel_name: str, fail_count: int,
              models: str, last_content: str) -> str:
    name = truncate(channel_name or f"ID:{channel_id}", 30)
    return (
        f"🚨 *渠道异常告警*\n\n"
        f"渠道: `{name}` (ID:{channel_id})\n"
        f"连续失败: {fail_count}次\n"
        f"涉及模型: {truncate(models, 60)}\n"
        f"最近错误: {truncate(last_content, 80)}"
    )


def fmt_recovery(channel_id: int, channel_name: str) -> str:
    name = truncate(channel_name or f"ID:{channel_id}", 30)
    return f"✅ *渠道恢复*\n\n渠道: `{name}` (ID:{channel_id}) 已恢复正常。"


# ── 统计格式化 ──

def fmt_quota(q) -> str:
    """把 quota 数字转成可读格式（NewAPI quota 单位是 1/500000 美元）"""
    if not q:
        return "$0"
    usd = float(q) / 500000
    if usd >= 1:
        return f"${usd:.2f}"
    elif usd >= 0.01:
        return f"${usd:.3f}"
    else:
        return f"${usd:.4f}"


def fmt_model_usage(models: list, title: str = "模型使用排行") -> str:
    if not models:
        return f"📊 {title}\n\n暂无数据。"
    lines = [f"📊 *{safe_text(title)}*\n"]
    lines.append("```")
    for i, m in enumerate(models[:20], 1):
        name = safe_text(str(m.get("model_name", "")))[:25]
        calls = m.get("call_count") or m.get("calls", 0)
        quota = fmt_quota(m.get("total_quota") or m.get("quota", 0))
        avg_t = m.get("avg_time")
        time_str = f"{float(avg_t):.0f}s" if avg_t else ""
        lines.append(f"{i:>2}. {name:<25} {calls:>6}次 {quota:>10} {time_str:>4}")
    lines.append("```")
    return "\n".join(lines)


def fmt_today_stats(stats: dict, models: list, yesterday_stats: dict = None) -> str:
    calls = stats.get("total_calls", 0)
    quota = fmt_quota(stats.get("total_quota", 0))
    prompt = stats.get("total_prompt", 0)
    completion = stats.get("total_completion", 0)

    lines = [
        "📅 *今日统计*\n",
        f"📨 总请求: {calls}",
        f"💰 总消耗: {quota}",
        f"📝 Prompt tokens: {prompt:,}",
        f"✍️ Completion tokens: {completion:,}",
    ]
    
    # 添加昨日对比
    if yesterday_stats:
        y_calls = yesterday_stats.get("total_calls", 0)
        y_quota = yesterday_stats.get("total_quota", 0)
        
        if y_calls > 0:
            calls_diff = calls - y_calls
            calls_pct = (calls_diff / y_calls * 100) if y_calls > 0 else 0
            calls_icon = "🔺" if calls_diff > 0 else "🔻" if calls_diff < 0 else "➡️"
            
            quota_diff = stats.get("total_quota", 0) - y_quota
            quota_pct = (quota_diff / y_quota * 100) if y_quota > 0 else 0
            quota_icon = "🔺" if quota_diff > 0 else "🔻" if quota_diff < 0 else "➡️"
            
            lines.append("\n📈 *对比昨日*")
            lines.append(f"{calls_icon} 请求: {calls_diff:+,} ({calls_pct:+.1f}%)")
            lines.append(f"{quota_icon} 消耗: {quota_diff:+,} ({quota_pct:+.1f}%)")

    if models:
        lines.append("\n🧩 *今日模型 Top 15*")
        lines.append("```")
        for i, m in enumerate(models[:15], 1):
            name = safe_text(str(m.get("model_name", "")))[:25]
            calls_m = m.get("calls", 0)
            quota_m = fmt_quota(m.get("quota", 0))
            lines.append(f"{i:>2}. {name:<25} {calls_m:>5}次 {quota_m:>10}")
        lines.append("```")

    return "\n".join(lines)


def fmt_user_usage(users: list) -> str:
    if not users:
        return "👤 *用户使用统计*\n\n暂无数据。"
    lines = ["👤 *用户使用统计*\n"]
    lines.append("```")
    for i, u in enumerate(users[:10], 1):
        name = (safe_text(str(u.get("username", "未知"))) or "未知")[:20]
        calls = u.get("calls", 0)
        quota = fmt_quota(u.get("quota", 0))
        lines.append(f"{i:>2}. {name:<20} {calls:>6}次 {quota:>10}")
    lines.append("```")
    return "\n".join(lines)


def fmt_token_usage(tokens: list) -> str:
    if not tokens:
        return "🔑 *Token 使用统计*\n\n暂无数据。"
    lines = ["🔑 *Token 使用统计*\n"]
    lines.append("```")
    for i, t in enumerate(tokens[:10], 1):
        name = (safe_text(str(t.get("token_name", "未知"))) or "未知")[:20]
        calls = t.get("calls", 0)
        quota = fmt_quota(t.get("quota", 0))
        lines.append(f"{i:>2}. {name:<20} {calls:>6}次 {quota:>10}")
    lines.append("```")
    return "\n".join(lines)


def fmt_console(stats: dict, today_models: list, all_models: list,
                users: list, tokens: list) -> str:
    """仿 console 页面的综合面板"""
    calls = stats.get("total_calls", 0)
    quota = fmt_quota(stats.get("total_quota", 0))
    prompt = stats.get("total_prompt", 0)
    completion = stats.get("total_completion", 0)

    lines = [
        "🖥️ *NewAPI Console*\n",
        "━━━ 📅 今日概览 ━━━",
        f"  📨 请求: {calls}",
        f"  💰 消耗: {quota}",
        f"  📝 Prompt: {prompt:,} tokens",
        f"  ✍️ Completion: {completion:,} tokens",
    ]

    if today_models:
        lines.append("\n━━━ 🧩 今日模型 Top 10 ━━━")
        lines.append("```")
        for i, m in enumerate(today_models[:10], 1):
            name = safe_text(str(m.get("model_name", "")))[:22]
            c = m.get("calls", 0)
            q = fmt_quota(m.get("quota", 0))
            bar = "█" * min(int(c / max(today_models[0].get("calls", 1), 1) * 8), 8)
            lines.append(f"{i:>2}. {name:<22} {bar:<8} {c:>4}次 {q:>9}")
        lines.append("```")

    if all_models:
        lines.append("\n━━━ 📊 历史模型 Top 10 ━━━")
        lines.append("```")
        for i, m in enumerate(all_models[:10], 1):
            name = safe_text(str(m.get("model_name", "")))[:22]
            c = m.get("call_count", 0)
            q = fmt_quota(m.get("total_quota", 0))
            bar = "█" * min(int(c / max(all_models[0].get("call_count", 1), 1) * 8), 8)
            lines.append(f"{i:>2}. {name:<22} {bar:<8} {c:>6}次 {q:>12}")
        lines.append("```")

    if users:
        lines.append("\n━━━ 👤 用户排行 ━━━")
        lines.append("```")
        for i, u in enumerate(users[:5], 1):
            name = (safe_text(str(u.get("username", "未知"))) or "未知")[:15]
            c = u.get("calls", 0)
            q = fmt_quota(u.get("quota", 0))
            lines.append(f"{i:>2}. {name:<15} {c:>6}次 {q:>12}")
        lines.append("```")

    if tokens:
        lines.append("\n━━━ 🔑 Token 排行 ━━━")
        lines.append("```")
        for i, t in enumerate(tokens[:5], 1):
            name = (safe_text(str(t.get("token_name", "未知"))) or "未知")[:15]
            c = t.get("calls", 0)
            q = fmt_quota(t.get("quota", 0))
            lines.append(f"{i:>2}. {name:<15} {c:>6}次 {q:>12}")
        lines.append("```")

    return "\n".join(lines)


def fmt_batch_status_result(results: list[dict], new_status: int) -> str:
    action = "启用" if new_status == 1 else "禁用"
    icon_ok = "🟢" if new_status == 1 else "🔴"
    success = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    lines = [
        f"{icon_ok} *批量{action}结果*",
        "",
        f"✅ 成功: {len(success)} | ❌ 失败: {len(failed)}",
    ]
    if success:
        lines.append("")
        lines.append("*成功渠道:*")
        for row in success:
            display_name = row.get("name") or f"ID:{row['id']}"
            lines.append(f"  ✅ `{truncate(display_name, 30)}` (ID:{row['id']})")
    if failed:
        lines.append("")
        lines.append("*失败渠道:*")
        for row in failed:
            display_name = row.get("name") or f"ID:{row['id']}"
            lines.append(
                f"  ❌ `{truncate(display_name, 30)}` (ID:{row['id']})\n"
                f"     {truncate(str(row.get('message', '未知错误')), 80)}"
            )
    return "\n".join(lines)


def fmt_disable_failed_preview(fail_stats: list[dict], threshold: int) -> str:
    lines = [
        f"⚠️ *一键禁用失败渠道确认*",
        "",
        f"条件: 最近 1 小时失败次数 ≥ `{threshold}`",
        f"命中渠道: `{len(fail_stats)}`",
        "",
    ]
    affected_models = set()
    for row in fail_stats:
        name = truncate(row.get("channel_name") or f"ID:{row['channel_id']}", 28)
        models = row.get("models") or ""
        if models:
            for m in models.split(","):
                if m.strip():
                    affected_models.add(m.strip())
        lines.append(
            f"  🔴 `{name}` (ID:{row['channel_id']})\n"
            f"     失败 {row.get('fail_count', 0)} 次 | 模型: {truncate(models, 50) or '未知'}"
        )
    if affected_models:
        model_text = ", ".join(sorted(affected_models)[:12])
        if len(affected_models) > 12:
            model_text += f" 等 {len(affected_models)} 个模型"
        lines.extend(["", f"影响模型: {safe_text(model_text)}"])
    return "\n".join(lines)


def fmt_health_score(score: int) -> str:
    if score >= 85:
        return f"🟢 {score}"
    if score >= 70:
        return f"🟡 {score}"
    if score >= 50:
        return f"🟠 {score}"
    return f"🔴 {score}"


def fmt_channels_overview(channels: list[dict]) -> str:
    if not channels:
        return "🔌 *渠道列表*\n\n暂无渠道数据。"
    lines = ["🔌 *渠道列表 / 健康度*", "", "```"]
    for ch in channels[:30]:
        status = "ON" if ch.get("status") == 1 else "OFF"
        score = fmt_health_score(int(ch.get("health_score", 0)))
        name = safe_text(str(ch.get("name", "")))[:16]
        lines.append(f"{ch['id']:>4} {status:<3} {score:<6} {name}")
    lines.append("```")
    if len(channels) > 30:
        lines.append(f"... 共 {len(channels)} 个渠道")
    return "\n".join(lines)


def fmt_recent_logs(logs: list[dict]) -> str:
    """格式化最近使用日志（最多 10 条）。

    示例行：
    ✅ 11:01 | 流 | 渠道1
    gpt-4o
    👤 12345 | 🔑 mytoken
    ⏱️ 15.2s | 📥 444→📤 328
    💰 $11.23 | 🌐 127.0.0.1
    """
    if not logs:
        return "✅ 最近没有使用日志。"
    lines = ["📋 最近10条使用日志", "━━━━━━━━━━━━━━━━━━", ""]
    for log in logs[:10]:
        # 状态图标
        log_type = log.get("type", 2)
        status_icon = "✅" if log_type == 2 else "❌"
        
        # 时间（只显示 HH:MM）
        created_at = log.get("created_at", 0)
        if created_at:
            full_time = ts_to_str(created_at)
            time_str = full_time.split()[1][:5] if ' ' in full_time else full_time[:5]
        else:
            time_str = "??:??"
        
        # 流式标识
        is_stream = log.get("is_stream", 0)
        stream_text = "流" if is_stream == 1 else "非流"
        
        # 渠道
        channel_name = log.get("channel_name") or f"渠道{log.get('channel_id', '?')}"
        channel_text = truncate(channel_name, 20)
        
        # 第一行：状态 | 时间 | 流式 | 渠道
        lines.append(f"{status_icon} {time_str} | {stream_text} | {safe_text(channel_text)}")
        
        # 第二行：模型（失败时标记）
        model = truncate(log.get("model_name", "unknown"), 30)
        if log_type != 2:
            model += " [失败]"
        lines.append(model)
        
        # 第三行：用户 | 令牌
        user_id = log.get("user_id", "?")
        token_name = truncate(log.get("token_name", "?"), 10)
        lines.append(f"👤 {user_id} | 🔑 {token_name}")
        
        # 第四行：用时 | tokens
        use_time = log.get("use_time", 0)
        use_time_s = f"{use_time / 1000:.1f}s" if use_time else "0s"
        prompt = log.get("prompt_tokens", 0)
        completion = log.get("completion_tokens", 0)
        lines.append(f"⏱️ {use_time_s} | 📥 {prompt}→📤 {completion}")
        
        # 第五行：花费 | IP
        quota = log.get("quota", 0)
        cost = fmt_quota(quota) if quota else "$0.00"
        ip = log.get("ip", "unknown")
        lines.append(f"💰 {cost} | 🌐 {ip}")
        
        lines.append("")  # 空行分隔
    
    return "\n".join(lines)


