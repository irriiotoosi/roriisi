from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from config import settings


@dataclass
class ContributionEntry:
    guild_id: int
    user_id: int
    issuer_id: int
    amount: int
    reason: str
    timestamp: int  # epoch seconds UTC


class JsonContributionStore:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path: str = file_path or settings.DATA_FILE_PATH
        self._lock: asyncio.Lock = asyncio.Lock()
        self._initialized: bool = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        if not os.path.exists(self.file_path):
            async with aiofiles.open(self.file_path, mode="w", encoding="utf-8") as f:
                await f.write(json.dumps({"guilds": {}}, ensure_ascii=False))
        self._initialized = True

    async def _read(self) -> Dict[str, Any]:
        async with aiofiles.open(self.file_path, mode="r", encoding="utf-8") as f:
            raw = await f.read()
            return json.loads(raw or "{}")

    async def _write(self, data: Dict[str, Any]) -> None:
        async with aiofiles.open(self.file_path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False))

    def _ensure_guild_struct(self, data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
        guilds = data.setdefault("guilds", {})
        guild = guilds.setdefault(str(guild_id), {})
        guild.setdefault("history", [])
        guild.setdefault("titles", {})
        lineage = guild.setdefault("lineage", {})
        lineage.setdefault("protege_to_elder", {})
        lineage.setdefault("elder_to_protege", {})
        return guild

    async def record_contribution(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str,
        issuer_id: int,
        timestamp: Optional[int] = None,
    ) -> None:
        if not self._initialized:
            await self.initialize()
        ts = timestamp or int(datetime.now(timezone.utc).timestamp())
        entry = ContributionEntry(
            guild_id=guild_id,
            user_id=user_id,
            issuer_id=issuer_id,
            amount=amount,
            reason=reason,
            timestamp=ts,
        )
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            history: List[Dict[str, Any]] = guild.setdefault("history", [])
            history.append(entry.__dict__)
            await self._write(data)

    async def get_user_total(self, guild_id: int, user_id: int, since_ts: Optional[int] = None) -> int:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        history: List[Dict[str, Any]] = guild.get("history", [])
        total = 0
        for item in history:
            if item.get("user_id") != user_id:
                continue
            if since_ts is not None and int(item.get("timestamp", 0)) < since_ts:
                continue
            total += int(item.get("amount", 0))
        return total

    async def get_leaderboard(
        self,
        guild_id: int,
        since_ts: Optional[int] = None,
        limit: int = 10,
    ) -> List[Tuple[int, int]]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        history: List[Dict[str, Any]] = guild.get("history", [])
        totals: Dict[int, int] = {}
        for item in history:
            if since_ts is not None and int(item.get("timestamp", 0)) < since_ts:
                continue
            user_id = int(item.get("user_id"))
            totals[user_id] = totals.get(user_id, 0) + int(item.get("amount", 0))
        # Sort by total desc, then user_id asc for stability
        sorted_items = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        return sorted_items[:limit]

    # ---------- Titles ----------
    async def set_title(self, guild_id: int, user_id: int, title: str) -> None:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            titles: Dict[str, str] = guild.setdefault("titles", {})
            titles[str(user_id)] = title
            await self._write(data)

    async def get_title(self, guild_id: int, user_id: int) -> Optional[str]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        titles: Dict[str, str] = guild.get("titles", {})
        return titles.get(str(user_id))

    # ---------- Lineage (Elder-Protegé) ----------
    async def set_lineage(self, guild_id: int, elder_id: int, protege_id: int) -> None:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            lineage = guild.setdefault("lineage", {})
            p2e: Dict[str, str] = lineage.setdefault("protege_to_elder", {})
            e2p: Dict[str, str] = lineage.setdefault("elder_to_protege", {})
            p2e[str(protege_id)] = str(elder_id)
            e2p[str(elder_id)] = str(protege_id)
            await self._write(data)

    async def get_elder_for_protege(self, guild_id: int, protege_id: int) -> Optional[int]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        lineage = guild.get("lineage", {})
        p2e: Dict[str, str] = lineage.get("protege_to_elder", {})
        elder = p2e.get(str(protege_id))
        return int(elder) if elder is not None else None

    async def get_protege_for_elder(self, guild_id: int, elder_id: int) -> Optional[int]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        lineage = guild.get("lineage", {})
        e2p: Dict[str, str] = lineage.get("elder_to_protege", {})
        protege = e2p.get(str(elder_id))
        return int(protege) if protege is not None else None

    # ---------- Shop purchases (single-use) ----------
    async def add_purchase(self, guild_id: int, user_id: int, item_key: str, count: int = 1) -> None:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            shop = guild.setdefault("shop", {})
            inv = shop.setdefault("inventory", {})
            user_inv = inv.setdefault(str(user_id), {})
            user_inv[item_key] = int(user_inv.get(item_key, 0)) + int(count)
            await self._write(data)

    async def get_inventory_count(self, guild_id: int, user_id: int, item_key: str) -> int:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        inv = guild.get("shop", {}).get("inventory", {})
        user_inv = inv.get(str(user_id), {})
        return int(user_inv.get(item_key, 0))

    async def consume_item(self, guild_id: int, user_id: int, item_key: str) -> bool:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            shop = guild.setdefault("shop", {})
            inv = shop.setdefault("inventory", {})
            user_inv = inv.setdefault(str(user_id), {})
            current = int(user_inv.get(item_key, 0))
            if current <= 0:
                return False
            if current == 1:
                user_inv.pop(item_key, None)
            else:
                user_inv[item_key] = current - 1
            await self._write(data)
            return True

    async def get_user_inventory(self, guild_id: int, user_id: int) -> Dict[str, int]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        inv = guild.get("shop", {}).get("inventory", {})
        user_inv = inv.get(str(user_id), {})
        # Normalize counts to ints
        return {k: int(v) for k, v in user_inv.items()}

    # ---------- Timed effects ----------
    async def add_effect(self, guild_id: int, effect: Dict[str, Any]) -> None:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            effects: List[Dict[str, Any]] = guild.setdefault("effects", [])
            effects.append(effect)
            await self._write(data)

    async def list_effects(self, guild_id: int) -> List[Dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        return list(guild.get("effects", []))

    async def save_effects(self, guild_id: int, effects: List[Dict[str, Any]]) -> None:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
            guild = self._ensure_guild_struct(data, guild_id)
            guild["effects"] = effects
            await self._write(data)