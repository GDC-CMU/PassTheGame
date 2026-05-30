from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    name: str
    sell_price: int


ITEMS: dict[str, Item] = {
    "Carrot": Item(name="Carrot", sell_price=7),
    "Lettuce": Item(name="Lettuce", sell_price=10),
    "Tomato": Item(name="Tomato", sell_price=15),
    "Apple": Item(name="Apple", sell_price=3),
    "Storm Seed": Item(name="Storm Seed", sell_price=40),
    "Storm Crystal": Item(name="Storm Crystal", sell_price=120),
    "Compost": Item(name="Compost", sell_price=3),
    "Fur": Item(name="Fur", sell_price=8),
    "Venom": Item(name="Venom", sell_price=16),
    "Cyclone Crystal": Item(name="Cyclone Crystal", sell_price=180),
    "Mushroom": Item(name="Mushroom", sell_price=6),
    "Cactus Fruit": Item(name="Cactus Fruit", sell_price=14),
    "Rice": Item(name="Rice", sell_price=5),
    "Night Bloom": Item(name="Night Bloom", sell_price=40),
    "Pumpkin": Item(name="Pumpkin", sell_price=22),
}
