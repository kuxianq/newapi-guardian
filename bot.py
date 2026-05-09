"""NewAPI Guardian Bot - Telegram Bot 主入口 v2"""
import logging
import asyncio
from pathlib import PurePath
from uuid import uuid4
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    BOT_TOKEN, AUTHORIZED_IDS, CHECK_INTERVAL_MINUTES, DAILY_REPORT_HOUR,
    BACKUP_DIR,
)
import db as newapi_db
from formatter import (
    fmt_overview, fmt_model_query, fmt_channel_detail,
    fmt_slow_channels, fmt_batch_status_result, fmt_disable_failed_preview,
    truncate, ts_to_str, safe_text, fmt_alert, fmt_recovery, fmt_health_score,
    fmt_recent_logs,
)
from menus import (
    ai_menu_kb,
    back_btn,
    channels_menu_kb,
    data_menu_kb,
    diagnose_menu_kb,
    main_menu_kb as build_main_menu_kb,
    newapi_docs_menu_kb,
    stats_menu_kb,
    status_kb,
    status_menu_kb,
)
from backup import create_backup, list_backups, restore_backup
from newapi_client import test_channel as api_test_channel, async_test_channels_batch, set_channel_status as api_set_channel_status
from core.diagnostics import diagnose_failure_scope
from tools_new.formatter import format_tool_output
from ai_config import load_config, set_url as ai_set_url, set_key as ai_set_key, set_model as ai_set_model, set_enabled as ai_set_enabled, get_mode_enabled, set_mode_enabled
# from ai_brain import handle_ai_message, ai_callback_handler  # 旧版
from agent_handler import handle_agent_message, agent_callback_handler  # Agent 模式
from tg_safe import safe_reply, safe_edit, safe_send

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("guardian")

BOT_VERSION = "v2.3.0"

# 会话状态
CONFIRM_RESTORE = 1
PENDING_RESTORE_KEY = "pending_restores"


def _create_pending_restore(context: ContextTypes.DEFAULT_TYPE, filename: str) -> str:
    """Store a validated restore target behind a short callback id."""
    restore_id = uuid4().hex[:12]
    pending = context.user_data.setdefault(PENDING_RESTORE_KEY, {})
    pending[restore_id] = filename
    return restore_id


def _pop_valid_pending_restore(context: ContextTypes.DEFAULT_TYPE, restore_id: str) -> str | None:
    """Return a pending restore filename only if it is still in the known backup list."""
    pending = context.user_data.get(PENDING_RESTORE_KEY, {})
    filename = pending.pop(restore_id, None)
    if not filename or PurePath(filename).name != filename:
        return None
    known_names = {backup["filename"] for backup in list_backups()}
    return filename if filename in known_names else None


def _parse_channel_ids(args: list[str]) -> list[int]:
    ids = []
    for arg in args:
        ids.append(int(arg))
    return ids


def _channel_label(ch: dict | None, cid: int) -> str:
    if not ch:
        return f"ID:{cid}"
    return ch.get("name") or f"ID:{cid}"


def _channel_models(ch: dict | None) -> list[str]:
    if not ch:
        return []
    raw = ch.get("models") or ""
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_batch_impact(channel_ids: list[int]) -> tuple[int, list[str]]:
    models = set()
    count = 0
    for cid in channel_ids:
        ch = newapi_db.get_channel_by_id(cid)
        if not ch:
            continue
        count += 1
        models.update(_channel_models(ch))
    return count, sorted(models)


async def _execute_batch_status(update_or_query, channel_ids: list[int], new_status: int, edit: bool = False):
    results = []
    for cid in channel_ids:
        ch = newapi_db.get_channel_by_id(cid)
        if not ch:
            results.append({"id": cid, "name": f"ID:{cid}", "success": False, "message": "渠道不存在"})
            continue
        result = api_set_channel_status(cid, new_status)
        results.append({
            "id": cid,
            "name": _channel_label(ch, cid),
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
        })
    text = fmt_batch_status_result(results, new_status)
    if edit:
        await safe_edit(update_or_query, text, reply_markup=back_btn())
    else:
        await safe_reply(update_or_query, text, reply_markup=back_btn())


# ── 权限 ──
def authorized(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else 0
        if uid not in AUTHORIZED_IDS:
            msg = update.effective_message or (update.callback_query and update.callback_query.message)
            if msg:
                await safe_reply(msg, "⛔ 无权限。")
            return
        return await func(update, context)
    return wrapper


# ── 菜单 ──
def main_menu_kb():
    return build_main_menu_kb(get_mode_enabled())


# ── 命令处理 ──

@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update.message, "🤖 *NewAPI Guardian*\n━━━━━━━━━━━━━━━━━━\n📊 监控 · 管理 · 备份\n━━━━━━━━━━━━━━━━━━\n💕 Made with love by Rem\n\n你的 NewAPI 渠道监控管家。\n点击下方按钮或使用命令查询。", reply_markup=main_menu_kb())


@authorized
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update.message, "🤖 *NewAPI Guardian*\n━━━━━━━━━━━━━━━━━━\n📊 监控 · 管理 · 备份\n━━━━━━━━━━━━━━━━━━\n💕 Made with love by Rem", reply_markup=main_menu_kb())


def build_overview_text(minutes: int = 60) -> str:
    """Build the richer status overview shared by /status and inline buttons."""
    stats = newapi_db.get_overview_stats(minutes=minutes)
    fail_ch = newapi_db.get_channel_failure_stats(minutes=minutes)
    fail_m = newapi_db.get_model_failure_stats(minutes=minutes)
    today = newapi_db.get_today_stats()
    slow = newapi_db.get_slow_channels(minutes=minutes)
    balance = newapi_db.get_balance_suspect_channels(minutes=120)
    return fmt_overview(stats, fail_ch, fail_m, today, slow, balance)


@authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_overview_text(minutes=60)
    text += "\n\n🌷 *快捷入口*\n点下面按钮继续查看统计、渠道和主菜单。"
    await safe_reply(update.message, text, reply_markup=status_kb())





@authorized
async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法: `/model 模型名`\n例如: `/model gpt-5.4`")
        return
    model_name = " ".join(context.args)
    channels = newapi_db.get_model_channels(model_name)
    fail_stats = newapi_db.get_model_failure_stats(minutes=60)
    text = fmt_model_query(model_name, channels, fail_stats)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法: `/channel 渠道ID`\n例如: `/channel 105`")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await safe_reply(update.message, "❌ 请输入数字渠道 ID。")
        return
    ch = newapi_db.get_channel_by_id(cid)
    health_map = newapi_db.get_channel_health_scores(minutes=1440)
    if ch and cid in health_map:
        ch = {**ch, "health_score": health_map[cid]["health_score"]}
    logs = newapi_db.get_channel_recent_logs(cid, minutes=60)
    text = fmt_channel_detail(ch, logs)
    # 添加操作按钮
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧪 测试", callback_data=f"test_{cid}"),
            InlineKeyboardButton("🔴 禁用" if ch and ch.get("status") == 1 else "🟢 启用",
                                 callback_data=f"toggle_{cid}"),
        ],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="menu")],
    ])
    await safe_reply(update.message, text, reply_markup=buttons)





@authorized
async def cmd_slow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slow = newapi_db.get_slow_channels(minutes=60)
    text = fmt_slow_channels(slow)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = newapi_db.get_overview_stats(minutes=1440)
    fail_ch = newapi_db.get_channel_failure_stats(minutes=1440)
    fail_m = newapi_db.get_model_failure_stats(minutes=1440)
    today = newapi_db.get_today_stats()
    slow = newapi_db.get_slow_channels(minutes=1440)
    balance = newapi_db.get_balance_suspect_channels(minutes=1440)
    text = fmt_overview(stats, fail_ch, fail_m, today, slow, balance).replace("最近 1h", "最近 24h")
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法:\n`/test 105` — 测试单渠道\n`/test 105 106 107` — 批量测试多个渠道\n`/test_model gpt-5.4` — 测试某模型所有渠道\n`/test_all` — 测试全部启用渠道")
        return
    
    # 解析渠道 ID 列表
    channel_ids = []
    for arg in context.args:
        try:
            cid = int(arg)
            channel_ids.append(cid)
        except ValueError:
            await safe_reply(update.message, f"❌ 无效的渠道 ID: `{arg}`")
            return
    
    if not channel_ids:
        await safe_reply(update.message, "❌ 请输入至少一个渠道 ID。")
        return
    
    # 单个渠道测试（保留原有详细输出）
    if len(channel_ids) == 1:
        cid = channel_ids[0]
        ch = newapi_db.get_channel_by_id(cid)
        if not ch:
            await safe_reply(update.message, f"❌ 渠道 {cid} 不存在。")
            return
        msg = await safe_reply(update.message, f"🧪 正在测试渠道 `{safe_text(ch.get('name',''))}` (ID:{cid})...")
        result = api_test_channel(cid, ch.get("test_model", ""))
        icon = "✅" if result["success"] else "❌"
        text = (
            f"{icon} *渠道测试结果*\n\n"
            f"渠道: `{safe_text(ch.get('name',''))}` (ID:{cid})\n"
            f"结果: {'成功' if result['success'] else '失败'}\n"
            f"耗时: {result.get('time', 0):.1f}s\n"
        )
        if result.get("message"):
            text += f"信息: {safe_text(str(result['message'])[:100])}"
        await safe_edit(msg, text, reply_markup=back_btn())
        return
    
    # 批量测试
    msg = await safe_reply(
        update.message,
        f"🧪 正在批量测试 {len(channel_ids)} 个渠道，请稍候...",
    )
    
    # 调用批量测试 API
    batch_result = await async_test_channels_batch(channel_ids)
    
    # 格式化结果
    lines = [
        f"🧪 *批量渠道测试*\n",
        f"✅ 成功: {batch_result['success_count']} | ❌ 失败: {batch_result['failed_count']}\n",
    ]
    
    # 先列失败的
    failed = [r for r in batch_result['results'] if not r['success']]
    if failed:
        lines.append("*失败渠道:*")
        for r in failed:
            ch = newapi_db.get_channel_by_id(r['id'])
            name = truncate(ch.get('name', '') if ch else f"ID:{r['id']}", 25)
            msg_text = truncate(str(r.get('message', '')), 30)
            lines.append(f"  ❌ `{name}` (ID:{r['id']}) {r.get('time',0):.1f}s")
            if msg_text:
                lines.append(f"     {msg_text}")
    
    # 再列成功的
    passed = [r for r in batch_result['results'] if r['success']]
    if passed:
        lines.append(f"\n*成功渠道 ({len(passed)}个):*")
        for r in passed:
            ch = newapi_db.get_channel_by_id(r['id'])
            name = truncate(ch.get('name', '') if ch else f"ID:{r['id']}", 25)
            lines.append(f"  ✅ `{name}` (ID:{r['id']}) {r.get('time',0):.1f}s")
    
    await safe_edit(msg, "\n".join(lines), reply_markup=back_btn())


@authorized
async def cmd_test_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法: `/test_model gpt-5.4`")
        return
    model_name = " ".join(context.args)
    channels = newapi_db.get_model_channels(model_name)
    if not channels:
        await safe_reply(update.message, f"❌ 没有找到支持 `{safe_text(model_name)}` 的启用渠道。")
        return
    msg = await safe_reply(
        update.message,
        f"🧪 正在测试模型 `{safe_text(model_name)}` 的 {len(channels)} 个渠道...",
    )
    results = []
    for ch in channels:
        r = api_test_channel(ch["id"], model_name)
        results.append((ch, r))
    ok = sum(1 for _, r in results if r["success"])
    fail = len(results) - ok
    lines = [f"🧪 *模型测试: `{safe_text(model_name)}`*\n",
             f"✅ 成功: {ok} | ❌ 失败: {fail}\n"]
    for ch, r in results:
        icon = "✅" if r["success"] else "❌"
        name = truncate(ch.get("name", ""), 25)
        t = f"{r.get('time', 0):.1f}s"
        lines.append(f"  {icon} `{name}` (ID:{ch['id']}) {t}")
    await safe_edit(msg, "\n".join(lines), reply_markup=back_btn())


@authorized
async def cmd_test_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = newapi_db.get_enabled_channels()
    if not channels:
        await safe_reply(update.message, "❌ 没有启用的渠道。")
        return
    msg = await safe_reply(
        update.message,
        f"🧪 正在并发测试全部 {len(channels)} 个启用渠道，请稍候...",
    )
    
    # 并发测试
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    def test_one(ch):
        model = ch.get("test_model", "") or ""
        return (ch, api_test_channel(ch["id"], model))
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = [loop.run_in_executor(executor, test_one, ch) for ch in channels]
        results = await asyncio.gather(*tasks)
    
    ok = sum(1 for _, r in results if r["success"])
    fail = len(results) - ok
    lines = [f"🧪 *全量渠道测试*\n", f"✅ 成功: {ok} | ❌ 失败: {fail}\n"]
    # 先列失败的
    failed = [(ch, r) for ch, r in results if not r["success"]]
    if failed:
        lines.append("*失败渠道:*")
        for ch, r in failed:
            name = truncate(ch.get("name", ""), 25)
            lines.append(f"  ❌ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
    # 再列成功的（简略）
    passed = [(ch, r) for ch, r in results if r["success"]]
    if passed:
        lines.append(f"\n*成功渠道 ({len(passed)}个):*")
        for ch, r in passed[:20]:
            name = truncate(ch.get("name", ""), 25)
            lines.append(f"  ✅ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
        if len(passed) > 20:
            lines.append(f"  ... 还有 {len(passed)-20} 个")
    await safe_edit(msg, "\n".join(lines), reply_markup=back_btn())


# ── 备份命令 ──

@authorized
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await safe_reply(update.message, "💾 正在备份数据库...")
    ok, info, filepath = create_backup(tag="manual")
    if ok:
        text = f"✅ {info}"
        # 如果文件小于 50MB，发送到 TG
        if filepath and filepath.stat().st_size < 50 * 1024 * 1024:
            try:
                await update.message.reply_document(
                    document=open(filepath, "rb"),
                    filename=filepath.name,
                    caption="💾 NewAPI 数据库备份",
                )
            except Exception as e:
                text += f"\n⚠️ 文件发送失败: {e}"
    else:
        text = f"❌ {info}"
    await safe_edit(msg, text, reply_markup=back_btn())


@authorized
async def cmd_backup_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    backups = list_backups()
    if not backups:
        await safe_reply(update.message, "📂 没有找到备份文件。", reply_markup=back_btn())
        return
    lines = ["📂 *备份列表*\n"]
    for i, b in enumerate(backups[:15], 1):
        lines.append(f"  {i}. `{b['filename']}`\n     {b['created']} | {b['size_mb']}MB")
    lines.append(f"\n共 {len(backups)} 份备份")
    lines.append("\n恢复用法: `/restore 文件名`")
    await safe_reply(update.message, "\n".join(lines), reply_markup=back_btn())


@authorized
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        backups = list_backups()
        if not backups:
            await safe_reply(update.message, "❌ 没有可用备份。")
            return
        lines = ["用法: `/restore 文件名`\n\n可用备份:"]
        for b in backups[:10]:
            lines.append(f"  `{b['filename']}`")
        await safe_reply(update.message, "\n".join(lines))
        return
    filename = context.args[0]
    if PurePath(filename).name != filename or filename not in {b["filename"] for b in list_backups()}:
        await safe_reply(update.message, "❌ 备份文件不存在或文件名无效。", reply_markup=back_btn())
        return
    restore_id = _create_pending_restore(context, filename)
    await safe_reply(
        update.message,
        f"⚠️ *确认恢复数据库？*\n\n"
        f"将恢复: `{safe_text(filename)}`\n"
        f"恢复前会自动备份当前状态。\n\n"
        f"⚠️ 这会覆盖当前数据库！",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 确认恢复", callback_data=f"confirm_restore:{restore_id}"),
                InlineKeyboardButton("❌ 取消", callback_data="menu"),
            ]
        ]),
    )


@authorized
async def cmd_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法: `/enable 渠道ID [渠道ID ...]`")
        return
    try:
        ids = _parse_channel_ids(context.args)
    except ValueError:
        await safe_reply(update.message, "❌ 渠道 ID 必须是数字。")
        return
    if len(ids) == 1:
        await _execute_batch_status(update.message, ids, 1)
        return
    affected_count, affected_models = _build_batch_impact(ids)
    ids_str = ",".join(map(str, ids))
    model_text = ", ".join(affected_models[:12]) if affected_models else "无"
    if len(affected_models) > 12:
        model_text += f" 等 {len(affected_models)} 个模型"
    await safe_reply(
        update.message,
        f"⚠️ *批量启用确认*\n\n"
        f"渠道数: `{affected_count}` / {len(ids)}\n"
        f"渠道ID: `{ids_str}`\n"
        f"影响模型: {safe_text(model_text)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 确认启用", callback_data=f"confirm_enable_{ids_str}"),
            InlineKeyboardButton("❌ 取消", callback_data="menu"),
        ]]),
    )


@authorized
async def cmd_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update.message, "用法: `/disable 渠道ID [渠道ID ...]`")
        return
    try:
        ids = _parse_channel_ids(context.args)
    except ValueError:
        await safe_reply(update.message, "❌ 渠道 ID 必须是数字。")
        return
    if len(ids) == 1:
        cid = ids[0]
        ch = newapi_db.get_channel_by_id(cid)
        models = ", ".join(_channel_models(ch)[:12]) if ch else "无"
        await safe_reply(
            update.message,
            f"⚠️ *禁用确认*\n\n渠道: `{safe_text(_channel_label(ch, cid))}` (ID:{cid})\n影响模型: {safe_text(models or '无')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ 确认禁用", callback_data=f"confirm_disable_{cid}"),
                InlineKeyboardButton("❌ 取消", callback_data="menu"),
            ]]),
        )
        return
    affected_count, affected_models = _build_batch_impact(ids)
    ids_str = ",".join(map(str, ids))
    model_text = ", ".join(affected_models[:12]) if affected_models else "无"
    if len(affected_models) > 12:
        model_text += f" 等 {len(affected_models)} 个模型"
    await safe_reply(
        update.message,
        f"⚠️ *批量禁用确认*\n\n"
        f"渠道数: `{affected_count}` / {len(ids)}\n"
        f"渠道ID: `{ids_str}`\n"
        f"影响模型: {safe_text(model_text)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 确认禁用", callback_data=f"confirm_disable_{ids_str}"),
            InlineKeyboardButton("❌ 取消", callback_data="menu"),
        ]]),
    )


@authorized
async def cmd_disable_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    threshold = 5
    if context.args:
        try:
            threshold = int(context.args[0])
        except ValueError:
            await safe_reply(update.message, "❌ 阈值必须是数字。")
            return
    fail_stats = newapi_db.get_channel_failure_stats(minutes=60)
    matched = [row for row in fail_stats if int(row.get("fail_count", 0)) >= threshold and row.get("status") == 1]
    if not matched:
        await safe_reply(update.message, f"✅ 最近 1 小时没有失败 ≥ {threshold} 次的启用渠道。", reply_markup=back_btn())
        return
    ids = [row["channel_id"] for row in matched]
    preview = fmt_disable_failed_preview(matched, threshold)
    ids_str = ",".join(map(str, ids))
    await safe_reply(
        update.message,
        preview,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 确认一键禁用", callback_data=f"confirm_disable_failed_{threshold}_{ids_str}"),
            InlineKeyboardButton("❌ 取消", callback_data="menu"),
        ]]),
    )



@authorized
async def cmd_console(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """仿 console 综合面板"""
    from formatter import fmt_console
    stats = newapi_db.get_today_stats()
    today_models = newapi_db.get_today_model_usage(15)
    all_models = newapi_db.get_model_usage_stats(0, 10)
    users = newapi_db.get_user_usage_stats(5)
    tokens = newapi_db.get_token_usage_stats(5)
    text = fmt_console(stats, today_models, all_models, users, tokens)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """模型使用排行"""
    from formatter import fmt_model_usage
    models = newapi_db.get_model_usage_stats(0, 20)
    text = fmt_model_usage(models, "模型使用排行（全部时间）")
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """今日统计"""
    from formatter import fmt_today_stats
    stats = newapi_db.get_today_stats()
    yesterday_stats = newapi_db.get_yesterday_stats()
    models = newapi_db.get_today_model_usage(15)
    text = fmt_today_stats(stats, models, yesterday_stats)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户使用统计"""
    from formatter import fmt_user_usage
    users = newapi_db.get_user_usage_stats(10)
    text = fmt_user_usage(users)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Token 使用统计"""
    from formatter import fmt_token_usage
    tokens = newapi_db.get_token_usage_stats(10)
    text = fmt_token_usage(tokens)
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *命令列表*\n\n"
        "*监控查询*\n"
        "  /status — 📊 总览\n"
        "  /model `名称` — 🧩 按模型查\n"
        "  /channel `ID` — 🔌 按渠道查\n"
        "  /slow — 🐢 慢渠道排行\n"
        "  /report — 📋 24h 汇总\n\n"
        "*渠道测试*\n"
        "  /test `ID` — 🧪 测试单渠道\n"
        "  /test\\_model `名称` — 🧪 按模型测试\n"
        "  /test\\_all — 🧪 测试全部渠道\n\n"
        "*渠道操作*\n"
        "  /enable `ID` — 🟢 启用渠道\n"
        "  /disable `ID` — 🔴 禁用渠道\n\n"
        "*数据安全*\n"
        "  /backup — 💾 备份数据库\n"
        "  /backup\\_list — 📂 备份列表\n"
        "  /restore `文件名` — ♻️ 恢复数据库\n\n"
        "*其他*\n"
        "  /menu — 📱 主菜单\n"
        "  /help — 📖 帮助\n"
        "  /ping — 🏓 存活检查"
    )
    await safe_reply(update.message, text, reply_markup=back_btn())


@authorized
async def cmd_diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """只读故障诊断入口。

    用法：
    /diagnose gpt-5.5
    /diagnose claude-opus-4-7
    /diagnose 266
    /diagnose gpt-5.5 90
    """
    if not context.args:
        await safe_reply(
            update.message,
            "用法:\n`/diagnose gpt-5.5`\n`/diagnose claude-opus-4-7`\n`/diagnose 266`\n`/diagnose gpt-5.5 90`",
            reply_markup=back_btn(),
        )
        return

    target = context.args[0].strip()
    minutes = 60
    if len(context.args) >= 2:
        try:
            minutes = int(context.args[1])
        except ValueError:
            await safe_reply(update.message, "❌ 第二个参数必须是分钟数，例如 `/diagnose gpt-5.5 90`。", reply_markup=back_btn())
            return

    kwargs = {"minutes": minutes, "include_recent": True}
    if target.isdigit():
        kwargs["channel_id"] = int(target)
    else:
        kwargs["model"] = target

    msg = await safe_reply(update.message, f"🔎 正在诊断 `{target}`，最近 {minutes} 分钟...", reply_markup=back_btn())
    raw = diagnose_failure_scope(**kwargs)
    text = format_tool_output("diagnose_newapi_failure", raw)
    await safe_edit(msg, text, reply_markup=back_btn())


@authorized
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update.message, "🏓 Pong! Guardian Bot 运行正常。")


@authorized
async def cmd_ai_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        cfg = load_config()
        masked_key = (cfg.get("key", "")[:6] + "***") if cfg.get("key") else "未设置"
        text = (
            "🤖 *AI 配置*\n\n"
            f"启用状态: {'✅ 已启用' if cfg.get('enabled') else '⛔ 未启用'}\n"
            f"API 地址: `{safe_text(cfg.get('url') or '未设置')}`\n"
            f"API Key: `{safe_text(masked_key)}`\n"
            f"模型: `{safe_text(cfg.get('model') or '未设置')}`\n\n"
            "用法:\n"
            "`/ai_config set_url <URL>`\n"
            "`/ai_config set_key <KEY>`\n"
            "`/ai_config set_model <MODEL>`\n"
            "`/ai_config enable`\n"
            "`/ai_config disable`"
        )
        await safe_reply(update.message, text, reply_markup=back_btn())
        return

    action = context.args[0].lower()
    if action == "set_url":
        if len(context.args) < 2:
            await safe_reply(update.message, "❌ 用法: `/ai_config set_url <URL>`")
            return
        url = context.args[1].strip()
        ai_set_url(url)
        await safe_reply(update.message, f"✅ AI API 地址已设置为: `{safe_text(load_config().get('url'))}`", reply_markup=back_btn())
        return
    if action == "set_key":
        if len(context.args) < 2:
            await safe_reply(update.message, "❌ 用法: `/ai_config set_key <KEY>`")
            return
        key = " ".join(context.args[1:]).strip()
        ai_set_key(key)
        await safe_reply(update.message, "✅ AI API Key 已更新。", reply_markup=back_btn())
        return
    if action == "set_model":
        if len(context.args) < 2:
            await safe_reply(update.message, "❌ 用法: `/ai_config set_model <MODEL>`")
            return
        model = " ".join(context.args[1:]).strip()
        ai_set_model(model)
        await safe_reply(update.message, f"✅ AI 模型已设置为: `{safe_text(model)}`", reply_markup=back_btn())
        return
    if action == "enable":
        ai_set_enabled(True)
        await safe_reply(update.message, "✅ AI 功能已启用。", reply_markup=back_btn())
        return
    if action == "disable":
        ai_set_enabled(False)
        await safe_reply(update.message, "⛔ AI 功能已禁用。", reply_markup=back_btn())
        return

    await safe_reply(update.message, "❌ 未知子命令。", reply_markup=back_btn())


@authorized
async def cmd_ai_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换 AI 对话模式。
    on: 所有非命令文本都走 AI
    off: 只有 @ai 前缀才走 AI
    """
    if not context.args:
        current = "开启" if get_mode_enabled() else "关闭"
        await safe_reply(update.message, f"🤖 AI 对话模式当前为: *{current}*\n\n用法:\n`/ai_mode on` — 开启全局 AI 模式\n`/ai_mode off` — 关闭全局 AI 模式（仅 @ai 生效）", reply_markup=back_btn())
        return

    action = context.args[0].lower()
    if action == "on":
        set_mode_enabled(True)
        await safe_reply(update.message, "✅ AI 对话模式已开启：所有非命令文本都会交给 AI 处理。", reply_markup=back_btn())
        return
    if action == "off":
        set_mode_enabled(False)
        await safe_reply(update.message, "⛔ AI 对话模式已关闭：现在只有 `@ai` 前缀消息会交给 AI。", reply_markup=back_btn())
        return

    await safe_reply(update.message, "❌ 用法: `/ai_mode on` 或 `/ai_mode off`", reply_markup=back_btn())


@authorized
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询最近 10 条使用日志。"""
    logs = newapi_db.get_recent_logs(limit=10)
    text = fmt_recent_logs(logs)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 刷新", callback_data="recent_logs")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu")],
    ])
    await safe_reply(update.message, text, reply_markup=markup)


# ── Inline 按钮回调 ──

@authorized
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    text = None
    markup = back_btn()

    if data == "menu":
        await safe_edit(q, "🤖 *NewAPI Guardian*\n━━━━━━━━━━━━━━━━━━\n📊 监控 · 管理 · 备份\n━━━━━━━━━━━━━━━━━━\n💕 Made with love by Rem", reply_markup=main_menu_kb())
        return

    elif data == "ai_mode_toggle":
        enabled = not get_mode_enabled()
        set_mode_enabled(enabled)
        status = "开启" if enabled else "关闭"
        text = f"🤖 AI 对话模式已切换为: *{status}*\n\n{'现在所有非命令文本都会交给 AI 处理。' if enabled else '现在只有 `@ai` 前缀消息会交给 AI 处理。'}"
        markup = ai_menu_kb()

    elif data == "menu_status":
        text = (
            "📊 *状态中心*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "这里放总览、Console、今日统计和 24h 汇总。"
        )
        markup = status_menu_kb()

    elif data == "menu_diagnose":
        text = (
            "🔎 *智能诊断*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "用于定位模型失败、渠道异常、余额/预扣费问题和 fallback 原因。"
        )
        markup = diagnose_menu_kb()

    elif data == "menu_stats":
        text = (
            "📈 *统计报表*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "这里放使用量、排行、慢请求和日志入口。"
        )
        markup = stats_menu_kb()

    elif data == "menu_channels":
        text = (
            "🔧 *渠道管理*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "这里放渠道查询、测试、启用/禁用和异常处理入口。\n\n"
            "💡 添加、编辑、删除渠道仍建议在 NewAPI 网页端操作。"
        )
        markup = channels_menu_kb()

    elif data == "menu_data":
        text = (
            "💾 *数据安全*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "这里放备份、备份列表和恢复说明。\n\n"
            "⚠️ 恢复数据库属于高风险操作，仍需要二次确认。"
        )
        markup = data_menu_kb()

    elif data == "menu_ai":
        cfg = load_config()
        raw_key = cfg.get("key", "") or ""
        if len(raw_key) > 10:
            masked_key = f"{raw_key[:6]}...{raw_key[-4:]}"
        elif raw_key:
            masked_key = raw_key[:3] + "***"
        else:
            masked_key = "未设置"
        text = (
            "🤖 *AI 设置*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"AI 功能: {'已启用 ✅' if cfg.get('enabled') else '未启用 ❌'}\n"
            f"对话模式: {'开启 ✅' if get_mode_enabled() else '关闭 ❌'}\n"
            f"模型: `{safe_text(cfg.get('model') or '未设置')}`\n"
            f"Key: `{safe_text(masked_key)}`"
        )
        markup = ai_menu_kb()

    elif data.startswith("diagnose_model:"):
        model = data.split(":", 1)[1]
        raw = diagnose_failure_scope(model=model, minutes=60, include_recent=True)
        text = format_tool_output("diagnose_newapi_failure", raw)
        markup = back_btn("menu_diagnose")

    elif data == "diagnose_balance":
        raw = diagnose_failure_scope(minutes=120, include_recent=True)
        text = format_tool_output("diagnose_newapi_failure", raw)
        markup = back_btn("menu_diagnose")

    elif data == "diagnose_model_prompt":
        text = "🧩 *按模型诊断*\n\n请发送：\n`/diagnose gpt-5.5`\n`/diagnose claude-opus-4-7`\n\n也可以指定时间：\n`/diagnose gpt-5.5 90`"
        markup = diagnose_menu_kb()

    elif data == "diagnose_channel_prompt":
        text = "🔌 *按渠道诊断*\n\n请发送：\n`/diagnose 266`\n\n也可以指定时间：\n`/diagnose 266 90`"
        markup = diagnose_menu_kb()

    elif data == "newapi_docs_menu":
        text = "📚 *NewAPI 文档参考*\n\n选择一个主题查看。真实状态仍以当前实例数据库 / API 为准。"
        markup = newapi_docs_menu_kb()

    elif data.startswith("newapi_docs:"):
        from skills.newapi import get_newapi_docs
        topic = data.split(":", 1)[1]
        text = format_tool_output("get_newapi_docs", get_newapi_docs(topic))
        markup = back_btn("newapi_docs_menu")

    elif data == "ai_config_menu":
        cfg = load_config()
        raw_key = cfg.get("key", "") or ""
        if len(raw_key) > 10:
            masked_key = f"{raw_key[:6]}...{raw_key[-4:]}"
        elif raw_key:
            masked_key = raw_key[:3] + "***"
        else:
            masked_key = "未设置"

        text = (
            "🤖 *AI 配置*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"状态: {'已启用 ✅' if cfg.get('enabled') else '未启用 ❌'}\n"
            f"API: `{safe_text(cfg.get('url') or '未设置')}`\n"
            f"模型: `{safe_text(cfg.get('model') or '未设置')}`\n"
            f"Key: `{safe_text(masked_key)}`"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 修改 URL", callback_data="ai_set_url"),
                InlineKeyboardButton("🔑 修改 Key", callback_data="ai_set_key"),
            ],
            [
                InlineKeyboardButton("🤖 修改模型", callback_data="ai_set_model"),
                InlineKeyboardButton("✅ 启用", callback_data="ai_enable"),
                InlineKeyboardButton("❌ 禁用", callback_data="ai_disable"),
            ],
            [InlineKeyboardButton("🔙 返回 AI 设置", callback_data="menu_ai")],
        ])

    elif data == "ai_set_url":
        text = "📝 请使用命令设置 AI URL：\n`/ai_config set_url <URL>`"

    elif data == "ai_set_key":
        text = "🔑 请使用命令设置 AI Key：\n`/ai_config set_key <KEY>`"

    elif data == "ai_set_model":
        text = "🤖 请使用命令设置 AI 模型：\n`/ai_config set_model <MODEL>`"

    elif data == "ai_enable":
        ai_set_enabled(True)
        text = "✅ AI 功能已启用。"
        markup = back_btn()

    elif data == "ai_disable":
        ai_set_enabled(False)
        text = "❌ AI 功能已禁用。"
        markup = back_btn()

    elif data == "overview":
        text = build_overview_text(minutes=60)

    elif data == "slow":
        slow = newapi_db.get_slow_channels(minutes=60)
        text = fmt_slow_channels(slow)

    elif data == "report":
        stats = newapi_db.get_overview_stats(minutes=1440)
        fail_ch = newapi_db.get_channel_failure_stats(minutes=1440)
        fail_m = newapi_db.get_model_failure_stats(minutes=1440)
        today = newapi_db.get_today_stats()
        slow = newapi_db.get_slow_channels(minutes=1440)
        balance = newapi_db.get_balance_suspect_channels(minutes=1440)
        text = fmt_overview(stats, fail_ch, fail_m, today, slow, balance).replace("最近 1h", "最近 24h")

    elif data == "recent_logs":
        logs = newapi_db.get_recent_logs(limit=10)
        text = fmt_recent_logs(logs)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 刷新", callback_data="recent_logs")],
            [InlineKeyboardButton("🔙 返回统计报表", callback_data="menu_stats")],
        ])

    elif data == "model_prompt":
        text = "🧩 *按模型查询*\n\n请发送模型名称：\n`/model gpt-5.4`"
        markup = channels_menu_kb()

    elif data == "channel_prompt":
        text = "🔌 *按渠道查询*\n\n请发送渠道 ID：\n`/channel 105`"
        markup = channels_menu_kb()

    elif data == "enable_prompt":
        text = "🟢 *启用渠道*\n\n请发送：\n`/enable 渠道ID`\n\n多个渠道可以空格分隔：\n`/enable 101 102 103`"
        markup = channels_menu_kb()

    elif data == "disable_prompt":
        text = "🔴 *禁用渠道*\n\n请发送：\n`/disable 渠道ID`\n\n多个渠道可以空格分隔：\n`/disable 101 102 103`"
        markup = channels_menu_kb()

    elif data == "disable_failed_prompt":
        text = "⚠️ *一键禁用失败渠道*\n\n请发送：\n`/disable_failed`\n\n也可以指定失败阈值：\n`/disable_failed 5`"
        markup = channels_menu_kb()

    elif data == "restore_prompt":
        text = "♻️ *恢复数据库*\n\n先查看备份：\n`/backup_list`\n\n再发送：\n`/restore 文件名`\n\n⚠️ 恢复会覆盖当前数据库，执行前会再次确认。"
        markup = data_menu_kb()

    elif data == "backup":
        await safe_edit(q, "💾 正在备份数据库...")
        ok, info, filepath = create_backup(tag="manual")
        if ok:
            text = f"✅ {info}"
            if filepath and filepath.stat().st_size < 50 * 1024 * 1024:
                try:
                    await q.message.reply_document(
                        document=open(filepath, "rb"),
                        filename=filepath.name,
                        caption="💾 NewAPI 数据库备份",
                    )
                except Exception as e:
                    text += f"\n⚠️ 文件发送失败: {e}"
        else:
            text = f"❌ {info}"

    elif data == "backup_list":
        backups = list_backups()
        if not backups:
            text = "📂 没有找到备份文件。"
        else:
            lines = ["📂 *备份列表*\n"]
            for i, b in enumerate(backups[:15], 1):
                lines.append(f"  {i}. `{b['filename']}`\n     {b['created']} | {b['size_mb']}MB")
            lines.append(f"\n共 {len(backups)} 份备份")
            lines.append("\n恢复: `/restore 文件名`")
            text = "\n".join(lines)

    elif data == "console":
        from formatter import fmt_console
        stats = newapi_db.get_today_stats()
        today_models = newapi_db.get_today_model_usage(15)
        all_models = newapi_db.get_model_usage_stats(0, 10)
        users = newapi_db.get_user_usage_stats(5)
        tokens = newapi_db.get_token_usage_stats(5)
        text = fmt_console(stats, today_models, all_models, users, tokens)

    elif data == "today":
        from formatter import fmt_today_stats
        stats = newapi_db.get_today_stats()
        yesterday_stats = newapi_db.get_yesterday_stats()
        models = newapi_db.get_today_model_usage(15)
        text = fmt_today_stats(stats, models, yesterday_stats)

    elif data == "models":
        from formatter import fmt_model_usage
        all_models = newapi_db.get_model_usage_stats(0, 20)
        text = fmt_model_usage(all_models, "模型使用排行（全部时间）")

    elif data == "users":
        from formatter import fmt_user_usage
        users_data = newapi_db.get_user_usage_stats(10)
        text = fmt_user_usage(users_data)

    elif data == "tokens":
        from formatter import fmt_token_usage
        tokens_data = newapi_db.get_token_usage_stats(10)
        text = fmt_token_usage(tokens_data)

    elif data == "help_prompt":
        text = (
            "📖 *命令帮助*\n\n"
            "*📊 监控查询*\n"
            "  `/status` — 总览 + 快捷入口\n"
            "  `/console` — Console 综合面板\n"
            "  `/today` — 今日统计\n"
            "  `/models` — 模型排行\n"
            "  `/users` — 用户排行\n"
            "  `/tokens` — Token 排行\n"
            "  `/model 名称` — 按模型查\n"
            "  `/channel ID` — 按渠道查\n"
            "  `/slow` — 慢渠道\n"
            "  `/logs` — 最近 10 条使用日志\n\n"
            "*🧪 渠道测试*\n"
            "  `/test ID` — 测试单渠道\n"
            "  `/test\\_model 名称` — 按模型测试\n"
            "  `/test\\_all` — 测试全部\n\n"
            "*🔧 渠道操作*\n"
            "  `/enable ID [ID...]` — 启用渠道\n"
            "  `/disable ID [ID...]` — 禁用渠道\n"
            "  `/disable\\_failed [阈值]` — 一键禁用失败渠道\n\n"
            "*💾 数据安全*\n"
            "  `/backup` — 备份数据库\n"
            "  `/backup\\_list` — 备份列表\n"
            "  `/restore 文件名` — 恢复数据库\n\n"
            "*🤖 AI 功能*\n"
            "  `/ai_mode on|off` — AI 对话模式开关\n"
            "  `/ai_config` — AI 配置管理\n"
            "  `@ai 消息` — 直接对话（AI 模式关闭时）\n\n"
            "*🛠️ 其他*\n"
            "  `/menu` — 主菜单\n"
            "  `/report` — 24h 汇总\n"
            "  `/ping` — 存活检查\n"
            "  `/help` — 本帮助"
        )

    elif data == "channel_manage":
        text = (
            "🔧 *渠道管理*\n\n"
            "当前支持的操作：\n\n"
            "🧪 `/test ID` — 测试单个渠道\n"
            "🧪 `/test_all` — 并发测试全部渠道\n"
            "🔌 `/channel ID` — 查看渠道详情（带快捷按钮）\n"
            "🟢 `/enable ID [ID...]` — 启用渠道\n"
            "🔴 `/disable ID [ID...]` — 禁用渠道\n"
            "⚠️ `/disable_failed [阈值]` — 一键禁用失败渠道\n\n"
            "💡 *快捷操作*\n"
            "在渠道详情页面可以直接点击按钮进行测试和启用/禁用操作。\n\n"
            "⚠️ *安全提示*\n"
            "为了数据安全，添加/编辑/删除渠道请在 NewAPI 网页端操作。"
        )
        markup = channels_menu_kb()

    elif data == "system_info":
        import time
        import os
        from datetime import datetime, timedelta
        
        # Bot 版本
        bot_version = BOT_VERSION
        
        # 运行时长（从进程启动时间计算）
        try:
            with open(f"/proc/{os.getpid()}/stat") as f:
                stat = f.read().split()
                start_time = int(stat[21]) / os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                uptime_seconds = time.time() - (time.time() - time.clock_gettime(time.CLOCK_BOOTTIME) + start_time)
                uptime = str(timedelta(seconds=int(uptime_seconds)))
        except:
            uptime = "未知"
        
        # 数据库大小
        try:
            import pymysql
            from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                charset="utf8mb4"
            )
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb "
                    "FROM information_schema.tables WHERE table_schema = %s",
                    (MYSQL_DATABASE,)
                )
                db_size = cur.fetchone()[0] or 0
            conn.close()
            db_size_str = f"{db_size} MB"
        except:
            db_size_str = "未知"
        
        # 渠道统计
        channels = newapi_db.get_all_channels()
        enabled_count = sum(1 for ch in channels if ch.get('status') == 1)
        disabled_count = len(channels) - enabled_count
        
        text = (
            "ℹ️ *系统信息*\n\n"
            f"🤖 Bot 版本: `{bot_version}`\n"
            f"⏱️ 运行时长: `{uptime}`\n"
            f"💾 数据库大小: `{db_size_str}`\n"
            f"🔌 渠道总数: `{len(channels)}`\n"
            f"  ├─ 🟢 启用: `{enabled_count}`\n"
            f"  └─ 🔴 禁用: `{disabled_count}`\n\n"
            "💕 Made with love by Rem"
        )

    elif data == "test_all":
        await safe_edit(q, "🧪 正在并发测试全部启用渠道，请稍候...")
        channels = newapi_db.get_enabled_channels()
        
        # 并发测试
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def test_one(ch):
            model = ch.get("test_model", "") or ""
            return (ch, api_test_channel(ch["id"], model))
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [loop.run_in_executor(executor, test_one, ch) for ch in channels]
            results = await asyncio.gather(*tasks)
        
        ok_count = sum(1 for _, r in results if r["success"])
        fail_count = len(results) - ok_count
        lines = [f"🧪 *全量渠道测试*\n", f"✅ 成功: {ok_count} | ❌ 失败: {fail_count}\n"]
        failed = [(ch, r) for ch, r in results if not r["success"]]
        if failed:
            lines.append("*失败渠道:*")
            for ch, r in failed:
                name = truncate(ch.get("name", ""), 25)
                lines.append(f"  ❌ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
        passed = [(ch, r) for ch, r in results if r["success"]]
        if passed:
            lines.append(f"\n*成功渠道 ({len(passed)}个):*")
            for ch, r in passed[:15]:
                name = truncate(ch.get("name", ""), 25)
                lines.append(f"  ✅ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
            if len(passed) > 15:
                lines.append(f"  ... 还有 {len(passed)-15} 个")
        text = "\n".join(lines)

    elif data.startswith("test_") and not data.startswith("test_all"):
        cid_str = data.replace("test_", "")
        try:
            cid = int(cid_str)
        except ValueError:
            text = "❌ 无效渠道 ID"
        else:
            ch = newapi_db.get_channel_by_id(cid)
            if not ch:
                text = f"❌ 渠道 {cid} 不存在。"
            else:
                await safe_edit(q, f"🧪 正在测试渠道 {cid}...")
                r = api_test_channel(cid, ch.get("test_model", ""))
                icon = "✅" if r["success"] else "❌"
                text = (
                    f"{icon} *渠道测试结果*\n\n"
                    f"渠道: `{safe_text(ch.get('name',''))}` (ID:{cid})\n"
                    f"结果: {'成功' if r['success'] else '失败'}\n"
                    f"耗时: {r.get('time', 0):.1f}s"
                )
                if r.get("message"):
                    text += f"\n信息: {safe_text(str(r['message'])[:100])}"

    elif data.startswith("toggle_"):
        cid_str = data.replace("toggle_", "")
        try:
            cid = int(cid_str)
        except ValueError:
            text = "❌ 无效渠道 ID"
        else:
            ch = newapi_db.get_channel_by_id(cid)
            if not ch:
                text = f"❌ 渠道 {cid} 不存在。"
            else:
                new_status = 2 if ch.get("status") == 1 else 1
                result = api_set_channel_status(cid, new_status)
                if result.get("success"):
                    icon = "🟢" if new_status == 1 else "🔴"
                    action = "启用" if new_status == 1 else "禁用"
                    text = f"{icon} 渠道 `{safe_text(ch.get('name',''))}` (ID:{cid}) 已{action}。"
                else:
                    text = f"❌ 操作失败: {result.get('message', '')}"

    elif data.startswith("confirm_enable_"):
        ids = [int(x) for x in data.replace("confirm_enable_", "").split(",") if x]
        await _execute_batch_status(q, ids, 1, edit=True)
        return

    elif data.startswith("confirm_disable_failed_"):
        rest = data.removeprefix("confirm_disable_failed_")
        threshold_str, ids_str = rest.split("_", 1)
        int(threshold_str)  # validate callback shape; ids carry the actual operation target
        ids = [int(x) for x in ids_str.split(",") if x]
        await _execute_batch_status(q, ids, 2, edit=True)
        return

    elif data.startswith("confirm_disable_"):
        ids = [int(x) for x in data.replace("confirm_disable_", "").split(",") if x]
        await _execute_batch_status(q, ids, 2, edit=True)
        return

    elif data.startswith("confirm_restore:"):
        restore_id = data.removeprefix("confirm_restore:")
        filename = _pop_valid_pending_restore(context, restore_id)
        if not filename:
            text = "❌ 恢复确认已过期或备份文件无效，请重新执行 /restore。"
        else:
            await safe_edit(q, f"♻️ 正在恢复 `{safe_text(filename)}`...\n恢复前会自动备份当前状态。")
            ok, info = restore_backup(filename)
            if ok:
                text = f"✅ {info}"
            else:
                text = f"❌ {info}"

    else:
        text = "未知操作。"

    if text:
        try:
            await safe_edit(q, text, reply_markup=markup)
        except Exception:
            # 如果 edit 失败（消息未变），发新消息
            await safe_reply(q.message, text, reply_markup=markup)


# ── 定时任务 ──


async def daily_report(app: Application):
    stats = newapi_db.get_overview_stats(minutes=1440)
    fail_ch = newapi_db.get_channel_failure_stats(minutes=1440)
    fail_m = newapi_db.get_model_failure_stats(minutes=1440)
    text = "📋 *每日汇总*\n\n" + fmt_overview(
        stats,
        fail_ch,
        fail_m,
        newapi_db.get_today_stats(),
        newapi_db.get_slow_channels(minutes=1440),
        newapi_db.get_balance_suspect_channels(minutes=1440),
    ).replace("最近 1h", "最近 24h")
    for uid in AUTHORIZED_IDS:
        try:
            await safe_send(app.bot, uid, text)
        except Exception as e:
            logger.error(f"send daily report failed: {e}")


# ── 启动 ──

async def post_init(app: Application):
    commands = [
        BotCommand("start", "🤖 主菜单"),
        BotCommand("status", "📊 总览"),
        BotCommand("model", "🧩 按模型查"),
        BotCommand("channel", "🔌 按渠道查"),
        BotCommand("slow", "🐢 慢渠道排行"),
        BotCommand("test", "🧪 测试单渠道"),
        BotCommand("test_model", "🧪 按模型测试"),
        BotCommand("test_all", "🧪 测试全部渠道"),
        BotCommand("backup", "💾 备份数据库"),
        BotCommand("backup_list", "📂 备份列表"),
        BotCommand("restore", "♻️ 恢复数据库"),
        BotCommand("enable", "🟢 启用渠道"),
        BotCommand("disable", "🔴 禁用渠道"),
        BotCommand("disable_failed", "⚠️ 一键禁用失败渠道"),
        BotCommand("console", "🖥️ Console面板"),
        BotCommand("today", "📅 今日统计"),
        BotCommand("models", "📊 模型排行"),
        BotCommand("users", "👤 用户排行"),
        BotCommand("tokens", "🔑 Token排行"),
        BotCommand("report", "📋 24h 汇总"),
        BotCommand("help", "📖 帮助"),
        BotCommand("ping", "🏓 存活检查"),
        BotCommand("menu", "📱 主菜单"),
        BotCommand("ai_config", "🤖 AI配置"),
        BotCommand("ai_mode", "🤖 AI模式开关"),
        BotCommand("logs", "📋 使用日志"),
        BotCommand("diagnose", "🔎 故障诊断"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot commands registered.")

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(daily_report, "cron", hour=DAILY_REPORT_HOUR, minute=0, args=[app], id="daily_report")

    async def monitor_job(app: Application):
        from monitor import check_failures
        alerts, recoveries = check_failures()
        for a in alerts:
            msg = fmt_alert(a["channel_id"], a.get("channel_name", ""), a["fail_count"], a.get("models", ""), a.get("content", ""))
            for uid in AUTHORIZED_IDS:
                try:
                    await safe_send(app.bot, uid, msg)
                except Exception as e:
                    logger.error(f"send alert failed: {e}")
        for r in recoveries:
            msg = fmt_recovery(r["channel_id"], r.get("channel_name", ""))
            for uid in AUTHORIZED_IDS:
                try:
                    await safe_send(app.bot, uid, msg)
                except Exception as e:
                    logger.error(f"send recovery failed: {e}")

    scheduler.add_job(monitor_job, "interval", minutes=CHECK_INTERVAL_MINUTES, args=[app], id="monitor")
    
    # 添加日志清理任务：每天凌晨 3 点清理 3 天前的日志
    async def cleanup_logs(app: Application):
        import subprocess
        try:
            result = subprocess.run(
                ["journalctl", "--vacuum-time=3d"],
                capture_output=True,
                text=True,
                timeout=30
            )
            logger.info(f"Log cleanup completed: {result.stdout.strip()}")
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
    
    scheduler.add_job(cleanup_logs, "cron", hour=3, minute=0, args=[app], id="cleanup_logs")
    
    scheduler.start()
    logger.info(f"Scheduler started: daily report at {DAILY_REPORT_HOUR}:00, monitor every {CHECK_INTERVAL_MINUTES} minutes, log cleanup at 03:00")


def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("channel", cmd_channel))
    app.add_handler(CommandHandler("slow", cmd_slow))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("test_model", cmd_test_model))
    app.add_handler(CommandHandler("test_all", cmd_test_all))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("backup_list", cmd_backup_list))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CommandHandler("enable", cmd_enable))
    app.add_handler(CommandHandler("disable", cmd_disable))
    app.add_handler(CommandHandler("disable_failed", cmd_disable_failed))
    app.add_handler(CommandHandler("console", cmd_console))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("models", cmd_models))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("tokens", cmd_tokens))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("ai_config", cmd_ai_config))
    app.add_handler(CommandHandler("ai_mode", cmd_ai_mode))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("diagnose", cmd_diagnose))
    # Agent 相关处理（必须在通用 callback_handler 之前注册）
    app.add_handler(CallbackQueryHandler(agent_callback_handler, pattern="^agent_confirm|^agent_cancel"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_agent_message))
    # 通用回调处理器（兜底）
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info(f"NewAPI Guardian Bot {BOT_VERSION} starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
