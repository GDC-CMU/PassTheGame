"""Shared juice helpers: easing curves, tiny tweens, and CACHED overlay surfaces.

The golden rule for this file (pygame is software-rendered): never build a Surface
inside the per-frame draw path. Every gradient / vignette here is built once, keyed
by its arguments, and reused. Call the builders freely from draw code; the work only
happens the first time for each unique size/colour.
"""

import math
import pygame


# ── easing curves ──────────────────────────────────────────────────────────
# Each takes t in 0..1 and returns an eased 0..1 (a couple overshoot past 1).

def linear(t: float) -> float:
    return t


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_quad(t: float) -> float:
    return t * t


def ease_in_out_quad(t: float) -> float:
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def ease_out_back(t: float) -> float:
    # Overshoots past 1 then settles, the classic "pop".
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


def ease_out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c4 = (2.0 * math.pi) / 3.0
    return (2.0 ** (-10.0 * t)) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


class Tween:
    """A scalar that eases from start to end over a duration. Drive with update(dt)."""

    __slots__ = ("start", "end", "duration", "ease", "elapsed")

    def __init__(self, start, end, duration, ease=ease_out_quad):
        self.start = float(start)
        self.end = float(end)
        self.duration = max(1e-6, float(duration))
        self.ease = ease
        self.elapsed = 0.0

    def update(self, dt: float) -> float:
        self.elapsed = min(self.duration, self.elapsed + dt)
        return self.value

    @property
    def t(self) -> float:
        return clamp(self.elapsed / self.duration)

    @property
    def value(self) -> float:
        return self.start + (self.end - self.start) * self.ease(self.t)

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


def pulse(elapsed: float, period: float) -> float:
    """A smooth 0..1..0 ping-pong for idle bobs/glows."""
    if period <= 0.0:
        return 0.0
    return 0.5 - 0.5 * math.cos((elapsed / period) * 2.0 * math.pi)


# ── cached overlay surfaces ─────────────────────────────────────────────────
_cache: dict = {}


def _get(key, builder):
    surf = _cache.get(key)
    if surf is None:
        surf = builder()
        _cache[key] = surf
    return surf


def cached_surface(key, builder):
    """Return a cached custom surface. Builders must not depend on frame state."""
    return _get(key, builder)


def vertical_gradient(w: int, h: int, top, bottom) -> pygame.Surface:
    """A top->bottom colour ramp, built once per (size, colours)."""
    w, h = int(w), int(h)
    key = ("vgrad", w, h, tuple(top), tuple(bottom))

    def build():
        col = pygame.Surface((1, h))
        for y in range(h):
            f = y / max(1, h - 1)
            col.set_at((0, y), (
                int(top[0] + (bottom[0] - top[0]) * f),
                int(top[1] + (bottom[1] - top[1]) * f),
                int(top[2] + (bottom[2] - top[2]) * f),
            ))
        return pygame.transform.scale(col, (w, h))

    return _get(key, build)


def vignette(w: int, h: int, strength: int = 110) -> pygame.Surface:
    """A soft darkening toward the edges/corners, built once per (size, strength).

    Uses concentric translucent ellipses (cheap, one-time) so the result is an
    SRCALPHA surface you can blit straight over the frame.
    """
    w, h = int(w), int(h)
    strength = int(strength)
    key = ("vignette", w, h, strength)

    def build():
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, strength))
        cx, cy = w // 2, h // 2
        steps = 48
        for i in range(steps, 0, -1):
            f = i / steps
            rx = int(cx * (0.30 + 0.85 * f))
            ry = int(cy * (0.30 + 0.85 * f))
            a = int(strength * (1.0 - f))
            pygame.draw.ellipse(surf, (0, 0, 0, a), (cx - rx, cy - ry, rx * 2, ry * 2))
        return surf

    return _get(key, build)


def edge_flash(w: int, h: int, color=(220, 48, 42), thickness: int = 18) -> pygame.Surface:
    w, h = int(w), int(h)
    thickness = max(1, int(thickness))
    key = ("edge_flash", w, h, tuple(color), thickness)

    def build():
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(thickness):
            a = int(255 * (1.0 - i / max(1, thickness)) ** 1.7)
            pygame.draw.rect(surf, (*color, a), (i, i, w - i * 2, h - i * 2), 1)
        return surf

    return _get(key, build)


def radial_glow(radius: int, color, max_alpha: int = 150) -> pygame.Surface:
    """A soft circular glow sprite (centre bright, edges transparent), cached."""
    radius = max(2, int(radius))
    key = ("glow", radius, tuple(color), int(max_alpha))

    def build():
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(max_alpha * (1.0 - r / radius) ** 2)
            pygame.draw.circle(surf, (color[0], color[1], color[2], a), (radius, radius), r)
        return surf

    return _get(key, build)


def radial_alpha_mask(radius: int, max_alpha: int = 220) -> pygame.Surface:
    """White radial alpha sprite for subtractive light holes, cached."""
    radius = max(2, int(radius))
    max_alpha = int(max_alpha)
    key = ("radial_alpha", radius, max_alpha)

    def build():
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(max_alpha * (1.0 - r / radius) ** 2.2)
            pygame.draw.circle(surf, (255, 255, 255, a), (radius, radius), r)
        return surf

    return _get(key, build)


def clear_cache() -> None:
    _cache.clear()


# ── tiny timer + helpers for juice ──────────────────────────────────────────
class Timer:
    """A one-shot countdown for hitstop, flashes, and press feedback. No allocation."""

    __slots__ = ("remaining", "duration")

    def __init__(self, duration: float = 0.0):
        self.duration = max(1e-6, float(duration))
        self.remaining = 0.0

    def start(self, duration=None) -> None:
        if duration is not None:
            self.duration = max(1e-6, float(duration))
        self.remaining = self.duration

    def update(self, dt: float) -> bool:
        if self.remaining > 0.0:
            self.remaining = max(0.0, self.remaining - dt)
        return self.remaining > 0.0

    @property
    def active(self) -> bool:
        return self.remaining > 0.0

    @property
    def t(self) -> float:
        # 1.0 at start, 0.0 when finished.
        return clamp(self.remaining / self.duration)


def emit_burst(pool: list, factory, n: int, cap: int) -> None:
    """Append n freshly built particles to pool, trimming the oldest past cap."""
    for _ in range(int(n)):
        pool.append(factory())
    if len(pool) > cap:
        del pool[: len(pool) - cap]


def squash_rect(rect: pygame.Rect, scale_x: float, scale_y: float, anchor: str = "center") -> pygame.Rect:
    """Scale a blit-destination rect for squash and stretch, keeping an anchor put.

    Scale the DEST rect, never the Surface, so deformation costs nothing.
    """
    w = max(1, int(round(rect.width * scale_x)))
    h = max(1, int(round(rect.height * scale_y)))
    out = pygame.Rect(0, 0, w, h)
    setattr(out, anchor, getattr(rect, anchor))
    return out
