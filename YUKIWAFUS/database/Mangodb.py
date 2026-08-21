from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI

from YUKIWAFUS.Logging import LOGGER

if not MONGO_DB_URI:
    raise RuntimeError(
        "MongoDB URI is missing. Set MONGO_DB_URI (or MONGO_URL) "
        "in the environment before starting the bot."
    )

LOGGER.info("Connecting to MongoDB...")
try:
    _mongo_ = AsyncIOMotorClient(
        MONGO_DB_URI,
        serverSelectionTimeoutMS=10_000,
    )
    mongodb = _mongo_.YUKIWAFUS
    LOGGER.info("MongoDB client initialized ✓")
except Exception as e:
    raise RuntimeError(f"MongoDB connection failed: {e}") from e

# ── Collections ───────────────────────────────────────────────────────────────

# Users & Chats
usersdb       = mongodb.users
chatsdb       = mongodb.chats
blockeddb     = mongodb.blocked_users
gbansdb       = mongodb.gbans
sudoersdb     = mongodb.sudoers

# Waifu Core
waifudb       = mongodb.waifus          # all waifu characters
collectiondb  = mongodb.user_collection # user waifu collections
haremdb       = mongodb.harem
favdb         = mongodb.favourites

# Economy
balancedb     = mongodb.balance         # coins, tokens, sakura
shopdb        = mongodb.shop
tradedb       = mongodb.trades
giftdb        = mongodb.gifts

# Games
gamesdb       = mongodb.games           # game state per chat
chat_guessdb  = mongodb.chat_guess_stats # per-chat guess counts by user
game_statsdb  = mongodb.game_stats      # points, unlocks per user
leaderdb      = mongodb.leaderboard

# Flex
titlesdb      = mongodb.titles          # purchased titles
badgesdb      = mongodb.badges          # purchased badges
auradb        = mongodb.auras           # purchased auras

# Admin / Settings
onoffdb       = mongodb.onoff
backupdb      = mongodb.backup_state  # API card backup progress and deduplication
langdb        = mongodb.language
blacklistdb   = mongodb.blacklist_chats
authdb        = mongodb.auth_users
notesdb       = mongodb.notes
filtersdb     = mongodb.filters
