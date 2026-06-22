# ── Small Caps Converter ───────────────────────────────────────────────────────
_SC_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)

def sc(text: str) -> str:
    """Convert text to Unicode small-caps style."""
    return text.translate(_SC_MAP)


# ── Command Filter Helper ──────────────────────────────────────────────────────
def cmd(commands: str | list) -> list:
    """Normalize command list."""
    if isinstance(commands, str):
        return [commands]
    return list(commands)
