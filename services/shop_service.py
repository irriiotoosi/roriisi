from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from domain.shop import ShopItem, get_item_by_key
from services.contributions_service import ContributionService
from storage.json_store import JsonContributionStore


@dataclass
class PurchaseResult:
    item: ShopItem


class ShopService:
    def __init__(self, store: Optional[JsonContributionStore] = None) -> None:
        self.store = store or JsonContributionStore()
        self.contribution_service = ContributionService(self.store)

    async def initialize(self) -> None:
        await self.store.initialize()
        await self.contribution_service.initialize()

    async def buy(self, *, guild_id: int, user_id: int, item_key: str) -> PurchaseResult:
        item = get_item_by_key(item_key)
        if item is None:
            raise ValueError("Unknown item key")
        # Deduct cost
        await self.contribution_service.award_points(
            guild_id=guild_id,
            user_id=user_id,
            amount=-item.cost,
            reason=f"Purchased {item.display_name}",
            issuer_id=user_id,
        )
        # Add inventory token
        await self.store.add_purchase(guild_id, user_id, item.key, 1)
        return PurchaseResult(item=item)

    async def has_item(self, *, guild_id: int, user_id: int, item_key: str) -> bool:
        count = await self.store.get_inventory_count(guild_id, user_id, item_key)
        return count > 0

    async def consume(self, *, guild_id: int, user_id: int, item_key: str) -> bool:
        return await self.store.consume_item(guild_id, user_id, item_key)

    async def get_inventory(self, *, guild_id: int, user_id: int) -> Dict[str, int]:
        return await self.store.get_user_inventory(guild_id, user_id)