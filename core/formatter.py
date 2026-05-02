"""核心格式化工具层 - 通用格式化函数"""
from typing import Any


def format_table(data: list[dict], columns: list[str] = None, max_width: int = 50) -> str:
    """
    通用表格格式化
    
    Args:
        data: 数据列表
        columns: 要显示的列（None = 全部）
        max_width: 单元格最大宽度
    
    Returns:
        Markdown 表格字符串
    """
    if not data:
        return "（无数据）"
    
    # 确定要显示的列
    if columns is None:
        columns = list(data[0].keys())
    
    # 构建表头
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    # 构建数据行
    rows = []
    for row in data:
        cells = []
        for col in columns:
            value = row.get(col, "")
            # 转换为字符串并截断
            cell_str = str(value)
            if len(cell_str) > max_width:
                cell_str = cell_str[:max_width-3] + "..."
            cells.append(cell_str)
        rows.append("| " + " | ".join(cells) + " |")
    
    return "\n".join([header, separator] + rows)


def format_list(data: list[dict], template: str = None) -> str:
    """
    通用列表格式化
    
    Args:
        data: 数据列表
        template: 格式模板（如 "• {name}: {value}"）
    
    Returns:
        格式化后的列表字符串
    """
    if not data:
        return "（无数据）"
    
    if template is None:
        # 默认模板：显示所有字段
        lines = []
        for i, item in enumerate(data, 1):
            lines.append(f"**{i}.**")
            for key, value in item.items():
                lines.append(f"  • {key}: {value}")
        return "\n".join(lines)
    else:
        # 使用自定义模板
        lines = []
        for item in data:
            try:
                lines.append(template.format(**item))
            except KeyError as e:
                lines.append(f"（格式化错误：缺少字段 {e}）")
        return "\n".join(lines)


def format_kv(data: dict, title: str = None) -> str:
    """
    键值对格式化
    
    Args:
        data: 键值对字典
        title: 标题（可选）
    
    Returns:
        格式化后的键值对字符串
    """
    lines = []
    if title:
        lines.append(f"**{title}**")
    
    for key, value in data.items():
        lines.append(f"• {key}: {value}")
    
    return "\n".join(lines)


def format_number(num: float, precision: int = 2) -> str:
    """格式化数字（添加千分位）"""
    if isinstance(num, (int, float)):
        return f"{num:,.{precision}f}"
    return str(num)


def format_quota(quota: float) -> str:
    """格式化额度（转换为美元）"""
    if quota is None:
        return "N/A"
    dollars = quota / 500000  # NewAPI 的额度单位转美元
    return f"${dollars:.2f}"


def format_time(seconds: float) -> str:
    """格式化时间"""
    if seconds is None:
        return "N/A"
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"


def format_status(status: int) -> str:
    """格式化状态"""
    return "✅ 启用" if status == 1 else "❌ 禁用"


def format_percentage(value: float, total: float) -> str:
    """格式化百分比"""
    if total == 0:
        return "0%"
    percentage = (value / total) * 100
    return f"{percentage:.1f}%"


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
