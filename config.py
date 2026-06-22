import os
from dotenv import load_dotenv

# ── Load .env — absolute path so it works from ANY working directory ──────────
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Simple.env")
load_dotenv(_ENV_PATH)


def _int(key: str, default: int = 0) -> int:
    """Safe int parser — returns default if empty or non-numeric."""
    val = os.getenv(key, "").strip()
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _list(key: str) -> list[int]:
    """Parse space-separated int list — skips non-numeric tokens."""
    val = os.getenv(key, "").strip()
    if not val:
        return []
    result = []
    for token in val.split():
        token = token.strip()
        if token.lstrip("-").isdigit():
            result.append(int(token))
    return result


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Bot ───────────────────────────────────────────────────────────────────────
API_ID          = _int("API_ID")
API_HASH        = _str("API_HASH")
BOT_TOKEN       = _str("BOT_TOKEN")

# ── Owner & Sudo ──────────────────────────────────────────────────────────────
OWNER_ID        = _int("OWNER_ID")
SUDO_USERS      = _list("SUDO_USERS")

# ── Database ──────────────────────────────────────────────────────────────────
MONGO_DB_URI    = _str("MONGO_DB_URI")

# ── Channels & Chats ──────────────────────────────────────────────────────────
LOG_CHANNEL     = _int("LOG_CHANNEL")
SUPPORT_CHAT    = _str("SUPPORT_CHAT")
UPDATE_CHANNEL  = _str("UPDATE_CHANNEL")

# ── Waifu API ─────────────────────────────────────────────────────────────────
WAIFU_API_URL   = _str("WAIFU_API_URL", "https://wafus.vercel.app")
WAIFU_API_KEY   = _str("WAIFU_API_KEY")

# ── Economy ───────────────────────────────────────────────────────────────────
GUESS_COINS     = _int("GUESS_COINS",    40)
BATTLE_REWARD   = _int("BATTLE_REWARD",  100)
CLAIM_COOLDOWN  = _int("CLAIM_COOLDOWN", 86400)

# ── Bot Settings ──────────────────────────────────────────────────────────────
BANNED_USERS    = set()

WAIFU_PICS = [
    url.strip()
    for url in _str("WAIFU_PICS", "https://i.ibb.co/x8tCyc9n/4a3347e4f573589a9bf8b2740f68a70a.jpg").split(",")
    if url.strip()
]

FIRE_EMOJI = "🔥"

# ── URL Validation — fail fast on boot if links are wrong ─────────────────────
import re as _re

def _check_url(value: str, name: str) -> None:
    if value and not _re.match(r"https?://", value):
        raise SystemExit(
            f"\n[ERROR] {name} URL invalid!\n"
            f"  Got    : {value!r}\n"
            f"  Fix    : Must start with https://\n"
            f"  Example: https://t.me/yourchat\n"
        )

_check_url(SUPPORT_CHAT,   "SUPPORT_CHAT")
_check_url(UPDATE_CHANNEL, "UPDATE_CHANNEL")
