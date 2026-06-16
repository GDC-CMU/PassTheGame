"""Reusable cozy-UI drawing kit for the in-game HUD, shop, and overlays.

This mirrors the language the finished main menu established (see main_menu.py):
two-tone rounded panels, layered soft drop shadows, eased hover (brighten + lift
+ a slight scale) and pressed (shrink + darken) button states, drop-shadowed
text, a dominant amber primary action and teal secondaries on a warm palette.

The golden rule from effects.py applies here too: never allocate a Surface in the
per-frame draw path when it can be cached. Shadow and glow sprites are built once
per shape and reused, so draw code may call these helpers freely.
"""

import pygame

from effects import clamp


# ── palette (lifted straight from the finished menu) ────────────────────────
INK = (40, 30, 22)
CREAM = (255, 246, 218)
AMBER = (250, 196, 104)
SHADOW_INK = (30, 22, 16)

# Warm wood inks, used for the carved frame on the Farm Status / Almanac plaques.
WOOD_DARK = (92, 56, 28)
WOOD_LIGHT = (150, 100, 55)

# Named button/surface styles: (top, bottom, border, text).
STYLES = {
    # The dominant call to action. Amber, with a warm halo when asked for.
    "primary":   ((252, 206, 118), (224, 158, 74), (255, 232, 168), INK),
    # Calm utility actions. The menu's teal secondary.
    "secondary": ((110, 162, 184), (74, 122, 150), (200, 226, 236), CREAM),
    # Destructive / dismissive. Muted rose so it never shouts.
    "danger":    ((196, 120, 104), (150, 84, 72), (224, 176, 162), CREAM),
    # A cozy green reserved for "you earned this" moments (sell, onward).
    "success":   ((150, 196, 120), (96, 150, 86), (196, 228, 168), INK),
    # Resting shop tile: a muted teal plate that lets crop art pop on the wood.
    "tile":      ((96, 142, 164), (64, 108, 134), (176, 208, 222), CREAM),
    # A locked / unavailable plate: cool stone.
    "locked":    ((96, 92, 100), (70, 66, 74), (130, 126, 134), CREAM),
    # Dark parchment for tooltips and help boxes.
    "ink":       ((58, 52, 60), (40, 36, 44), (120, 112, 124), CREAM),
}

GLOW_AMBER = (255, 198, 108)

_cache: dict = {}


def _get(key, builder):
    surf = _cache.get(key)
    if surf is None:
        surf = builder()
        _cache[key] = surf
    return surf


def clear_cache() -> None:
    _cache.clear()


# ── small math helpers ──────────────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    t = clamp(t)
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def approach(current: float, target: float, dt: float, speed: float) -> float:
    """Frame-rate aware ease toward a target (the menu's smoothing curve)."""
    return current + (target - current) * min(1.0, max(0.0, dt) * speed)


def scaled_rect(rect: pygame.Rect, scale: float) -> pygame.Rect:
    """A copy of rect scaled about its centre. The source rect is never mutated,
    so a button's logical hit-test stays put while its drawn body breathes."""
    w = max(1, int(round(rect.w * scale)))
    h = max(1, int(round(rect.h * scale)))
    out = pygame.Rect(0, 0, w, h)
    out.center = rect.center
    return out


def style_colors(style: str):
    return STYLES.get(style, STYLES["secondary"])


# ── cached soft shadow / glow sprites ───────────────────────────────────────
def _shadow_sprite(w: int, h: int, radius: int, pad: int, layers: int, alpha: int):
    key = ("shadow", w, h, radius, pad, layers, alpha)

    def build():
        surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        for i in range(layers):
            a = max(0, alpha - i * (alpha // max(1, layers)))
            r = pygame.Rect(pad - i, pad - i, w + i * 2, h + i * 2)
            pygame.draw.rect(surf, (*SHADOW_INK, a), r, border_radius=radius + i)
        return surf

    return _get(key, build)


def soft_shadow(surf, rect, radius=12, lift=4, pad=8, layers=3, alpha=34):
    """Blit a cached layered drop shadow beneath rect, offset down by lift."""
    sprite = _shadow_sprite(rect.w, rect.h, radius, pad, layers, alpha)
    surf.blit(sprite, (rect.x - pad, rect.y - pad + lift))


def _glow_sprite(w, h, radius, color, alpha, spread):
    key = ("glow", w, h, radius, tuple(color), alpha, spread)

    def build():
        s = pygame.Surface((w + spread * 2, h + spread * 2), pygame.SRCALPHA)
        for i in range(spread, 0, -1):
            a = int(alpha * (1.0 - i / spread) ** 2)
            r = pygame.Rect(spread - i, spread - i, w + i * 2, h + i * 2)
            pygame.draw.rect(s, (*color, a), r, border_radius=radius + i)
        return s

    return _get(key, build)


def soft_glow(surf, rect, radius=12, color=GLOW_AMBER, alpha=90, spread=16):
    """A warm halo that hugs rect and fades outward (cached by shape)."""
    sprite = _glow_sprite(rect.w, rect.h, radius, color, alpha, spread)
    surf.blit(sprite, sprite.get_rect(center=rect.center))


# ── the core two-tone rounded button plate ──────────────────────────────────
def button_plate(surf, rect, *, style="secondary", hover=0.0, pressed=False,
                 radius=12, shadow=True, glow=0.0, glow_color=GLOW_AMBER,
                 colors=None):
    """Draw a menu-style two-tone rounded plate inside rect.

    hover   0..1 eased value -> brighten + a taller drop shadow (lift).
    pressed bool             -> darken + the shadow tucks in.
    glow    0..1             -> warm halo strength (used for primary / selected).
    colors  optional (top, bottom, border) override of the style.
    Content (icon, label, cost) is drawn by the caller on top of rect.
    """
    if colors is None:
        top, bot, border, _text = style_colors(style)
    else:
        top, bot, border = colors

    if glow > 0.0:
        soft_glow(surf, rect, radius=radius, color=glow_color,
                  alpha=int(40 + 70 * clamp(glow)))

    if shadow:
        lift = (1 if pressed else 4) + int(3 * clamp(hover))
        soft_shadow(surf, rect, radius=radius, lift=lift,
                    alpha=30 if pressed else 36)

    bf = 0.14 * clamp(hover)
    top = lerp_col(top, (255, 255, 255), bf)
    bot = lerp_col(bot, (255, 255, 255), bf)
    if pressed:
        top = lerp_col(top, (0, 0, 0), 0.12)
        bot = lerp_col(bot, (0, 0, 0), 0.12)

    pygame.draw.rect(surf, bot, rect, border_radius=radius)
    top_rect = pygame.Rect(rect.x, rect.y, rect.w, max(2, int(rect.h * 0.58)))
    pygame.draw.rect(surf, top, top_rect,
                     border_top_left_radius=radius, border_top_right_radius=radius)
    # A thin sheen near the top sells the rounded, lit look.
    hi = pygame.Rect(rect.x + max(4, radius // 2), rect.y + 3,
                     rect.w - 2 * max(4, radius // 2), 2)
    if hi.w > 0:
        pygame.draw.rect(surf, lerp_col(top, (255, 255, 255), 0.4), hi, border_radius=2)
    pygame.draw.rect(surf, lerp_col(border, (255, 255, 255), bf), rect, 2,
                     border_radius=radius)


def button(surf, rect, label, font, *, style="secondary", hover=0.0, pressed=False,
           radius=12, glow=0.0, shadow=True, text_color=None):
    """A full labelled button: plate + centred, drop-shadowed text."""
    top, bot, border, text = style_colors(style)
    button_plate(surf, rect, style=style, hover=hover, pressed=pressed,
                 radius=radius, glow=glow, shadow=shadow)
    col = text_color or text
    draw_text(surf, font, label, col, rect.center, anchor="center",
              shadow=(0, 0, 0) if col != CREAM and col != AMBER else SHADOW_INK,
              dy=2)


# ── text with a drop shadow ─────────────────────────────────────────────────
def draw_text(surf, font, text, color, pos, *, anchor="topleft",
              shadow=(0, 0, 0), dx=1, dy=2, shadow_alpha=170):
    """Render text with a soft drop shadow. Returns the text rect."""
    if shadow is not None:
        sh = font.render(text, True, shadow)
        if shadow_alpha is not None and shadow_alpha < 255:
            sh.set_alpha(shadow_alpha)
        sr = sh.get_rect()
        setattr(sr, anchor, pos)
        surf.blit(sh, (sr.x + dx, sr.y + dy))
    main = font.render(text, True, color)
    mr = main.get_rect()
    setattr(mr, anchor, pos)
    surf.blit(main, mr)
    return mr


# ── cached rounded panels for plaques / overlays ────────────────────────────
def rounded_panel(w, h, *, top=(58, 52, 60), bottom=(40, 36, 44),
                  border=(120, 112, 124), radius=14, border_w=2,
                  sheen=True):
    """A cached two-tone rounded panel surface (background for overlays)."""
    key = ("panel", w, h, tuple(top), tuple(bottom), tuple(border), radius, border_w, sheen)

    def build():
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        full = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(surf, bottom, full, border_radius=radius)
        top_rect = pygame.Rect(0, 0, w, int(h * 0.5))
        pygame.draw.rect(surf, top, top_rect,
                         border_top_left_radius=radius, border_top_right_radius=radius)
        if sheen:
            hi = pygame.Rect(radius, 4, w - 2 * radius, 2)
            pygame.draw.rect(surf, lerp_col(top, (255, 255, 255), 0.35), hi, border_radius=2)
        if border_w > 0:
            pygame.draw.rect(surf, border, full, border_w, border_radius=radius)
        return surf

    return _get(key, build)


def panel_with_shadow(surf, rect, *, top=(58, 52, 60), bottom=(40, 36, 44),
                      border=(120, 112, 124), radius=14, border_w=2,
                      shadow_lift=8, shadow_alpha=70):
    """Blit a soft shadow then a cached rounded panel at rect (overlays/dialogs)."""
    soft_shadow(surf, rect, radius=radius, lift=shadow_lift, pad=12,
                layers=4, alpha=shadow_alpha)
    surf.blit(rounded_panel(rect.w, rect.h, top=top, bottom=bottom, border=border,
                            radius=radius, border_w=border_w), rect.topleft)


def section_header(surf, rect, text, font, *, style="primary", radius=9,
                   text_color=None, shadow=True):
    """A small rounded header chip (Seeds / Tools / Inventory) on the panel."""
    top, bot, border, txt = style_colors(style)
    button_plate(surf, rect, style=style, radius=radius, shadow=shadow)
    draw_text(surf, font, text, text_color or txt,
              (rect.x + 10, rect.centery), anchor="midleft",
              shadow=SHADOW_INK if (text_color or txt) in (INK, AMBER) else (0, 0, 0), dy=1)


def progress_bar(surf, rect, ratio, *, radius=6, track=(26, 20, 16),
                 fill=(120, 180, 90), fill_hi=None, border=None):
    """A rounded progress/health track with a two-tone fill."""
    ratio = clamp(ratio)
    pygame.draw.rect(surf, track, rect, border_radius=radius)
    inner = rect.inflate(-4, -4)
    fw = int(inner.width * ratio)
    if fw > 0:
        fill_rect = pygame.Rect(inner.left, inner.top, fw, inner.height)
        pygame.draw.rect(surf, fill, fill_rect, border_radius=max(2, radius - 1))
        hi = fill_hi or lerp_col(fill, (255, 255, 255), 0.3)
        cap = pygame.Rect(inner.left, inner.top, fw, max(2, inner.height // 3))
        pygame.draw.rect(surf, hi, cap, border_radius=max(2, radius - 1))
    if border:
        pygame.draw.rect(surf, border, rect, 2, border_radius=radius)


class Motion:
    """Per-key eased hover/scale state for buttons rebuilt every frame.

    The shop rebuilds its button rects each frame, so hover/press animation is
    keyed by a stable id (e.g. "seed:Carrot", "tool:compost"). tween() returns
    (hover 0..1, scale) eased toward the input state, exactly like the menu.
    """

    def __init__(self):
        self._hover: dict = {}
        self._scale: dict = {}

    def tween(self, key, hovered, pressed, dt, *, hover_scale=1.04,
              press_scale=0.95, hover_speed=14.0, scale_speed=16.0):
        h = approach(self._hover.get(key, 0.0), 1.0 if hovered else 0.0, dt, hover_speed)
        self._hover[key] = h
        target = press_scale if pressed else (hover_scale if hovered else 1.0)
        s = approach(self._scale.get(key, 1.0), target, dt, scale_speed)
        self._scale[key] = s
        return h, s

    def fade(self, key, shown, dt, *, speed=12.0):
        """A single 0..1 value that eases in while shown and out while hidden."""
        v = approach(self._hover.get(("fade", key), 0.0), 1.0 if shown else 0.0, dt, speed)
        self._hover[("fade", key)] = v
        return v
