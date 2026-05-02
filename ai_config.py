# AI 配置管理模块
"""简易的 AI 配置持久化实现。
文件位于 data/ai_config.json，结构示例:
{
  "enabled": false,
  "url": "",
  "key": "",
  "model": ""
}
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "data" / "ai_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "mode_enabled": False,
    "url": "",
    "key": "",
    "model": "",
}

def _ensure_file():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)

def load_config():
    _ensure_file()
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = DEFAULT_CONFIG.copy()
    # 保证键完整
    for k, v in DEFAULT_CONFIG.items():
        data.setdefault(k, v)
    return data

def save_config(cfg: dict):
    _ensure_file()
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_enabled():
    return load_config().get("enabled", False)

def set_enabled(flag: bool):
    cfg = load_config()
    cfg["enabled"] = bool(flag)
    save_config(cfg)

# New AI mode toggle (Phase 4)
def get_mode_enabled() -> bool:
    cfg = load_config()
    return cfg.get("mode_enabled", False)

def set_mode_enabled(enabled: bool):
    cfg = load_config()
    cfg["mode_enabled"] = bool(enabled)
    save_config(cfg)

def get_url():
    return load_config().get("url", "")

def set_url(url: str):
    # 自动补 /v1
    if not url.endswith("/v1"):
        if url.endswith('/'):
            url = url.rstrip('/')
        url = f"{url}/v1"
    cfg = load_config()
    cfg["url"] = url
    save_config(cfg)

def get_key():
    return load_config().get("key", "")

def set_key(key: str):
    cfg = load_config()
    cfg["key"] = key
    save_config(cfg)

def get_model():
    return load_config().get("model", "")

def set_model(model: str):
    cfg = load_config()
    cfg["model"] = model
    save_config(cfg)
