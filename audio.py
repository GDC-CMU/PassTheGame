import os
import pygame
from typing import Dict
from settings import (
    SFX_ENABLED,
    SFX_VOLUME,
    SFX_HARVEST_FILENAME,
    SFX_BOSS_WARNING_FILENAME,
    SFX_BOSS_STRIKE_FILENAME,
    SFX_BOSS_BLOCK_FILENAME,
    SFX_BOSS_PERFECT_BLOCK_FILENAME,
    SFX_CRITTER_SPAWN_FILENAME,
    SFX_CRITTER_SCARE_FILENAME,
)

_SFX: Dict[str, pygame.mixer.Sound | None] = {}
_INIT = False


def init(props_dir: str) -> None:
    global _INIT, _SFX
    if _INIT:
        return
    _INIT = True

    try:
        pygame.mixer.init()
    except Exception:
        # Audio unavailable; continue without crashing.
        return

    def _load(name: str, fname: str):
        path = os.path.join(props_dir, fname) if fname else None
        if not path or not os.path.exists(path):
            _SFX[name] = None
            return
        try:
            snd = pygame.mixer.Sound(path)
            try:
                snd.set_volume(float(SFX_VOLUME))
            except Exception:
                pass
            _SFX[name] = snd
        except Exception:
            _SFX[name] = None

    _load("harvest", SFX_HARVEST_FILENAME)
    _load("boss_warning", SFX_BOSS_WARNING_FILENAME)
    _load("boss_strike", SFX_BOSS_STRIKE_FILENAME)
    _load("boss_block", SFX_BOSS_BLOCK_FILENAME)
    _load("boss_perfect", SFX_BOSS_PERFECT_BLOCK_FILENAME)
    _load("critter_spawn", SFX_CRITTER_SPAWN_FILENAME)
    _load("critter_scare", SFX_CRITTER_SCARE_FILENAME)


def play(name: str) -> None:
    if not SFX_ENABLED:
        return
    if not _INIT:
        return
    snd = _SFX.get(name)
    if snd:
        try:
            snd.play()
        except Exception:
            pass
