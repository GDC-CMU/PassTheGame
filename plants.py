from __future__ import annotations

from abc import ABC


class PlantType(ABC):
    """Static plant definition used by the farm system.

    Create a new plant by subclassing PlantType and setting class attributes.
    Then add an instance to Game.seeds in game.py.

    Required fields:
    - name: display name used in UI and tooltips
    - cost: seed price shown in the seed panel
    - product_name: inventory item name produced on harvest
    - growth_stages: number of growth stages (matches phase sprites count)
    - seconds_per_stage: seconds needed to advance a stage
    - water_min/max: healthy range for water
    - sun_min/max: healthy range for sun
    - base_color: fallback color if no sprite is provided
    - icon_filename: 64x64 icon used in the seed panel
    - phase_filenames: list of 48x48 sprites for growth stages
    """
    name: str
    cost: int
    product_name: str
    growth_stages: int
    seconds_per_stage: float
    water_min: float
    water_max: float
    sun_min: float
    sun_max: float
    base_color: tuple[int, int, int]
    icon_filename: str
    phase_filenames: list[str]
    harvest_yield: int = 1
    regrow_to_stage: int | None = None
    sprite_w: int | None = None
    sprite_h: int | None = None
    seed_item_name: str | None = None
    # Total money earned (from selling) required before this seed unlocks. 0 =
    # available from the start. Used by the seed panel to gate/dim crops.
    unlock_at: int = 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class Carrot(PlantType):
    name = "Carrot"
    cost = 5
    product_name = "Carrot"
    growth_stages = 3
    seconds_per_stage = 4.0
    water_min = 35.0
    water_max = 75.0
    sun_min = 35.0
    sun_max = 80.0
    base_color = (230, 140, 60)
    icon_filename = "carrot_icon.png"
    phase_filenames = [
        "carrot_phase1.png",
        "carrot_phase2.png",
        "carrot_phase3.png",
    ]


class Lettuce(PlantType):
    name = "Lettuce"
    cost = 4
    product_name = "Lettuce"
    growth_stages = 3
    seconds_per_stage = 4.5
    water_min = 45.0
    water_max = 85.0
    sun_min = 25.0
    sun_max = 70.0
    base_color = (90, 180, 90)
    icon_filename = "lettuce_icon.png"
    phase_filenames = [
        "lettuce_phase1.png",
        "lettuce_phase2.png",
        "lettuce_phase3.png",
    ]


class Tomato(PlantType):
    name = "Tomato"
    cost = 7
    unlock_at = 25
    product_name = "Tomato"
    growth_stages = 4
    seconds_per_stage = 5.0
    water_min = 40.0
    water_max = 80.0
    sun_min = 40.0
    sun_max = 85.0
    base_color = (200, 70, 70)
    icon_filename = "tomato_icon.png"
    phase_filenames = [
        "tomato_phase1.png",
        "tomato_phase2.png",
        "tomato_phase3.png",
        "tomato_phase4.png",
    ]


class Apple(PlantType):
    name = "Apple"
    cost = 20
    unlock_at = 400
    product_name = "Apple"
    growth_stages = 4
    seconds_per_stage = 6.0
    water_min = 35.0
    water_max = 80.0
    sun_min = 40.0
    sun_max = 85.0
    base_color = (200, 60, 60)
    icon_filename = "apple_icon.png"
    phase_filenames = [
        "apple_phase1.png",
        "apple_phase2.png",
        "apple_phase3.png",
        "apple_phase4.png",
    ]
    harvest_yield = 20 #collect 20 apples per harvest
    regrow_to_stage = 3 #tree will go back to stage 3 after harvest
    sprite_w = 170
    sprite_h = 280 # since apple trees are taller than carrots!


class StormSeed(PlantType):
    """Rare seed dropped by the Storm Titan.

    This seed is planted by consuming an inventory item (seed_item_name) rather
    than spending money.
    """

    name = "Storm Seed"
    cost = 0
    seed_item_name = "Storm Seed"
    product_name = "Storm Crystal"
    growth_stages = 4
    seconds_per_stage = 5.5
    water_min = 40.0
    water_max = 85.0
    sun_min = 15.0
    sun_max = 65.0
    base_color = (170, 120, 220)
    icon_filename = "storm_seed_icon.png"
    phase_filenames = [
        "storm_seed_phase1.png",
        "storm_seed_phase2.png",
        "storm_seed_phase3.png",
        "storm_seed_phase4.png",
    ]


class Mushroom(PlantType):
    name = "Mushroom"
    cost = 3
    unlock_at = 170
    product_name = "Mushroom"
    growth_stages = 2
    seconds_per_stage = 6.0
    water_min = 60.0
    water_max = 95.0
    sun_min = 0.0
    sun_max = 40.0
    base_color = (180, 140, 120)
    icon_filename = "mushroom_icon.png"
    phase_filenames = [
        "mushroom_phase1.png",
        "mushroom_phase2.png",
    ]


class Cactus(PlantType):
    name = "Cactus"
    cost = 6
    unlock_at = 60
    product_name = "Cactus Fruit"
    growth_stages = 3
    seconds_per_stage = 5.5
    water_min = 10.0
    water_max = 50.0
    sun_min = 60.0
    sun_max = 100.0
    base_color = (120, 200, 100)
    icon_filename = "cactus_icon.png"
    phase_filenames = [
        "cactus_phase1.png",
        "cactus_phase2.png",
        "cactus_phase3.png",
    ]


class Rice(PlantType):
    name = "Rice"
    cost = 4
    unlock_at = 230
    product_name = "Rice"
    growth_stages = 3
    seconds_per_stage = 4.0
    water_min = 70.0
    water_max = 100.0
    sun_min = 30.0
    sun_max = 80.0
    base_color = (220, 200, 120)
    icon_filename = "rice_icon.png"
    phase_filenames = [
        "rice_phase1.png",
        "rice_phase2.png",
        "rice_phase3.png",
    ]


class NightBloom(PlantType):
    name = "Night Bloom"
    cost = 12
    unlock_at = 300
    product_name = "Night Bloom"
    growth_stages = 4
    seconds_per_stage = 6.0
    water_min = 40.0
    water_max = 80.0
    sun_min = 0.0
    sun_max = 30.0
    base_color = (90, 40, 160)
    icon_filename = "nightbloom_icon.png"
    phase_filenames = [
        "nightbloom_phase1.png",
        "nightbloom_phase2.png",
        "nightbloom_phase3.png",
        "nightbloom_phase4.png",
    ]


class Pumpkin(PlantType):
    name = "Pumpkin"
    cost = 10
    unlock_at = 110
    product_name = "Pumpkin"
    growth_stages = 4
    seconds_per_stage = 6.5
    water_min = 50.0
    water_max = 85.0
    sun_min = 45.0
    sun_max = 90.0
    base_color = (220, 130, 60)
    icon_filename = "pumpkin_icon.png"
    phase_filenames = [
        "pumpkin_phase1.png",
        "pumpkin_phase2.png",
        "pumpkin_phase3.png",
        "pumpkin_phase4.png",
    ]