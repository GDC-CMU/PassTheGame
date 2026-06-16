from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    name: str
    sell_price: int


ITEMS: dict[str, Item] = {
    "Carrot": Item(name="Carrot", sell_price=6),
    "Lettuce": Item(name="Lettuce", sell_price=10),
    "Tomato": Item(name="Tomato", sell_price=22),
    "Apple": Item(name="Apple", sell_price=6),
    "Storm Seed": Item(name="Storm Seed", sell_price=40),
    "Storm Crystal": Item(name="Storm Crystal", sell_price=90),
    "Compost": Item(name="Compost", sell_price=3),
    "Fur": Item(name="Fur", sell_price=8),
    "Venom": Item(name="Venom", sell_price=16),
    "Cyclone Crystal": Item(name="Cyclone Crystal", sell_price=180),
    "Mushroom": Item(name="Mushroom", sell_price=9),
    "Cactus Fruit": Item(name="Cactus Fruit", sell_price=14),
    "Rice": Item(name="Rice", sell_price=6),
    "Night Bloom": Item(name="Night Bloom", sell_price=40),
    "Pumpkin": Item(name="Pumpkin", sell_price=30),
    "Sun Shard": Item(name="Sun Shard", sell_price=150),
    "Sunflower Head": Item(name="Sunflower Head", sell_price=16),
    "Moonpetal": Item(name="Moonpetal", sell_price=38),
    "Charged Crystal": Item(name="Charged Crystal", sell_price=160),
    "Fern Frond": Item(name="Fern Frond", sell_price=8),
    "Reed": Item(name="Reed", sell_price=8),
    "Clover": Item(name="Clover", sell_price=3),
    "Orchid Bloom": Item(name="Orchid Bloom", sell_price=70),
    "Everbloom": Item(name="Everbloom", sell_price=120),
}
