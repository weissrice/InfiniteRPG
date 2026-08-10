"""Legacy generation interface — delegates to world_gen for actual generation."""

from __future__ import annotations

from typing import Any

from .ai import AIClient
from .state import GameState, Location
from .world_gen import (
    generate_world_content,
    _make_safe_id,
    _parse_generation_response,
)


def generate_location(
    game: GameState,
    ai: AIClient,
    direction: str,
) -> Location | None:
    """Generate a new location in the requested direction.

    This is the legacy interface used by move_player() and open_interactable().
    It delegates to the full world generation system.
    """
    current = game.current_location()
    if current is None:
        return None

    result = generate_world_content(
        game=game,
        ai=ai,
        reference_location_id=current.id,
        direction=direction,
    )

    if result.success and result.location is not None:
        return result.location

    return None
