"""Keyboard input — maps keys to engine actions."""

from __future__ import annotations

from typing import Optional, Dict, Tuple

import pygame

from engine.game import GameEngine
from engine.state import GameState
from engine.actions import move_player, has_local_movement, move_local

from .constants import INPUT_CURSOR_BLINK_MS


def _build_exit_map(game: GameState) -> Dict[Tuple[int, int], str]:
    """Build a direction-vector → exit-name mapping for the current location.

    For each exit, compute (dx, dy) from the current location to the
    destination using map_x / map_y coordinates.  Returns a dict keyed
    by the dominant direction vector, e.g. ``(1, 0)`` → ``"outside"``.

    Coordinate convention (from engine/world.py):
        map_x increases → East  (D / Right)
        map_y increases → South (S / Down)
    """
    loc = game.current_location()
    if not loc or not loc.exits:
        return {}
    result: Dict[Tuple[int, int], str] = {}
    for exit_name, target_id in loc.exits.items():
        target = game.world.locations.get(target_id)
        if not target:
            continue
        dx = target.map_x - loc.map_x
        dy = target.map_y - loc.map_y
        if dx == 0 and dy == 0:
            continue
        if abs(dx) >= abs(dy):
            key = (1 if dx > 0 else -1, 0)
        else:
            key = (0, 1 if dy > 0 else -1)
        if key not in result:
            result[key] = exit_name
    return result


_DIR_MAP = {
    pygame.K_w:     (0, -1),
    pygame.K_UP:    (0, -1),
    pygame.K_s:     (0, 1),
    pygame.K_DOWN:  (0, 1),
    pygame.K_a:     (-1, 0),
    pygame.K_LEFT:  (-1, 0),
    pygame.K_d:     (1, 0),
    pygame.K_RIGHT: (1, 0),
}


class InputHandler:
    """Processes keyboard events and routes input to the correct handler.

    Input routing:
        WASD / arrow keys → direct spatial movement (no AI)
        /command         → local system command
        everything else  → AI Game Master via GameEngine.process_input()
    """

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.input_buffer: str = ""
        self.text_mode: bool = False
        self._cursor_blink = True
        self._last_blink = 0
        self.last_was_ai: bool = False

    def handle_event(self, event: pygame.event.Event,
                     game: GameState) -> Optional[str]:
        """Process a single pygame event. Returns narration/message or None."""
        if event.type == pygame.QUIT:
            return "__QUIT__"

        if event.type != pygame.KEYDOWN:
            return None

        key = event.key

        if key == pygame.K_TAB:
            self.text_mode = not self.text_mode
            return None

        if key == pygame.K_RETURN:
            text = self.input_buffer.strip()
            self.input_buffer = ""
            if text:
                self.text_mode = False
                return self._dispatch(text, game)
            if not self.text_mode:
                self.text_mode = True
            return None

        if key == pygame.K_BACKSPACE:
            self.input_buffer = self.input_buffer[:-1]
            return None

        if key == pygame.K_ESCAPE:
            if self.input_buffer:
                self.input_buffer = ""
            elif self.text_mode:
                self.text_mode = False
            else:
                return "__QUIT__"
            return None

        in_text_mode = self.text_mode or len(self.input_buffer) > 0

        if in_text_mode and event.unicode and event.unicode.isprintable():
            self.input_buffer += event.unicode
            return None

        if not in_text_mode and key in _DIR_MAP:
            if has_local_movement(game):
                dx, dy = _DIR_MAP[key]
                result = move_local(game, dx, dy)
                if result.success:
                    self.engine.step_turn()
                return result.message if result.success else None
            exit_map = _build_exit_map(game)
            direction = _DIR_MAP[key]
            exit_name = exit_map.get(direction)
            if exit_name:
                result = move_player(game, exit_name)
                return result.message if result.success else None
            return None

        if not in_text_mode and event.unicode and event.unicode.isprintable():
            self.input_buffer += event.unicode
            self.text_mode = True
            return None

        return None

    def _dispatch(self, text: str, game: GameState) -> Optional[str]:
        """Route text to the correct handler.

        /command → local system handler
        everything else → AI Game Master via GameEngine.process_input()
        """
        if text.startswith("/"):
            self.last_was_ai = False
            return self._handle_system_command(text[1:].strip(), game)
        self.last_was_ai = True
        ai_result = self.engine.process_input(text)
        return ai_result.get("narration", "Nothing happens.")

    def _handle_system_command(self, command: str, game: GameState) -> Optional[str]:
        """Handle /slash system commands locally."""
        if not command:
            return "Type a command. Try /help for a list."

        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("inventory", "inv", "i"):
            if game.player.inventory:
                return "Inventory: " + ", ".join(game.player.inventory)
            return "Inventory is empty."

        if cmd in ("help", "h", "?"):
            return "__HELP__"

        if cmd == "save":
            from engine.save import save_game
            save_game(game)
            return "Game saved."

        if cmd == "load":
            from engine.save import load_game
            from engine.local_map import generate_local_map
            loaded = load_game()
            game.player = loaded.player
            game.world = loaded.world
            game.quests = loaded.quests
            game.visited_locations = loaded.visited_locations
            game.events = loaded.events
            game.last_narration = loaded.last_narration
            # Regenerate local maps (deterministic from location data)
            game.local_maps = {}
            for loc in game.world.locations.values():
                game.local_maps[loc.id] = generate_local_map(loc)
            # Place NPCs and interactables onto their local maps
            from engine.local_map import _place_npcs_and_interactables
            for loc in game.world.locations.values():
                lm = game.local_maps.get(loc.id)
                if lm is not None:
                    _place_npcs_and_interactables(
                        lm, loc,
                        game.world.npcs, game.world.interactables,
                    )
            return "Game loaded."

        if cmd in ("quit", "exit", "q"):
            return "__QUIT__"

        if cmd == "status":
            p = game.player
            loc = game.current_location()
            loc_name = loc.name if loc else game.player.location
            lines = [
                f"{p.name} — Level {p.level}",
                f"HP: {p.hp}/{p.max_hp}  XP: {p.xp}/{p.level * 100}",
                f"STR: {p.strength}  VIT: {p.vitality}  AGI: {p.agility}  INT: {p.intelligence}",
                f"Location: {loc_name}",
                f"Money: {p.money}g",
                f"Stat Points: {p.stat_points}",
            ]
            return "\n".join(lines)

        if cmd == "quests":
            active = [q for q in game.quests.values() if q.state == "active"]
            offered = [q for q in game.quests.values() if q.state == "offered"]
            if not active and not offered:
                return "No active or offered quests."
            lines = []
            if active:
                lines.append("ACTIVE QUESTS:")
                for q in active:
                    done = sum(1 for o in q.objectives if o.completed)
                    total = len(q.objectives)
                    lines.append(f"  [{q.id}] {q.title} ({done}/{total})")
                    for o in q.objectives:
                        mark = "x" if o.completed else " "
                        lines.append(f"    [{mark}] {o.description}")
            if offered:
                lines.append("OFFERED QUESTS:")
                for q in offered:
                    lines.append(f"  [{q.id}] {q.title}: {q.description}")
            return "\n".join(lines)

        if cmd == "map":
            from engine.map import render_map
            return render_map(game)

        return f"Unknown command: /{cmd}. Type /help for a list."

    def update_cursor(self, now_ms: int) -> None:
        """Toggle cursor visibility for blink effect."""
        if now_ms - self._last_blink >= INPUT_CURSOR_BLINK_MS:
            self._cursor_blink = not self._cursor_blink
            self._last_blink = now_ms
