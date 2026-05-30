from __future__ import annotations

from dataclasses import dataclass

import pygame

from settings import (
    CYCLONE_TITAN_WIDTH,
    CYCLONE_TITAN_HEIGHT,
    CYCLONE_TITAN_Y,
    CYCLONE_TITAN_MAX_HP,
    CYCLONE_TITAN_SPAWN_EVERY_SECONDS,
    CYCLONE_TITAN_STRIKE_COOLDOWN_SECONDS,
    CYCLONE_TITAN_STRIKE_WARNING_SECONDS,
    CYCLONE_TITAN_RETREAT_SECONDS,
    CYCLONE_TITAN_AOE_RADIUS_SLOTS,
    CYCLONE_TITAN_IMAGE_FILENAME,
)
from storm_titan import StormTitan, StormTitanConfig


@dataclass(frozen=True)
class CycloneTitanConfig(StormTitanConfig):
    """Tuning parameters for the Cyclone Titan boss."""

    spawn_every_seconds: float = CYCLONE_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = CYCLONE_TITAN_MAX_HP

    strike_cooldown_seconds: float = CYCLONE_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = CYCLONE_TITAN_STRIKE_WARNING_SECONDS

    retreat_seconds: float = CYCLONE_TITAN_RETREAT_SECONDS

    # Bigger visuals.
    width: int = CYCLONE_TITAN_WIDTH
    height: int = CYCLONE_TITAN_HEIGHT
    y: int = CYCLONE_TITAN_Y

    # No default inventory reward.
    reward_item_name: str = "Cyclone Crystal"
    reward_item_count: int = 1

    # Stronger attack: one-shot target + nearby slots.
    aoe_radius_slots: int = CYCLONE_TITAN_AOE_RADIUS_SLOTS

    image_filename: str = CYCLONE_TITAN_IMAGE_FILENAME

    # Slightly different look.
    warning_color: tuple[int, int, int] = (170, 70, 230)
    bolt_color: tuple[int, int, int] = (210, 245, 255)
    bolt_shadow_color: tuple[int, int, int] = (255, 255, 255)

    # Bigger top HUD bar.
    health_bar_width: int = 460
    health_bar_height: int = 22

    # Slightly heavier movement.
    move_lerp_rate: float = 4.0


class CycloneTitan(StormTitan):
    """Cyclone Titan boss: bigger, tankier, and does AoE one-shot strikes."""

    def __init__(self, config: CycloneTitanConfig | None = None, *, rng=None):
        super().__init__(config or CycloneTitanConfig(), rng=rng)

    @staticmethod
    def _blocking_cloud_for_x(x: int, clouds: Iterable[object]):
        """Cyclone requires raining clouds to block a strike."""
        blockers: list[object] = []
        for cloud in clouds:
            rect = getattr(cloud, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            if rect.left <= x <= rect.right and getattr(cloud, "raining", False):
                blockers.append(cloud)

        if not blockers:
            return None

        return min(blockers, key=lambda c: c.rect.top)

    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        """Draw a simple cyclone/funnel silhouette when PNG assets are missing."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        base = (130, 135, 150, 235)
        shade = (105, 110, 125, 215)

        # Funnel made of stacked ellipses, narrower toward the bottom.
        top_y = int(h * 0.08)
        bottom_y = int(h * 0.92)
        layers = 11
        for i in range(layers):
            t = i / (layers - 1)
            layer_w = int(w * (0.92 - 0.55 * t))
            layer_h = max(10, int(h * 0.10))
            x = (w - layer_w) // 2
            y = int(top_y + (bottom_y - top_y) * t) - layer_h // 2
            color = base if i % 2 == 0 else shade
            pygame.draw.ellipse(surf, color, pygame.Rect(x, y, layer_w, layer_h))

        # A few swirl arcs to sell the cyclone vibe.
        arc_color = (230, 230, 245, 150)
        for i in range(4):
            pad = 20 + i * 18
            rect = pygame.Rect(pad, pad // 2, w - pad * 2, int(h * 0.55))
            pygame.draw.arc(surf, arc_color, rect, 3.6, 6.0, 4)

        # Angry eyes near the top.
        eye = (30, 30, 35)
        left_eye = pygame.Rect(int(w * 0.38), int(h * 0.28), 18, 10)
        right_eye = pygame.Rect(int(w * 0.56), int(h * 0.28), 18, 10)
        pygame.draw.ellipse(surf, eye, left_eye)
        pygame.draw.ellipse(surf, eye, right_eye)
        pygame.draw.line(
            surf,
            eye,
            (left_eye.left - 2, left_eye.top - 6),
            (left_eye.right + 4, left_eye.top - 2),
            3,
        )
        pygame.draw.line(
            surf,
            eye,
            (right_eye.left - 4, right_eye.top - 2),
            (right_eye.right + 2, right_eye.top - 6),
            3,
        )

        return surf
