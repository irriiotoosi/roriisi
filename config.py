from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    COMMAND_PREFIX: str = "!"
    DATA_FILE_PATH: str = "data/contributions.json"
    # If set, the bot will do a faster, guild-only app command sync
    DEBUG_GUILD_ID: Optional[int] = (
        int(os.environ["DEBUG_GUILD_ID"]) if os.environ.get("DEBUG_GUILD_ID") else None
    )
    # Optional role name treated as developer for protections
    DEVELOPER_ROLE_NAME: Optional[str] = os.environ.get("DEVELOPER_ROLE_NAME")
    # Category name for Whispering Realm Mirror
    GREMLINS_CATEGORY_NAME: str = os.environ.get("GREMLINS_CATEGORY_NAME", "Gremlins")
    # Announce channel name for Silence Seal
    SEAL_ANNOUNCE_CHANNEL_NAME: str = os.environ.get("SEAL_ANNOUNCE_CHANNEL_NAME", "get-sealed-buddy")


settings = Settings()