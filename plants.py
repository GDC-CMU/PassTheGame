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
