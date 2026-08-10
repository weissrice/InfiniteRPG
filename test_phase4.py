# -*- coding: utf-8 -*-
"""Tests for Phase 4: Area transitions when stepping on exit tiles."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import GameState, LocalMap, ExitPoint
from engine.actions import (
    move_local, has_local_movement, _resolve_entry_point,
    _perform_area_transition, ActionResult,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


# --- Setup ---
print("=== Setup ===")
game = create_new_game()
lm = game.local_maps.get("old_wooden_house")
results.append(check("Game created", game is not None))
results.append(check("Living Room local map exists", lm is not None))
results.append(check("Player starts in old_wooden_house",
                     game.player.location == "old_wooden_house"))
results.append(check("Player at spawn",
                     game.player.local_x == lm.spawn[0]
                     and game.player.local_y == lm.spawn[1]))


# --- 1. Transition through kitchen exit ---
print("\n=== 1. Transition: Kitchen exit ===")
game.player.local_x = 1
game.player.local_y = 5
result = move_local(game, -1, 0)
results.append(check("Kitchen transition succeeds", result.success))
results.append(check("Player location is kitchen",
                     game.player.location == "kitchen"))
results.append(check("Result 'from' is old_wooden_house",
                     result.data.get("from") == "old_wooden_house"))
results.append(check("Result 'location' is kitchen",
                     result.data.get("location") == "kitchen"))
results.append(check("Result has entry_name",
                     "entry_name" in result.data))

kitchen_lm = game.local_maps.get("kitchen")
results.append(check("Kitchen local map exists", kitchen_lm is not None))
results.append(check("Player local_x is valid",
                     0 <= game.player.local_x < kitchen_lm.width))
results.append(check("Player local_y is valid",
                     0 <= game.player.local_y < kitchen_lm.height))


# --- 2. Transition through outside exit (to forest edge) ---
print("\n=== 2. Transition: Outside exit (forest edge) ===")
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]

game.player.local_x = 17
game.player.local_y = 5
result = move_local(game, 1, 0)
results.append(check("Forest Edge transition succeeds", result.success))
results.append(check("Player location is forest_edge",
                     game.player.location == "forest_edge"))
results.append(check("Result 'from' is old_wooden_house",
                     result.data.get("from") == "old_wooden_house"))
# Forest edge "house" exit at (0,5), so entry near (1,5)
results.append(check("Player near forest_edge entry (x near 1)",
                     abs(game.player.local_x - 1) <= 1))
results.append(check("Player near forest_edge entry (y near 5)",
                     abs(game.player.local_y - 5) <= 1))


# --- 3. Transition through upstairs exit ---
print("\n=== 3. Transition: Upstairs exit ===")
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]

game.player.local_x = 10
game.player.local_y = 1
result = move_local(game, 0, -1)
results.append(check("Upstairs transition succeeds", result.success))
results.append(check("Player location is upstairs",
                     game.player.location == "upstairs"))
results.append(check("Result 'from' is old_wooden_house",
                     result.data.get("from") == "old_wooden_house"))

upstairs_lm = game.local_maps.get("upstairs")
results.append(check("Upstairs local map exists", upstairs_lm is not None))
# Upstairs "downstairs" exit at (9,10), entry near (9,9)
results.append(check("Player near upstairs entry (x near 9)",
                     abs(game.player.local_x - 9) <= 1))
results.append(check("Player near upstairs entry (y near 9)",
                     abs(game.player.local_y - 9) <= 1))


# --- 4. Position persistence: save before leaving, restore on return ---
print("\n=== 4. Position persistence ===")
game4 = create_new_game()

# Set a known position in living room
game4.player.location = "old_wooden_house"
game4.player.local_x = 7
game4.player.local_y = 3

# Transition to kitchen (this saves [7,3] for living room)
game4.player.local_x = 1
game4.player.local_y = 5
move_local(game4, -1, 0)
results.append(check("Step 1: in kitchen", game4.player.location == "kitchen"))

# Now manually set kitchen position and transition back
game4.player.location = "kitchen"
game4.player.local_x = 17
game4.player.local_y = 5
_perform_area_transition(game4, "old_wooden_house", "kitchen")
results.append(check("Step 2: back in house", game4.player.location == "old_wooden_house"))

# The position saved for living room was [1, 5] (the position at time of move_local)
# because move_local first sets local_x=0, local_y=5 (moving onto exit tile)
# then _perform_area_transition saves that position.
# But we manually set local_x=7, local_y=3 before that move_local call...
# Actually: move_local sets new_x=1+(-1)=0, new_y=5, so saved position is [0, 5]

# Let me re-verify: the flow was:
# 1. game4.player.local_x = 7, local_y = 3 (set)
# 2. game4.player.local_x = 1, local_y = 5 (overwritten before move_local)
# 3. move_local(game4, -1, 0): new_x = 1+(-1) = 0, new_y = 5
# 4. _perform_area_transition saves _area_positions["old_wooden_house"] = [0, 5]
saved_pos = game4.player._area_positions.get("old_wooden_house")
results.append(check("Living room position saved as [0, 5]",
                     saved_pos == [0, 5]))

# Now test restoration: save a specific position then return
game4b = create_new_game()
game4b.player.location = "old_wooden_house"
game4b.player.local_x = 7
game4b.player.local_y = 3
# Manually save position
game4b.player._area_positions["old_wooden_house"] = [7, 3]

# Go to kitchen and back
game4b.player.location = "kitchen"
game4b.player.local_x = 17
game4b.player.local_y = 5
_perform_area_transition(game4b, "old_wooden_house", "kitchen")
results.append(check("Returned to house", game4b.player.location == "old_wooden_house"))
results.append(check("Position restored to [7, 3]",
                     game4b.player.local_x == 7 and game4b.player.local_y == 3))


# --- 5. First-time entry uses spawn ---
print("\n=== 5. First-time entry (spawn fallback) ===")
game5 = create_new_game()
game5.player._area_positions.pop("deep_forest", None)

# Use _perform_area_transition directly (forest_edge doesn't have local movement)
game5.player.location = "forest_edge"
game5.player.local_x = 17
game5.player.local_y = 5
result = _perform_area_transition(game5, "deep_forest", "back")
results.append(check("Deep Forest transition succeeds", result.success))
results.append(check("Player location is deep_forest",
                     game5.player.location == "deep_forest"))
df_lm = game5.local_maps.get("deep_forest")
results.append(check("Deep Forest local map exists", df_lm is not None))
# Deep forest "back" exit at (0, 5), entry near (1, 5) if walkable
# or spawn (1, 5)
results.append(check("Player at expected entry (near (1,5))",
                     abs(game5.player.local_x - 1) <= 1
                     and abs(game5.player.local_y - 5) <= 1))


# --- 6. Visited locations updated ---
print("\n=== 6. Visited locations ===")
game6 = create_new_game()
results.append(check("New game: only old_wooden_house visited",
                     game6.visited_locations == {"old_wooden_house"}))

game6.player.location = "old_wooden_house"
game6.player.local_x = 1
game6.player.local_y = 5
move_local(game6, -1, 0)
results.append(check("After transition: kitchen visited",
                     "kitchen" in game6.visited_locations))
results.append(check("After transition: old_wooden_house still visited",
                     "old_wooden_house" in game6.visited_locations))


# --- 7. _resolve_entry_point ---
print("\n=== 7. _resolve_entry_point ===")
game7 = create_new_game()
ex, ey = _resolve_entry_point(game7, "kitchen", "outside")
results.append(check("resolve_entry_point for kitchen:outside returns valid",
                     0 <= ex < 19 and 0 <= ey < 11))
results.append(check("Kitchen entry near x=17",
                     abs(ex - 17) <= 1))

ex2, ey2 = _resolve_entry_point(game7, "kitchen", "nonexistent")
kitchen_spawn = game7.local_maps["kitchen"].spawn
results.append(check("Non-existent exit falls back to spawn",
                     ex2 == kitchen_spawn[0] and ey2 == kitchen_spawn[1]))

ex3, ey3 = _resolve_entry_point(game7, "no_map_here", "any")
results.append(check("Missing local map returns (0,0)",
                     ex3 == 0 and ey3 == 0))


# --- 8. Rendering compatibility (skip if no pygame) ---
print("\n=== 8. Rendering compatibility ===")
try:
    import pygame
    pygame.init()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from ui.pygame.world_renderer import LocalRenderer

    game8 = create_new_game()
    lr = LocalRenderer(game8)

    game8.player.location = "old_wooden_house"
    game8.player.local_x = 12
    game8.player.local_y = 5
    lm_check = lr.current_local_map()
    results.append(check("LocalRenderer renders living room",
                         lm_check is not None and lm_check.width == 19))

    # Transition to kitchen
    game8.player.local_x = 1
    game8.player.local_y = 5
    move_local(game8, -1, 0)
    lm_kitchen = lr.current_local_map()
    results.append(check("After transition: LocalRenderer renders kitchen",
                         lm_kitchen is not None))
    results.append(check("Kitchen map width is 19",
                         lm_kitchen.width == 19))

    px, py = lr.player_pixel_pos()
    results.append(check("Player pixel pos is valid (non-negative)",
                         px >= 0 and py >= 0))
    pygame.quit()
except ImportError:
    print("  (pygame not available, skipping rendering tests)")
    results.append(check("Rendering: pygame not available (skipped)", True))


# --- 9. Local movement enabled for all five locations (Phase 6) ---
print("\n=== 9. Local movement scope ===")
game9 = create_new_game()

kitchen_lm9 = game9.local_maps.get("kitchen")
game9.player.location = "kitchen"
game9.player.local_x = kitchen_lm9.spawn[0]
game9.player.local_y = kitchen_lm9.spawn[1]
results.append(check("Kitchen: has_local_movement is True",
                     has_local_movement(game9)))
result = move_local(game9, 1, 0)
results.append(check("Kitchen: move_local succeeds",
                     result.success))

fe_lm9 = game9.local_maps.get("forest_edge")
game9.player.location = "forest_edge"
game9.player.local_x = fe_lm9.spawn[0]
game9.player.local_y = fe_lm9.spawn[1]
results.append(check("Forest Edge: has_local_movement is True",
                     has_local_movement(game9)))

df_lm9 = game9.local_maps.get("deep_forest")
game9.player.location = "deep_forest"
game9.player.local_x = df_lm9.spawn[0]
game9.player.local_y = df_lm9.spawn[1]
results.append(check("Deep Forest: has_local_movement is True",
                     has_local_movement(game9)))

up_lm9 = game9.local_maps.get("upstairs")
game9.player.location = "upstairs"
game9.player.local_x = up_lm9.spawn[0]
game9.player.local_y = up_lm9.spawn[1]
results.append(check("Upstairs: has_local_movement is True",
                     has_local_movement(game9)))


# --- 10. _area_positions after multiple transitions ---
print("\n=== 10. Multiple transitions ===")
game10 = create_new_game()

# Transition: house -> kitchen
game10.player.location = "old_wooden_house"
game10.player.local_x = 1
game10.player.local_y = 5
move_local(game10, -1, 0)
results.append(check("Step 1: in kitchen", game10.player.location == "kitchen"))
results.append(check("Step 1: house position saved",
                     "old_wooden_house" in game10.player._area_positions))

# kitchen -> house (via exit, or manually for direct control)
game10.player.location = "kitchen"
game10.player.local_x = 17
game10.player.local_y = 5
_perform_area_transition(game10, "old_wooden_house", "kitchen")
results.append(check("Step 2: back in house", game10.player.location == "old_wooden_house"))
results.append(check("Step 2: kitchen position saved",
                     "kitchen" in game10.player._area_positions))

# house -> forest_edge
game10.player.local_x = 17
game10.player.local_y = 5
move_local(game10, 1, 0)
results.append(check("Step 3: in forest_edge", game10.player.location == "forest_edge"))
results.append(check("Step 3: house position saved again",
                     "old_wooden_house" in game10.player._area_positions))

# forest_edge -> house (manually)
game10.player.location = "forest_edge"
game10.player.local_x = 1
game10.player.local_y = 5
_perform_area_transition(game10, "old_wooden_house", "house")
results.append(check("Step 4: back in house", game10.player.location == "old_wooden_house"))
results.append(check("Step 4: forest_edge position saved",
                     "forest_edge" in game10.player._area_positions))

results.append(check("All positions saved",
                     len(game10.player._area_positions) >= 3))


# --- 11. Quest progression ---
print("\n=== 11. Quest progression ===")
game11 = create_new_game()
game11.visited_locations.discard("kitchen")
results.append(check("Kitchen not visited before transition",
                     "kitchen" not in game11.visited_locations))

game11.player.location = "old_wooden_house"
game11.player.local_x = 1
game11.player.local_y = 5
result = move_local(game11, -1, 0)
results.append(check("After transition: kitchen visited",
                     "kitchen" in game11.visited_locations))
results.append(check("Result has quest_events",
                     "quest_events" in result.data))


# --- 12. Invalid/missing target ---
print("\n=== 12. Invalid/missing target ===")
game12 = create_new_game()
game12.player.location = "old_wooden_house"
# Use a unique coordinate (5,5) for the fake exit
game12.player.local_x = 6
game12.player.local_y = 5
fake_ep = ExitPoint(x=5, y=5, target_location_id="nonexistent", entry_name="back")
game12.local_maps["old_wooden_house"].exits["fake"] = fake_ep
result = move_local(game12, -1, 0)
results.append(check("Invalid target: transition completes",
                     result.success))
results.append(check("Invalid target: player moved to nonexistent",
                     game12.player.location == "nonexistent"))
del game12.local_maps["old_wooden_house"].exits["fake"]


# --- 13. Save/load preserves _area_positions ---
print("\n=== 13. Save/load preserves _area_positions ===")
from engine.save import save_game, load_game
import tempfile

game13 = create_new_game()
game13.player.location = "old_wooden_house"
game13.player.local_x = 1
game13.player.local_y = 5
move_local(game13, -1, 0)
# _area_positions should have old_wooden_house
results.append(check("Before save: position saved",
                     "old_wooden_house" in game13.player._area_positions))

with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
    tmp = f.name
try:
    save_game(game13, path=__import__("pathlib").Path(tmp))
    loaded = load_game(path=__import__("pathlib").Path(tmp))
    results.append(check("Load succeeds", loaded is not None))
    results.append(check("Loaded _area_positions has house",
                         "old_wooden_house" in loaded.player._area_positions))
    results.append(check("Loaded position is [0, 5]",
                         loaded.player._area_positions["old_wooden_house"] == [0, 5]))
    results.append(check("Loaded local_x", loaded.player.local_x == game13.player.local_x))
    results.append(check("Loaded local_y", loaded.player.local_y == game13.player.local_y))
finally:
    os.unlink(tmp)


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
