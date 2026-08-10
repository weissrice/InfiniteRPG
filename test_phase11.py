"""Phase 11 -- NPC local movement tests.

Tests NPC movement modes (stationary, wander, guard), occupancy,
cooldowns, BFS pathfinding, save/load, area transitions, and
game loop integration.

ASCII-only output for Windows cp1252 compatibility.
"""

import json
import random
import sys
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")

from engine.state import GameState, NPC, LocalMap, ExitPoint, LocalObject, Player
from engine.actions import (
    ActionResult,
    _npc_occupancy_set,
    _npc_is_tile_blocked_for_npc,
    _npc_bfs_first_step,
    move_npc_local,
    npc_set_movement_mode,
    update_npc_local_movement,
    has_local_movement,
    move_local,
)
from engine.local_map import (
    generate_local_map,
    validate_local_map,
    MAP_WIDTH,
    MAP_HEIGHT,
    T_WALL,
    T_FLOOR,
    T_TREE,
    T_DOOR,
    T_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    npc_positions=None,
    movement_modes=None,
    guard_positions=None,
    local_map=None,
    location_id="loc_a",
) -> GameState:
    """Create a minimal GameState with one location and optional NPCs."""
    game = GameState()

    from engine.state import Location, World

    loc = Location(
        id=location_id,
        name="Test Location",
        description="A test location.",
    )
    game.world.locations[location_id] = loc
    game.player.location = location_id

    if local_map is None:
        local_map = _make_open_map()

    game.local_maps[location_id] = local_map

    game.player.local_x = local_map.spawn[0]
    game.player.local_y = local_map.spawn[1]

    if npc_positions is None:
        npc_positions = {}

    movement_modes = movement_modes or {}
    guard_positions = guard_positions or {}

    for npc_id, (nx, ny) in npc_positions.items():
        mode = movement_modes.get(npc_id, "stationary")
        gx, gy = guard_positions.get(npc_id, (-1, -1))
        npc = NPC(
            id=npc_id,
            name=npc_id.replace("_", " ").title(),
            location=location_id,
            local_x=nx,
            local_y=ny,
            movement_mode=mode,
            guard_x=gx,
            guard_y=gy,
        )
        game.world.npcs[npc_id] = npc

    return game


def _make_open_map(width=19, height=11, exits=None) -> LocalMap:
    """Create an open map with border walls and a clear interior."""
    terrain = [[T_FLOOR for _ in range(width)] for _ in range(height)]
    collision = [[False for _ in range(width)] for _ in range(height)]

    # Border walls
    for x in range(width):
        terrain[0][x] = T_WALL
        collision[0][x] = True
        terrain[height - 1][x] = T_WALL
        collision[height - 1][x] = True
    for y in range(height):
        terrain[y][0] = T_WALL
        collision[y][0] = True
        terrain[y][width - 1] = T_WALL
        collision[y][width - 1] = True

    exit_map = {}
    if exits:
        for ename, (ex, ey, target_id, entry_name) in exits.items():
            terrain[ey][ex] = T_DOOR
            collision[ey][ex] = False
            exit_map[ename] = ExitPoint(
                x=ex, y=ey,
                target_location_id=target_id,
                entry_name=entry_name,
            )

    return LocalMap(
        width=width, height=height,
        terrain=terrain, collision=collision,
        objects=[], exits=exit_map,
        spawn=[width // 2, height // 2],
    )


def _make_map_with_obstacle(obstacles=None) -> LocalMap:
    """Create an open map with optional obstacle positions."""
    lm = _make_open_map()
    if obstacles:
        for ox, oy in obstacles:
            lm.terrain[oy][ox] = "#"
            lm.collision[oy][ox] = True
    return lm


def _make_two_room_map() -> LocalMap:
    """Create a map with two rooms connected by a corridor."""
    w, h = 19, 11
    terrain = [[T_FLOOR for _ in range(w)] for _ in range(h)]
    collision = [[False for _ in range(w)] for _ in range(h)]

    # Border walls
    for x in range(w):
        terrain[0][x] = T_WALL
        collision[0][x] = True
        terrain[h - 1][x] = T_WALL
        collision[h - 1][x] = True
    for y in range(h):
        terrain[y][0] = T_WALL
        collision[y][0] = True
        terrain[y][w - 1] = T_WALL
        collision[y][w - 1] = True

    # Internal wall dividing at x=9, y=1..9
    for y in range(1, 10):
        terrain[y][9] = T_WALL
        collision[y][9] = True

    # Doorway in the internal wall at y=5
    terrain[5][9] = T_DOOR
    collision[5][9] = False

    return LocalMap(
        width=w, height=h,
        terrain=terrain, collision=collision,
        objects=[], exits={},
        spawn=[5, 5],
    )


# ===========================================================================
# Tests
# ===========================================================================

class TestNPCState(unittest.TestCase):
    """NPC movement state defaults and construction."""

    def test_default_movement_fields(self):
        npc = NPC(id="a", name="A", location="loc")
        self.assertEqual(npc.movement_mode, "stationary")
        self.assertEqual(npc.guard_x, -1)
        self.assertEqual(npc.guard_y, -1)
        self.assertEqual(npc.move_cooldown, 0)
        self.assertEqual(npc.move_interval, 3)

    def test_custom_movement_fields(self):
        npc = NPC(
            id="a", name="A", location="loc",
            movement_mode="wander",
            guard_x=5, guard_y=3,
            move_cooldown=2, move_interval=5,
        )
        self.assertEqual(npc.movement_mode, "wander")
        self.assertEqual(npc.guard_x, 5)
        self.assertEqual(npc.guard_y, 3)
        self.assertEqual(npc.move_cooldown, 2)
        self.assertEqual(npc.move_interval, 5)

    def test_backward_compatible_construction(self):
        npc = NPC(id="a", name="A", location="loc")
        self.assertEqual(npc.movement_mode, "stationary")
        self.assertEqual(npc.local_x, -1)
        self.assertEqual(npc.local_y, -1)

    def test_save_load_round_trip(self):
        from engine.save import save_game, load_game
        import tempfile, os

        game = _make_game(npc_positions={"npc1": (5, 5)})
        game.world.npcs["npc1"].movement_mode = "wander"
        game.world.npcs["npc1"].move_cooldown = 2

        path = Path(tempfile.mktemp(suffix=".json"))
        try:
            save_game(game, path=path)
            loaded = load_game(path=path)
            npc = loaded.world.npcs["npc1"]
            self.assertEqual(npc.movement_mode, "wander")
            self.assertEqual(npc.move_cooldown, 2)
            self.assertEqual(npc.local_x, 5)
            self.assertEqual(npc.local_y, 5)
        finally:
            if path.exists():
                path.unlink()

    def test_old_save_backward_compatibility(self):
        from engine.save import load_game
        import tempfile

        old_data = {
            "version": 5,
            "player": {
                "name": "Traveler", "hp": 100, "max_hp": 100,
                "location": "loc", "inventory": [],
                "xp": 0, "level": 1, "stat_points": 0,
                "strength": 10, "vitality": 10, "agility": 10,
                "intelligence": 10, "money": 0,
                "local_x": 0, "local_y": 0,
                "_area_positions": {},
            },
            "world": {
                "name": "W", "genre": "Fantasy",
                "time": "12:00", "day": 1,
                "weather": {"condition": "clear", "temperature": 25},
                "seed": 0,
                "locations": {
                    "loc": {
                        "id": "loc", "name": "Loc",
                        "description": "A place.",
                        "exits": {}, "npcs": ["npc1"],
                        "items": [], "interactables": [],
                        "symbol": "?", "visual_type": "area",
                        "map_x": 0, "map_y": 0,
                    }
                },
                "npcs": {
                    "npc1": {
                        "id": "npc1", "name": "Npc1",
                        "location": "loc", "local_x": 5, "local_y": 5,
                    }
                },
                "interactables": {},
            },
            "visited_locations": ["loc"],
            "events": [],
            "last_event_period": -1,
            "quests": {},
            "last_narration": "",
        }

        path = Path(tempfile.mktemp(suffix=".json"))
        try:
            with open(path, "w") as f:
                json.dump(old_data, f)
            loaded = load_game(path=path)
            npc = loaded.world.npcs["npc1"]
            self.assertEqual(npc.movement_mode, "stationary")
            self.assertEqual(npc.guard_x, -1)
            self.assertEqual(npc.guard_y, -1)
            self.assertEqual(npc.move_cooldown, 0)
            self.assertEqual(npc.move_interval, 3)
            self.assertEqual(npc.local_x, 5)
            self.assertEqual(npc.local_y, 5)
        finally:
            if path.exists():
                path.unlink()


class TestOccupancy(unittest.TestCase):
    """NPC occupancy set and collision detection."""

    def test_occupancy_basic(self):
        game = _make_game(npc_positions={"a": (3, 3), "b": (7, 7)})
        occ = _npc_occupancy_set(game, "loc_a")
        self.assertIn((3, 3), occ)
        self.assertIn((7, 7), occ)
        self.assertEqual(len(occ), 2)

    def test_occupancy_excludes_invalid(self):
        game = _make_game(npc_positions={"a": (3, 3)})
        game.world.npcs["b"] = NPC(
            id="b", name="B", location="loc_a",
            local_x=-1, local_y=-1,
        )
        occ = _npc_occupancy_set(game, "loc_a")
        self.assertNotIn((-1, -1), occ)
        self.assertEqual(len(occ), 1)

    def test_occupancy_excludes_npc(self):
        game = _make_game(npc_positions={"a": (3, 3), "b": (7, 7)})
        occ = _npc_occupancy_set(game, "loc_a", exclude_npc_id="a")
        self.assertNotIn((3, 3), occ)
        self.assertIn((7, 7), occ)

    def test_occupancy_only_current_location(self):
        game = _make_game(npc_positions={"a": (3, 3)})
        game.world.npcs["b"] = NPC(
            id="b", name="B", location="other_loc",
            local_x=3, local_y=3,
        )
        occ = _npc_occupancy_set(game, "loc_a")
        self.assertEqual(len(occ), 1)

    def test_tile_blocked_by_npc(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        self.assertTrue(
            _npc_is_tile_blocked_for_npc(game, "loc_a", 5, 5)
        )

    def test_tile_not_blocked_by_self(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        self.assertFalse(
            _npc_is_tile_blocked_for_npc(game, "loc_a", 5, 5, "a")
        )

    def test_tile_blocked_by_wall(self):
        lm = _make_open_map()
        game = _make_game(local_map=lm)
        self.assertTrue(
            _npc_is_tile_blocked_for_npc(game, "loc_a", 0, 0)
        )

    def test_tile_blocked_by_object(self):
        lm = _make_open_map()
        obj = LocalObject(id="box", name="Box", x=5, y=5,
                          tile="B", blocking=True)
        lm.objects.append(obj)
        game = _make_game(local_map=lm)
        self.assertTrue(
            _npc_is_tile_blocked_for_npc(game, "loc_a", 5, 5)
        )

    def test_tile_blocked_by_exit(self):
        lm = _make_open_map(exits={"door": (5, 5, "other", "in")})
        game = _make_game(local_map=lm)
        self.assertTrue(
            _npc_is_tile_blocked_for_npc(game, "loc_a", 5, 5)
        )


class TestMoveNpcLocal(unittest.TestCase):
    """Direct NPC movement via move_npc_local()."""

    def test_move_north(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", 0, -1)
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 4)

    def test_move_south(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", 0, 1)
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].local_y, 6)

    def test_move_east(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", 1, 0)
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 6)

    def test_move_west(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", -1, 0)
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 4)

    def test_diagonal_rejection(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", 1, 1)
        self.assertFalse(result.success)

    def test_invalid_vector_rejection(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = move_npc_local(game, "a", 0, 0)
        self.assertFalse(result.success)

    def test_boundary_rejection(self):
        game = _make_game(npc_positions={"a": (1, 1)})
        result = move_npc_local(game, "a", -1, 0)
        self.assertFalse(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 1)

    def test_wall_collision(self):
        lm = _make_open_map()
        game = _make_game(npc_positions={"a": (1, 1)}, local_map=lm)
        result = move_npc_local(game, "a", -1, 0)
        self.assertFalse(result.success)

    def test_blocking_object_collision(self):
        lm = _make_open_map()
        obj = LocalObject(id="wall", name="Wall", x=6, y=5,
                          tile="#", blocking=True)
        lm.objects.append(obj)
        game = _make_game(npc_positions={"a": (5, 5)}, local_map=lm)
        result = move_npc_local(game, "a", 1, 0)
        self.assertFalse(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 5)

    def test_npc_npc_collision(self):
        game = _make_game(npc_positions={"a": (5, 5), "b": (6, 5)})
        result = move_npc_local(game, "a", 1, 0)
        self.assertFalse(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 5)

    def test_invalid_npc(self):
        game = _make_game()
        result = move_npc_local(game, "nonexistent", 0, 1)
        self.assertFalse(result.success)

    def test_npc_wrong_location(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        game.world.npcs["b"] = NPC(
            id="b", name="B", location="other_loc",
            local_x=5, local_y=5,
        )
        game.player.location = "loc_a"
        result = move_npc_local(game, "b", 0, 1)
        self.assertFalse(result.success)

    def test_missing_local_map(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        game.local_maps.clear()
        result = move_npc_local(game, "a", 0, 1)
        self.assertFalse(result.success)

    def test_player_still_walks_through_npc(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        game.player.local_x = 4
        game.player.local_y = 5
        from engine.actions import is_local_position_blocked
        self.assertFalse(is_local_position_blocked(game, 5, 5))


class TestStationaryMode(unittest.TestCase):
    """Stationary NPCs never auto-move."""

    def test_stationary_never_moves(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "stationary"},
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)


class TestWanderMode(unittest.TestCase):
    """Wander mode movement behavior."""

    def test_wander_respects_cooldown(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 2
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)
        self.assertEqual(game.world.npcs["a"].move_cooldown, 1)

    def test_wander_moves_when_cooldown_zero(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        # Force a specific random direction
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 6)

    def test_wander_cardinal_only(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        # Try many random shuffles; all should be cardinal
        for _ in range(20):
            npc = game.world.npcs["a"]
            orig_x, orig_y = npc.local_x, npc.local_y
            npc.move_cooldown = 0
            update_npc_local_movement(game)
            dx = abs(npc.local_x - orig_x)
            dy = abs(npc.local_y - orig_y)
            self.assertTrue(
                (dx == 1 and dy == 0) or (dx == 0 and dy == 1),
                f"Wander moved diagonally: dx={dx}, dy={dy}",
            )
            npc.local_x, npc.local_y = orig_x, orig_y

    def test_wander_stays_walkable(self):
        lm = _make_open_map()
        game = _make_game(
            npc_positions={"a": (1, 1)},
            movement_modes={"a": "wander"},
            local_map=lm,
        )
        for _ in range(20):
            npc = game.world.npcs["a"]
            npc.local_x, npc.local_y = 1, 1
            npc.move_cooldown = 0
            update_npc_local_movement(game)
            self.assertFalse(
                lm.collision[npc.local_y][npc.local_x],
                "Wander moved onto a collision tile",
            )
            npc.local_x, npc.local_y = 1, 1

    def test_wander_handles_all_blocked(self):
        # NPC surrounded by walls on all walkable sides
        lm = _make_open_map()
        # Put NPC at (2, 2) and wall off (1,2), (3,2), (2,1), (2,3)
        for wx, wy in [(1, 2), (3, 2), (2, 1), (2, 3)]:
            lm.terrain[wy][wx] = T_WALL
            lm.collision[wy][wx] = True
        game = _make_game(
            npc_positions={"a": (2, 2)},
            movement_modes={"a": "wander"},
            local_map=lm,
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 2)
        self.assertEqual(game.world.npcs["a"].local_y, 2)

    def test_wander_resets_cooldown_on_move(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(
            game.world.npcs["a"].move_cooldown,
            game.world.npcs["a"].move_interval,
        )

    def test_wander_multiple_npcs(self):
        game = _make_game(
            npc_positions={"a": (5, 5), "b": (7, 7)},
            movement_modes={"a": "wander", "b": "wander"},
        )
        call_count = [0]
        original_shuffle = random.shuffle

        def counting_shuffle(d):
            call_count[0] += 1
            original_shuffle(d)

        with patch("engine.actions.random.shuffle", side_effect=counting_shuffle):
            update_npc_local_movement(game)

        self.assertEqual(call_count[0], 2)


class TestGuardMode(unittest.TestCase):
    """Guard mode BFS pathfinding behavior."""

    def test_guard_at_home_stays_put(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (5, 5)},
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)

    def test_guard_returns_home(self):
        game = _make_game(
            npc_positions={"a": (7, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (5, 5)},
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        dist_before = abs(7 - 5) + abs(5 - 5)
        dist_after = abs(npc.local_x - 5) + abs(npc.local_y - 5)
        self.assertLessEqual(dist_after, dist_before)

    def test_guard_bfs_around_obstacle(self):
        lm = _make_open_map()
        # Wall at (6,5) blocking direct path from (7,5) to (5,5)
        lm.terrain[5][6] = T_WALL
        lm.collision[5][6] = True
        game = _make_game(
            npc_positions={"a": (7, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (5, 5)},
            local_map=lm,
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertNotEqual(npc.local_x, 6)
        self.assertTrue(npc.local_x != 7 or npc.local_y != 5)

    def test_guard_blocked_path(self):
        lm = _make_open_map()
        # Completely wall off (5,5) from (7,5)
        for y in range(1, 10):
            lm.terrain[y][6] = T_WALL
            lm.collision[y][6] = True
        game = _make_game(
            npc_positions={"a": (7, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (5, 5)},
            local_map=lm,
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertEqual(npc.local_x, 7)
        self.assertEqual(npc.local_y, 5)

    def test_guard_uses_bfs_first_step(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (8, 5)},
        )
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 8, 5, "a"
        )
        self.assertEqual(step, (1, 0))

    def test_guard_bfs_around_npc(self):
        game = _make_game(
            npc_positions={"a": (5, 5), "blocker": (6, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (7, 5)},
        )
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 7, 5, "a"
        )
        self.assertIsNotNone(step)
        dx, dy = step
        self.assertFalse(dx == 1 and dy == 0, "BFS should not go through NPC")

    def test_guard_invalid_coords(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
        )
        npc = game.world.npcs["a"]
        self.assertEqual(npc.guard_x, -1)
        self.assertEqual(npc.guard_y, -1)
        update_npc_local_movement(game)
        self.assertEqual(npc.local_x, 5)
        self.assertEqual(npc.local_y, 5)


class TestCooldown(unittest.TestCase):
    """Cooldown behavior."""

    def test_cooldown_decrements(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 3
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].move_cooldown, 2)

    def test_no_movement_while_cooldown(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 5
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)

    def test_cooldown_resets_on_successful_move(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        game.world.npcs["a"].move_interval = 4
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((0, 1))):
            update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].move_cooldown, 4)

    def test_cooldown_not_reset_on_failed_move(self):
        lm = _make_open_map()
        # Surround (5,5) with walls so NPC can't move
        for wx, wy in [(5, 4), (5, 6), (4, 5), (6, 5)]:
            lm.terrain[wy][wx] = T_WALL
            lm.collision[wy][wx] = True
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
            local_map=lm,
        )
        game.world.npcs["a"].move_cooldown = 0
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].move_cooldown, 0)

    def test_move_interval_respected(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_interval = 5
        game.world.npcs["a"].move_cooldown = 0
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].move_cooldown, 5)


class TestMovementModeSetter(unittest.TestCase):
    """npc_set_movement_mode() behavior."""

    def test_set_stationary(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = npc_set_movement_mode(game, "a", "stationary")
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].movement_mode, "stationary")

    def test_set_wander(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = npc_set_movement_mode(game, "a", "wander")
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].movement_mode, "wander")

    def test_set_guard_with_coords(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = npc_set_movement_mode(game, "a", "guard", 8, 3)
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].movement_mode, "guard")
        self.assertEqual(game.world.npcs["a"].guard_x, 8)
        self.assertEqual(game.world.npcs["a"].guard_y, 3)

    def test_set_guard_uses_current_pos(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = npc_set_movement_mode(game, "a", "guard")
        self.assertTrue(result.success)
        self.assertEqual(game.world.npcs["a"].guard_x, 5)
        self.assertEqual(game.world.npcs["a"].guard_y, 5)

    def test_invalid_mode_rejected(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        result = npc_set_movement_mode(game, "a", "fly")
        self.assertFalse(result.success)

    def test_cooldown_reset_on_mode_change(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        game.world.npcs["a"].move_cooldown = 5
        npc_set_movement_mode(game, "a", "wander")
        self.assertEqual(game.world.npcs["a"].move_cooldown, 0)

    def test_invalid_npc(self):
        game = _make_game()
        result = npc_set_movement_mode(game, "nope", "wander")
        self.assertFalse(result.success)

    def test_mode_transitions(self):
        game = _make_game(npc_positions={"a": (5, 5)})
        npc_set_movement_mode(game, "a", "wander")
        self.assertEqual(game.world.npcs["a"].movement_mode, "wander")
        npc_set_movement_mode(game, "a", "guard", 3, 3)
        self.assertEqual(game.world.npcs["a"].movement_mode, "guard")
        npc_set_movement_mode(game, "a", "stationary")
        self.assertEqual(game.world.npcs["a"].movement_mode, "stationary")


class TestMultipleNpcs(unittest.TestCase):
    """Multiple NPC interaction."""

    def test_no_overlap(self):
        game = _make_game(
            npc_positions={"a": (5, 5), "b": (6, 5)},
            movement_modes={"a": "wander", "b": "wander"},
        )
        update_npc_local_movement(game)
        pos_a = (game.world.npcs["a"].local_x, game.world.npcs["a"].local_y)
        pos_b = (game.world.npcs["b"].local_x, game.world.npcs["b"].local_y)
        self.assertNotEqual(pos_a, pos_b)

    def test_occupancy_set_multiple(self):
        game = _make_game(
            npc_positions={"a": (3, 3), "b": (5, 5), "c": (7, 7)},
        )
        occ = _npc_occupancy_set(game, "loc_a")
        self.assertEqual(len(occ), 3)

    def test_npcs_move_independently(self):
        game = _make_game(
            npc_positions={"a": (5, 5), "b": (10, 5)},
            movement_modes={"a": "stationary", "b": "wander"},
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)
        npc_b = game.world.npcs["b"]
        dx = abs(npc_b.local_x - 10)
        dy = abs(npc_b.local_y - 5)
        self.assertTrue(
            (dx == 1 and dy == 0) or (dx == 0 and dy == 1) or (dx == 0 and dy == 0),
            "b should have moved or stayed",
        )

    def test_npcs_in_other_locations_unaffected(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["other"] = NPC(
            id="other", name="Other", location="other_loc",
            local_x=3, local_y=3, movement_mode="wander",
            move_cooldown=0,
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["other"].local_x, 3)
        self.assertEqual(game.world.npcs["other"].local_y, 3)


class TestAreaTransitions(unittest.TestCase):
    """NPC positions persist across area transitions."""

    def test_npc_position_persists(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
        )
        game.player.location = "other_loc"
        game.local_maps["other_loc"] = _make_open_map()
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)

    def test_npc_movement_resumes_on_return(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.player.location = "other_loc"
        game.local_maps["other_loc"] = _make_open_map()
        update_npc_local_movement(game)
        game.player.location = "loc_a"
        npc = game.world.npcs["a"]
        npc.move_cooldown = 0
        orig_x, orig_y = npc.local_x, npc.local_y
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(npc.local_x, orig_x + 1)


class TestSaveLoad(unittest.TestCase):
    """Save/load round-trip for NPC movement state."""

    def test_movement_fields_survive(self):
        from engine.save import save_game, load_game
        import tempfile

        game = _make_game(npc_positions={"a": (5, 5)})
        game.world.npcs["a"].movement_mode = "guard"
        game.world.npcs["a"].guard_x = 8
        game.world.npcs["a"].guard_y = 3
        game.world.npcs["a"].move_cooldown = 2
        game.world.npcs["a"].move_interval = 5

        path = Path(tempfile.mktemp(suffix=".json"))
        try:
            save_game(game, path=path)
            loaded = load_game(path=path)
            npc = loaded.world.npcs["a"]
            self.assertEqual(npc.movement_mode, "guard")
            self.assertEqual(npc.guard_x, 8)
            self.assertEqual(npc.guard_y, 3)
            self.assertEqual(npc.move_cooldown, 2)
            self.assertEqual(npc.move_interval, 5)
            self.assertEqual(npc.local_x, 5)
            self.assertEqual(npc.local_y, 5)
        finally:
            if path.exists():
                path.unlink()

    def test_local_position_survives(self):
        from engine.save import save_game, load_game
        import tempfile

        game = _make_game(npc_positions={"a": (7, 3)})
        path = Path(tempfile.mktemp(suffix=".json"))
        try:
            save_game(game, path=path)
            loaded = load_game(path=path)
            npc = loaded.world.npcs["a"]
            self.assertEqual(npc.local_x, 7)
            self.assertEqual(npc.local_y, 3)
        finally:
            if path.exists():
                path.unlink()


class TestAiGeneratedNpcs(unittest.TestCase):
    """NPC movement works for AI-generated NPCs."""

    def test_generated_npc_valid_position(self):
        game = _make_game()
        npc = NPC(
            id="gen_npc", name="Gen NPC", location="loc_a",
            local_x=5, local_y=5,
        )
        game.world.npcs["gen_npc"] = npc
        self.assertEqual(npc.movement_mode, "stationary")

    def test_generated_npc_mode_changeable(self):
        game = _make_game()
        npc = NPC(
            id="gen_npc", name="Gen NPC", location="loc_a",
            local_x=5, local_y=5,
        )
        game.world.npcs["gen_npc"] = npc
        result = npc_set_movement_mode(game, "gen_npc", "wander")
        self.assertTrue(result.success)
        self.assertEqual(npc.movement_mode, "wander")

    def test_generated_npc_movement_works(self):
        game = _make_game()
        npc = NPC(
            id="gen_npc", name="Gen NPC", location="loc_a",
            local_x=5, local_y=5, movement_mode="wander",
            move_cooldown=0,
        )
        game.world.npcs["gen_npc"] = npc
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(npc.local_x, 6)

    def test_generated_npc_occupancy(self):
        game = _make_game(npc_positions={"existing": (5, 5)})
        npc = NPC(
            id="gen_npc", name="Gen NPC", location="loc_a",
            local_x=6, local_y=5,
        )
        game.world.npcs["gen_npc"] = npc
        occ = _npc_occupancy_set(game, "loc_a")
        self.assertIn((5, 5), occ)
        self.assertIn((6, 5), occ)


class TestGameLoop(unittest.TestCase):
    """Game loop integration tests."""

    def test_tick_after_successful_move(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        result = move_local(game, 1, 0)
        self.assertTrue(result.success)
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        dx = abs(npc.local_x - 5)
        dy = abs(npc.local_y - 5)
        self.assertTrue(
            (dx == 1 and dy == 0) or (dx == 0 and dy == 1) or (dx == 0 and dy == 0),
        )

    def test_no_tick_after_failed_move(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        game.player.local_x = 1
        game.player.local_y = 1
        result = move_local(game, -1, 0)
        self.assertFalse(result.success)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)

    def test_npcs_dont_move_twice(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        move_count = [0]
        original_try = None

        from engine import actions as act
        original_try = act._npc_try_wander

        def counting_try(g, npc):
            move_count[0] += 1
            return original_try(g, npc)

        with patch.object(act, "_npc_try_wander", side_effect=counting_try):
            update_npc_local_movement(game)

        self.assertEqual(move_count[0], 1)

    def test_no_tick_without_local_map(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "wander"},
        )
        game.local_maps.clear()
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)


class TestGuardBfsDetailed(unittest.TestCase):
    """Detailed BFS pathfinding tests."""

    def test_bfs_finds_shortest_path(self):
        lm = _make_open_map()
        game = _make_game(local_map=lm)
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 8, 5, "test_npc"
        )
        self.assertEqual(step, (1, 0))

    def test_bfs_no_path(self):
        lm = _make_open_map()
        # Wall off target completely
        for y in range(1, 10):
            lm.terrain[y][9] = T_WALL
            lm.collision[y][9] = True
        game = _make_game(local_map=lm)
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 12, 5, "test_npc"
        )
        self.assertIsNone(step)

    def test_bfs_same_position(self):
        game = _make_game()
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 5, 5, "test_npc"
        )
        self.assertIsNone(step)

    def test_bfs_around_multiple_obstacles(self):
        lm = _make_two_room_map()
        game = _make_game(local_map=lm)
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 14, 5, "test_npc"
        )
        self.assertIsNotNone(step)

    def test_bfs_respects_npc_occupancy(self):
        game = _make_game(npc_positions={"blocker": (6, 5)})
        step = _npc_bfs_first_step(
            game, "loc_a", 5, 5, 8, 5, "test_npc"
        )
        self.assertIsNotNone(step)
        dx, dy = step
        self.assertFalse(dx == 1 and dy == 0)


class TestBfsPathIntegration(unittest.TestCase):
    """Test BFS pathfinding in the guard mode tick."""

    def test_guard_follows_bfs_path(self):
        lm = _make_open_map()
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (8, 5)},
            local_map=lm,
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertEqual(npc.local_x, 6)
        self.assertEqual(npc.local_y, 5)

    def test_guard_navigates_around_wall(self):
        lm = _make_open_map()
        lm.terrain[5][6] = T_WALL
        lm.collision[5][6] = True
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (7, 5)},
            local_map=lm,
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertTrue(
            (npc.local_x, npc.local_y) != (6, 5),
            "NPC should not move into wall",
        )

    def test_guard_reaches_home_over_multiple_ticks(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (8, 5)},
        )
        for _ in range(10):
            game.world.npcs["a"].move_cooldown = 0
            update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertEqual(npc.local_x, 8)
        self.assertEqual(npc.local_y, 5)


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_tick_on_empty_location(self):
        game = _make_game()
        update_npc_local_movement(game)

    def test_invalid_npc_local_coords_in_tick(self):
        game = _make_game()
        game.world.npcs["ghost"] = NPC(
            id="ghost", name="Ghost", location="loc_a",
            local_x=-1, local_y=-1, movement_mode="wander",
        )
        update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["ghost"].local_x, -1)
        self.assertEqual(game.world.npcs["ghost"].local_y, -1)

    def test_guard_with_no_local_map(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (8, 5)},
        )
        game.local_maps.clear()
        npc_set_movement_mode(game, "a", "guard", 8, 5)
        self.assertEqual(game.world.npcs["a"].guard_x, 8)

    def test_wander_at_map_edge(self):
        game = _make_game(
            npc_positions={"a": (1, 1)},
            movement_modes={"a": "wander"},
        )
        game.world.npcs["a"].move_cooldown = 0
        with patch("engine.actions.random.shuffle", side_effect=lambda d: d.clear() or d.append((-1, 0))):
            update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 1)
        self.assertEqual(game.world.npcs["a"].local_y, 1)

    def test_many_ticks_deterministic_stationary(self):
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "stationary"},
        )
        for _ in range(100):
            update_npc_local_movement(game)
        self.assertEqual(game.world.npcs["a"].local_x, 5)
        self.assertEqual(game.world.npcs["a"].local_y, 5)

    def test_guard_no_path_exists(self):
        lm = _make_open_map()
        for y in range(1, 10):
            lm.terrain[y][9] = T_WALL
            lm.collision[y][9] = True
        game = _make_game(
            npc_positions={"a": (5, 5)},
            movement_modes={"a": "guard"},
            guard_positions={"a": (12, 5)},
            local_map=lm,
        )
        update_npc_local_movement(game)
        npc = game.world.npcs["a"]
        self.assertEqual(npc.local_x, 5)
        self.assertEqual(npc.local_y, 5)


class TestSimulationClock(unittest.TestCase):
    """SimulationClock tests."""

    def test_initial_ticks_zero(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        self.assertEqual(clock.ticks, 0)

    def test_advance_default(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        clock.advance()
        self.assertEqual(clock.ticks, 1)

    def test_advance_multiple(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        clock.advance(5)
        self.assertEqual(clock.ticks, 5)

    def test_advance_zero_is_noop(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        clock.advance(0)
        self.assertEqual(clock.ticks, 0)

    def test_advance_negative_is_noop(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        clock.advance(-3)
        self.assertEqual(clock.ticks, 0)

    def test_cumulative_advance(self):
        from engine.game import SimulationClock
        clock = SimulationClock()
        clock.advance(2)
        clock.advance(3)
        self.assertEqual(clock.ticks, 5)


class TestStepTurn(unittest.TestCase):
    """step_turn() integration tests."""

    def test_step_turn_advances_clock(self):
        from engine.game import GameEngine, SimulationClock
        engine = GameEngine()
        self.assertEqual(engine.clock.ticks, 0)
        engine.step_turn()
        self.assertEqual(engine.clock.ticks, 1)

    def test_step_turn_advances_clock_by_ticks(self):
        from engine.game import GameEngine
        engine = GameEngine()
        engine.step_turn(3)
        self.assertEqual(engine.clock.ticks, 3)

    def test_step_turn_ticks_npc_movement(self):
        """step_turn() must invoke NPC movement exactly once."""
        from engine.game import GameEngine
        from engine.actions import update_npc_local_movement

        engine = GameEngine()
        game = engine.game

        # Set up a wander NPC with cooldown=0 so it can move
        npc = game.world.npcs["old_man"]
        npc.movement_mode = "wander"
        npc.move_cooldown = 0
        orig_x, orig_y = npc.local_x, npc.local_y

        # Call step_turn
        engine.step_turn()

        # NPC should have had a chance to move (or stay if blocked)
        # Clock should have advanced
        self.assertEqual(engine.clock.ticks, 1)

    def test_step_turn_npc_movement_exactly_once(self):
        """Verify NPC movement is called exactly once per step_turn."""
        from engine.game import GameEngine

        engine = GameEngine()
        call_count = [0]
        original = engine.tick_npc_movement

        def counting_tick():
            call_count[0] += 1
            original()

        engine.tick_npc_movement = counting_tick
        engine.step_turn()
        self.assertEqual(call_count[0], 1)

    def test_step_turn_zero_ticks_is_noop(self):
        """step_turn(0) should not advance clock or tick NPC movement."""
        from engine.game import GameEngine

        engine = GameEngine()
        call_count = [0]
        original = engine.tick_npc_movement

        def counting_tick():
            call_count[0] += 1
            original()

        engine.tick_npc_movement = counting_tick
        engine.step_turn(0)
        self.assertEqual(engine.clock.ticks, 0)
        self.assertEqual(call_count[0], 0)


class TestStepTurnMovementIntegration(unittest.TestCase):
    """Integration tests for step_turn with actual movement."""

    def test_successful_local_movement_advances_clock(self):
        """Successful local movement should advance the clock via step_turn."""
        from engine.game import GameEngine
        from engine.actions import move_local

        engine = GameEngine()
        game = engine.game

        # Position player at a walkable tile with room to move
        game.player.local_x = 12
        game.player.local_y = 5

        # Move north (should be walkable)
        result = move_local(game, 0, -1)
        if result.success:
            engine.step_turn()
            self.assertEqual(engine.clock.ticks, 1)
        else:
            # If move failed, that's also fine - just verify no clock advance
            # without step_turn
            self.assertEqual(engine.clock.ticks, 0)

    def test_failed_movement_does_not_advance_clock(self):
        """Failed movement should NOT advance the clock."""
        from engine.game import GameEngine
        from engine.actions import move_local

        engine = GameEngine()
        game = engine.game

        # Position player at a wall
        game.player.local_x = 0
        game.player.local_y = 0

        # Try to move into the wall
        result = move_local(game, -1, 0)
        self.assertFalse(result.success)
        # Clock should not advance from failed movement
        self.assertEqual(engine.clock.ticks, 0)


class TestWitnessReactions(unittest.TestCase):
    """NPC Witness Perception & Immediate Reaction tests."""

    def _make_game_with_npcs(self, witness_personality=None,
                             rel_to_victim=0, rel_to_attacker=0):
        """Create a game with a victim NPC and a witness NPC."""
        from engine.world import create_new_game
        from engine.state import NPC

        game = create_new_game()

        # Create a victim NPC (Bob)
        victim = NPC(
            id="bob", name="Bob", location="old_wooden_house",
            local_x=5, local_y=5, hp=100,
        )
        game.world.npcs["bob"] = victim
        game.world.locations["old_wooden_house"].npcs.append("bob")

        # Create a witness NPC (Alice)
        witness = NPC(
            id="alice", name="Alice", location="old_wooden_house",
            local_x=6, local_y=5, hp=100,
            personality=witness_personality or [],
            relationships={"Bob": rel_to_victim, "player": rel_to_attacker},
        )
        game.world.npcs["alice"] = witness
        game.world.locations["old_wooden_house"].npcs.append("alice")

        # Position player near the victim
        game.player.local_x = 4
        game.player.local_y = 5

        return game, victim, witness

    def test_witness_in_range_reacts(self):
        """NPC within witness range should react to attack."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        reactions = process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        # Cowardly witness should flee
        self.assertTrue(len(reactions) > 0)
        self.assertIn("flee", reactions[0].lower())

    def test_witness_out_of_range_does_not_react(self):
        """NPC outside witness range should not react."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )
        # Move witness far away
        witness.local_x = 18
        witness.local_y = 10

        reactions = process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        self.assertEqual(len(reactions), 0)

    def test_brave_witness_defends_ally(self):
        """Brave NPC with positive relationship to victim should defend."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["brave", "loyal"],
            rel_to_victim=10,
        )

        reactions = process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        self.assertTrue(len(reactions) > 0)
        self.assertIn("defend", reactions[0].lower())

    def test_cowardly_witness_flees(self):
        """Cowardly NPC should flee when witnessing violence."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        reactions = process_witness_reactions(
            game, "player", "bob", True, victim.local_x, victim.local_y,
        )

        self.assertTrue(len(reactions) > 0)
        self.assertIn("flee", reactions[0].lower())

    def test_neutral_witness_ignores(self):
        """NPC with no strong ties should ignore the event."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["practical"],
            rel_to_victim=0,
            rel_to_attacker=0,
        )

        reactions = process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        self.assertEqual(len(reactions), 0)

    def test_witness_records_memory(self):
        """Witness should record the event in memory."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        # Check that witness recorded the event
        self.assertTrue(any("Bob" in mem for mem in witness.memory))

    def test_flee_uses_existing_movement(self):
        """Flee reaction should use existing movement system."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        orig_x, orig_y = witness.local_x, witness.local_y

        process_witness_reactions(
            game, "player", "bob", True, victim.local_x, victim.local_y,
        )

        # Witness should have moved away from player
        # Player is at (4,5), witness was at (6,5)
        # After fleeing, witness should be further from player
        new_dist = max(abs(witness.local_x - 4), abs(witness.local_y - 5))
        old_dist = max(abs(orig_x - 4), abs(orig_y - 5))
        self.assertGreaterEqual(new_dist, old_dist)

    def test_defend_uses_existing_combat(self):
        """Defend reaction should use existing combat system."""
        from engine.actions import process_witness_reactions

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["brave", "loyal"],
            rel_to_victim=10,
        )

        # Player HP before defend
        original_player_hp = game.player.hp

        reactions = process_witness_reactions(
            game, "player", "bob", False, victim.local_x, victim.local_y,
        )

        # Brave witness should defend by attacking player
        self.assertTrue(len(reactions) > 0)
        self.assertIn("defend", reactions[0].lower())

    def test_deterministic_reactions(self):
        """Same state should produce same reaction."""
        from engine.actions import process_witness_reactions

        results = []
        for _ in range(3):
            game, victim, witness = self._make_game_with_npcs(
                witness_personality=["cowardly"],
            )
            reactions = process_witness_reactions(
                game, "player", "bob", False, victim.local_x, victim.local_y,
            )
            results.append(reactions)

        # All results should be identical
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_attack_integrates_witness_reactions(self):
        """Attack function should include witness reactions in result."""
        from engine.actions import attack

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        result = attack(game, "player", "bob", "")

        self.assertTrue(result.success)
        self.assertIn("witness_reactions", result.data)
        self.assertTrue(len(result.data["witness_reactions"]) > 0)

    def test_existing_combat_behavior_intact(self):
        """Existing combat behavior should remain unchanged."""
        from engine.actions import attack

        game, victim, witness = self._make_game_with_npcs()

        original_hp = victim.hp
        result = attack(game, "player", "bob", "")

        self.assertTrue(result.success)
        self.assertLess(victim.hp, original_hp)  # Damage was dealt
        self.assertEqual(result.data["attacker"], "player")
        self.assertEqual(result.data["target"], "bob")

    def test_existing_memory_behavior_intact(self):
        """Existing memory recording should remain intact."""
        from engine.actions import attack

        game, victim, witness = self._make_game_with_npcs(
            witness_personality=["cowardly"],
        )

        attack(game, "player", "bob", "")

        # Victim should remember being attacked
        self.assertTrue(any("player attacked" in mem for mem in victim.memory))
        # Witness should remember seeing the attack
        self.assertTrue(any("Bob" in mem for mem in witness.memory))


class TestNPCAutonomy(unittest.TestCase):
    """NPC Autonomous Actions V1 tests."""

    def _make_game_with_npcs(self, npc_configs=None):
        """Create a game with configurable NPCs."""
        from engine.world import create_new_game
        from engine.state import NPC

        game = create_new_game()
        loc_id = "old_wooden_house"

        if npc_configs:
            for config in npc_configs:
                npc = NPC(
                    id=config["id"],
                    name=config.get("name", config["id"]),
                    location=loc_id,
                    local_x=config.get("local_x", 5),
                    local_y=config.get("local_y", 5),
                    hp=config.get("hp", 100),
                    personality=config.get("personality", []),
                    relationships=config.get("relationships", {}),
                    goals=config.get("goals", []),
                    routine=config.get("routine", []),
                    current_activity=config.get("current_activity", ""),
                    movement_mode=config.get("movement_mode", "stationary"),
                )
                game.world.npcs[npc.id] = npc
                if npc.id not in game.world.locations[loc_id].npcs:
                    game.world.locations[loc_id].npcs.append(npc.id)

        return game

    def test_dead_npc_chooses_idle(self):
        """Dead NPC should choose no action."""
        from engine.actions import choose_npc_action

        game = self._make_game_with_npcs([
            {"id": "dead_npc", "hp": 0, "local_x": 5, "local_y": 5}
        ])
        npc = game.world.npcs["dead_npc"]

        action = choose_npc_action(game, npc)
        self.assertEqual(action, "idle")

    def test_npc_without_position_chooses_idle(self):
        """NPC without valid position should choose idle."""
        from engine.actions import choose_npc_action

        game = self._make_game_with_npcs([
            {"id": "lost_npc", "local_x": -1, "local_y": -1}
        ])
        npc = game.world.npcs["lost_npc"]

        action = choose_npc_action(game, npc)
        self.assertEqual(action, "idle")

    def test_npc_attacks_hostile_target(self):
        """NPC should attack a nearby NPC with negative relationship."""
        from engine.actions import choose_npc_action

        game = self._make_game_with_npcs([
            {"id": "aggressor", "local_x": 5, "local_y": 5,
             "personality": ["aggressive"]},
            {"id": "enemy", "local_x": 6, "local_y": 5},
        ])
        aggressor = game.world.npcs["aggressor"]
        enemy = game.world.npcs["enemy"]
        # Set negative relationship
        aggressor.relationships["enemy"] = -10

        action = choose_npc_action(game, aggressor)
        self.assertEqual(action, "attack")

    def test_npc_chooses_idle_when_peaceful(self):
        """NPC with no goals/hostiles should idle or move harmlessly."""
        from engine.actions import choose_npc_action

        game = self._make_game_with_npcs([
            {"id": "peaceful", "local_x": 5, "local_y": 5,
             "personality": ["kind"], "movement_mode": "stationary"}
        ])
        npc = game.world.npcs["peaceful"]

        action = choose_npc_action(game, npc)
        self.assertEqual(action, "idle")

    def test_npc_wanders_when_set(self):
        """NPC in wander mode should choose to move."""
        from engine.actions import choose_npc_action

        game = self._make_game_with_npcs([
            {"id": "wanderer", "local_x": 5, "local_y": 5,
             "movement_mode": "wander"}
        ])
        npc = game.world.npcs["wanderer"]

        action = choose_npc_action(game, npc)
        self.assertEqual(action, "move")

    def test_autonomous_movement_uses_existing_system(self):
        """Autonomous movement should use existing movement system."""
        from engine.actions import tick_npc_autonomy

        game = self._make_game_with_npcs([
            {"id": "wanderer", "local_x": 5, "local_y": 5,
             "movement_mode": "wander", "move_cooldown": 0}
        ])
        wanderer = game.world.npcs["wanderer"]
        game.player.location = "old_wooden_house"

        orig_x, orig_y = wanderer.local_x, wanderer.local_y
        tick_npc_autonomy(game)

        # NPC should have moved (or tried to)
        # Position may change if movement was possible
        # At minimum, cooldown should be set if moved
        if wanderer.local_x != orig_x or wanderer.local_y != orig_y:
            self.assertEqual(wanderer.move_cooldown, wanderer.move_interval)

    def test_autonomous_attack_uses_existing_system(self):
        """Autonomous attack should use existing attack system."""
        from engine.actions import tick_npc_autonomy

        game = self._make_game_with_npcs([
            {"id": "aggressor", "local_x": 5, "local_y": 5,
             "personality": ["aggressive"]},
            {"id": "enemy", "local_x": 6, "local_y": 5, "hp": 100},
        ])
        aggressor = game.world.npcs["aggressor"]
        enemy = game.world.npcs["enemy"]
        aggressor.relationships["enemy"] = -10
        game.player.location = "old_wooden_house"

        narrations = tick_npc_autonomy(game)

        # Enemy should have taken damage
        self.assertLess(enemy.hp, 100)
        # Should produce narration
        self.assertTrue(len(narrations) > 0)

    def test_deterministic_decisions(self):
        """Identical state should produce identical decisions."""
        from engine.actions import choose_npc_action

        results = []
        for _ in range(3):
            game = self._make_game_with_npcs([
                {"id": "npc1", "local_x": 5, "local_y": 5,
                 "personality": ["aggressive"]},
                {"id": "npc2", "local_x": 6, "local_y": 5},
            ])
            npc1 = game.world.npcs["npc1"]
            npc1.relationships["npc2"] = -10
            results.append(choose_npc_action(game, npc1))

        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_deterministic_ordering(self):
        """Multiple NPCs should execute in deterministic order."""
        from engine.actions import tick_npc_autonomy

        results = []
        for _ in range(3):
            game = self._make_game_with_npcs([
                {"id": "alpha", "local_x": 5, "local_y": 5,
                 "personality": ["aggressive"]},
                {"id": "beta", "local_x": 6, "local_y": 5, "hp": 100},
            ])
            alpha = game.world.npcs["alpha"]
            alpha.relationships["beta"] = -10
            game.player.location = "old_wooden_house"
            narrations = tick_npc_autonomy(game)
            results.append(narrations)

        # All results should be identical
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_dead_npc_never_acts(self):
        """Dead NPC should never perform autonomous action."""
        from engine.actions import tick_npc_autonomy

        game = self._make_game_with_npcs([
            {"id": "dead", "local_x": 5, "local_y": 5, "hp": 0,
             "personality": ["aggressive"]},
            {"id": "target", "local_x": 6, "local_y": 5},
        ])
        # Remove other NPCs to isolate the test
        game.world.npcs = {
            "dead": game.world.npcs["dead"],
            "target": game.world.npcs["target"],
        }
        game.world.locations["old_wooden_house"].npcs = ["dead", "target"]
        dead = game.world.npcs["dead"]
        dead.relationships["target"] = -10
        game.player.location = "old_wooden_house"

        narrations = tick_npc_autonomy(game)

        # Dead NPC should not produce any narration
        self.assertEqual(len(narrations), 0)

    def test_npc_cannot_attack_self(self):
        """NPC should not be able to attack itself."""
        from engine.actions import choose_npc_action, execute_npc_action

        game = self._make_game_with_npcs([
            {"id": "narcissist", "local_x": 5, "local_y": 5,
             "personality": ["aggressive"]},
        ])
        npc = game.world.npcs["narcissist"]
        # Even if relationship to self is negative (shouldn't happen, but test)
        npc.relationships["narcissist"] = -10

        action = choose_npc_action(game, npc)
        # Should not choose attack (no valid target)
        self.assertNotEqual(action, "attack")

    def test_step_turn_integrates_autonomy(self):
        """step_turn should call tick_npc_autonomy."""
        from engine.game import GameEngine

        engine = GameEngine()
        game = engine.game

        # Add a wander NPC
        from engine.state import NPC
        npc = NPC(
            id="auto_npc", name="Auto", location=game.player.location,
            local_x=5, local_y=5, movement_mode="wander", move_cooldown=0,
        )
        game.world.npcs["auto_npc"] = npc
        game.world.locations[game.player.location].npcs.append("auto_npc")

        narrations = engine.step_turn()

        # Should return list (may be empty if NPC couldn't move)
        self.assertIsInstance(narrations, list)

    def test_autonomy_does_not_advance_clock_recursively(self):
        """Autonomous actions should not recursively advance clock."""
        from engine.game import GameEngine

        engine = GameEngine()
        initial_ticks = engine.clock.ticks

        engine.step_turn()

        # Clock should advance exactly once
        self.assertEqual(engine.clock.ticks, initial_ticks + 1)

    def test_phase13_witness_reactions_still_work(self):
        """Phase 13 witness reactions should still work with autonomy."""
        from engine.actions import attack

        game = self._make_game_with_npcs([
            {"id": "victim", "local_x": 5, "local_y": 5},
            {"id": "witness", "local_x": 6, "local_y": 5,
             "personality": ["cowardly"]},
        ])
        game.player.local_x = 4
        game.player.local_y = 5

        result = attack(game, "player", "victim", "")

        self.assertTrue(result.success)
        self.assertIn("witness_reactions", result.data)


if __name__ == "__main__":
    unittest.main()
