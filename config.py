import os
import re

from dotenv import load_dotenv

# Load the first available local env file. Linux filenames are case-sensitive,
# so support both the historical `Simple.env` name and the committed template.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for _env_name in (".env", "Simple.env", "simple.env"):
    _env_path = os.path.join(_BASE_DIR, _env_name)
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=False)


def _int(key: str, default: int = 0) -> int:
    """Safe int parser — returns default if empty or non-numeric."""
    val = os.getenv(key, "").strip().strip("[](){}")
    # Accept values copied with a trailing comma or semicolon from dashboards.
    val = re.split(r"[;,\s]+", val, maxsplit=1)[0] if val else ""
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _list(key: str) -> list[int]:
    """Parse space-separated int list — skips non-numeric tokens."""
    val = os.getenv(key, "").strip().strip("[](){}")
    if not val:
        return []
    result = []
    for token in re.split(r"[;,\s]+", val):
        token = token.strip()
        if token.lstrip("-").isdigit():
            result.append(int(token))
    return result


def _str(key: str, default: str = "") -> str:
    value = os.getenv(key, default).strip()
    # Ignore inline-comment placeholders from env templates such as
    # `SUPPORT_CHAT= # https://t.me/example`.
    return default if value.startswith("#") else value


# ── Bot ───────────────────────────────────────────────────────────────────────
API_ID          = _int("API_ID")
API_HASH        = _str("API_HASH")
BOT_TOKEN       = _str("BOT_TOKEN")

# ── Owner & Sudo ──────────────────────────────────────────────────────────────
OWNER_ID        = _int("OWNER_ID")
SUDO_USERS      = _list("SUDO_USERS")

# ── Database ──────────────────────────────────────────────────────────────────
# Render/deployment files may provide MONGO_URL; keep MONGO_DB_URI as the
# canonical application name while accepting the deployment alias.
MONGO_DB_URI    = _str("MONGO_DB_URI") or _str("MONGO_URL")

# ── Channels & Chats ──────────────────────────────────────────────────────────
LOG_CHANNEL     = _int("LOG_CHANNEL")
SUPPORT_CHAT    = _str("SUPPORT_CHAT")
UPDATE_CHANNEL  = _str("UPDATE_CHANNEL")
# Optional fallback only; the owner can configure the channel from DM with
# /setbackupchannel, so this does not need to be present in Render env.
BACKUP_CHANNEL  = _int("BACKUP_CHANNEL")

# ── Waifu API ─────────────────────────────────────────────────────────────────
WAIFU_API_URL   = _str("WAIFU_API_URL", "YUKI_027d60ef7a1041771d0791836260daf7")
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
        # Do not terminate the bot before Render can detect /health. The
        # affected feature can report its own configuration error at runtime.
        print(
            f"[WARNING] {name} URL is invalid: {value!r}; "
            "expected a value beginning with https://"
        )

_check_url(SUPPORT_CHAT,   "SUPPORT_CHAT")
_check_url(UPDATE_CHANNEL, "UPDATE_CHANNEL")
