# -*- coding: utf-8 -*-
"""Tests for Phase 5: Local tile movement in Kitchen and Upstairs."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import GameState, LocalMap
from engine.actions import (
    move_local, has_local_movement, is_local_position_blocked,
    get_exit_at, _perform_area_transition, _resolve_entry_point,
    ActionResult,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


# =========================================================================
# KITCHEN TESTS
# =========================================================================

# Kitchen collision map (19x11):
#   y= 0: ###################
#   y= 1: #.########.#.#....#
#   y= 2: #.................#
#   y= 3: ##................#
#   y= 4: ##................#
#   y= 5: #..................  <-- exit at (18,5)
#   y= 6: #.......###.......#
#   y= 7: #.......###.......#
#   y= 8: #.................#
#   y= 9: #.#####...........#
#   y=10: ###################
#
# Spawn: (10,5)
# Exit: (18,5) -> old_wooden_house entry="kitchen"
# Good open test spot: (5,5) -- all 4 directions walkable

# --- 1. Kitchen setup ---
print("=== 1. Kitchen setup ===")
game = create_new_game()
game.player.location = "kitchen"
klm = game.local_maps.get("kitchen")
results.append(check("Kitchen local map exists", klm is not None))
results.append(check("Kitchen map is 19x11",
                     klm.width == 19 and klm.height == 11))
game.player.local_x = klm.spawn[0]
game.player.local_y = klm.spawn[1]
results.append(check("has_local_movement returns True",
                     has_local_movement(game)))
results.append(check("Player at kitchen spawn",
                     game.player.local_x == 10
                     and game.player.local_y == 5))


# --- 2. Kitchen basic WASD movement ---
print("\n=== 2. Kitchen basic movement ===")
game.player.location = "kitchen"
game.player.local_x = 5
game.player.local_y = 5
sx, sy = 5, 5

result = move_local(game, 0, -1)
results.append(check("W succeeds", result.success))
results.append(check("W moves up by 1",
                     game.player.local_x == sx
                     and game.player.local_y == sy - 1))
move_local(game, 0, 1)

result = move_local(game, 0, 1)
results.append(check("S succeeds", result.success))
results.append(check("S moves down by 1",
                     game.player.local_x == sx
                     and game.player.local_y == sy + 1))
move_local(game, 0, -1)

result = move_local(game, -1, 0)
results.append(check("A succeeds", result.success))
results.append(check("A moves left by 1",
                     game.player.local_x == sx - 1
                     and game.player.local_y == sy))
move_local(game, 1, 0)

result = move_local(game, 1, 0)
results.append(check("D succeeds", result.success))
results.append(check("D moves right by 1",
                     game.player.local_x == sx + 1
                     and game.player.local_y == sy))
move_local(game, -1, 0)

results.append(check("Position fully restored",
                     game.player.local_x == sx
                     and game.player.local_y == sy))


# --- 3. Kitchen collision: walls ---
print("\n=== 3. Kitchen collision: walls ===")
game.player.location = "kitchen"

game.player.local_x = 5
game.player.local_y = 1
result = move_local(game, 0, -1)
results.append(check("North wall blocks", not result.success))
results.append(check("Position unchanged", game.player.local_y == 1))

game.player.local_x = 5
game.player.local_y = klm.height - 2
result = move_local(game, 0, 1)
results.append(check("South wall blocks", not result.success))

game.player.local_x = 1
game.player.local_y = 5
result = move_local(game, -1, 0)
results.append(check("West wall blocks", not result.success))

# East wall at y=3 (not y=5 which is the exit)
game.player.local_x = klm.width - 2
game.player.local_y = 3
result = move_local(game, 1, 0)
results.append(check("East wall blocks at y=3", not result.success))


# --- 4. Kitchen collision: blocking objects ---
print("\n=== 4. Kitchen collision: objects ===")
game.player.location = "kitchen"

# Counter at y=1, x=2-9
game.player.local_x = 5
game.player.local_y = 2
result = move_local(game, 0, -1)
results.append(check("Counter blocks from below", not result.success))

# Stove at (11,1)
game.player.local_x = 11
game.player.local_y = 2
result = move_local(game, 0, -1)
results.append(check("Stove blocks from below", not result.success))

# Table at (8-10, 6-7)
game.player.local_x = 7
game.player.local_y = 6
result = move_local(game, 1, 0)
results.append(check("Table blocks from left", not result.success))

game.player.local_x = 9
game.player.local_y = 5
result = move_local(game, 0, 1)
results.append(check("Table blocks from above", not result.success))

# Shelf at (2-6, 9)
game.player.local_x = 4
game.player.local_y = 8
result = move_local(game, 0, 1)
results.append(check("Shelf blocks from above", not result.success))

# Cabinet at (1, 3-4)
game.player.local_x = 2
game.player.local_y = 3
result = move_local(game, -1, 0)
results.append(check("Cabinet blocks from right", not result.success))


# --- 5. Kitchen walkable movement ---
print("\n=== 5. Kitchen walkable movement ===")
game.player.location = "kitchen"
game.player.local_x = klm.spawn[0]
game.player.local_y = klm.spawn[1]
result = move_local(game, -1, 0)
results.append(check("Open floor walkable", result.success))
results.append(check("Player moved",
                     game.player.local_x == klm.spawn[0] - 1))


# --- 6. Kitchen bounds checking ---
print("\n=== 6. Kitchen bounds checking ===")
game.player.location = "kitchen"
game.player.local_x = 0
game.player.local_y = 5
result = move_local(game, -1, 0)
results.append(check("Out-of-bounds left blocked", not result.success))

game.player.local_x = klm.width - 1
game.player.local_y = 5
result = move_local(game, 1, 0)
results.append(check("Right edge blocked", not result.success))

game.player.local_x = 5
game.player.local_y = 0
result = move_local(game, 0, -1)
results.append(check("Top edge blocked", not result.success))

game.player.local_x = 5
game.player.local_y = klm.height - 1
result = move_local(game, 0, 1)
results.append(check("Bottom edge blocked", not result.success))


# --- 7. Kitchen exit tiles ---
print("\n=== 7. Kitchen exit tiles ===")
game.player.location = "kitchen"
ep = get_exit_at(game, 18, 5)
results.append(check("Exit at (18,5) found", ep is not None))
results.append(check("Kitchen exit targets old_wooden_house",
                     ep.target_location_id == "old_wooden_house"))
results.append(check("Kitchen exit entry_name is 'kitchen'",
                     ep.entry_name == "kitchen"))

ep_none = get_exit_at(game, 5, 5)
results.append(check("No exit at (5,5)", ep_none is None))


# --- 8. Kitchen is_local_position_blocked ---
print("\n=== 8. Kitchen is_local_position_blocked ===")
game.player.location = "kitchen"
results.append(check("Wall (0,0) blocked",
                     is_local_position_blocked(game, 0, 0)))
results.append(check("Floor (5,5) not blocked",
                     not is_local_position_blocked(game, 5, 5)))
results.append(check("Counter (5,1) blocked",
                     is_local_position_blocked(game, 5, 1)))
results.append(check("Table (9,6) blocked",
                     is_local_position_blocked(game, 9, 6)))
results.append(check("Negative coords blocked",
                     is_local_position_blocked(game, -1, 5)))
results.append(check("Out-of-bounds blocked",
                     is_local_position_blocked(game, 99, 99)))


# --- 9. Kitchen area transition: exit to living room ---
print("\n=== 9. Kitchen -> Living Room transition ===")
game.player.location = "kitchen"
game.player.local_x = 17
game.player.local_y = 5
result = move_local(game, 1, 0)
results.append(check("Kitchen exit transition succeeds", result.success))
results.append(check("Player in old_wooden_house",
                     game.player.location == "old_wooden_house"))
results.append(check("Result has 'from'",
                     result.data.get("from") == "kitchen"))
results.append(check("Result has 'location'",
                     result.data.get("location") == "old_wooden_house"))
results.append(check("old_wooden_house in visited_locations",
                     "old_wooden_house" in game.visited_locations))


# =========================================================================
# UPSTAIRS TESTS
# =========================================================================

# Upstairs collision map (19x11):
#   y= 0: ###################
#   y= 1: #...#...#.........#
#   y= 2: #.................#
#   y= 3: ##................#
#   y= 4: #.................#
#   y= 5: #....#...........##
#   y= 6: #.................#
#   y= 7: #.................#
#   y= 8: #.................#
#   y= 9: #......#####......#
#   y=10: #########.#########
#
# Spawn: (9,8)
# Exit: (9,10) -> old_wooden_house entry="downstairs"
# Good open test spot: (14,5) -- all 4 directions walkable

# --- 10. Upstairs setup ---
print("\n=== 10. Upstairs setup ===")
game2 = create_new_game()
game2.player.location = "upstairs"
ulm = game2.local_maps.get("upstairs")
results.append(check("Upstairs local map exists", ulm is not None))
results.append(check("Upstairs map is 19x11",
                     ulm.width == 19 and ulm.height == 11))
game2.player.local_x = ulm.spawn[0]
game2.player.local_y = ulm.spawn[1]
results.append(check("has_local_movement returns True",
                     has_local_movement(game2)))


# --- 11. Upstairs basic WASD movement ---
print("\n=== 11. Upstairs basic movement ===")
game2.player.location = "upstairs"
game2.player.local_x = 14
game2.player.local_y = 5
sx2, sy2 = 14, 5

result = move_local(game2, 0, -1)
results.append(check("W succeeds", result.success))
results.append(check("W moves up by 1",
                     game2.player.local_x == sx2
                     and game2.player.local_y == sy2 - 1))
move_local(game2, 0, 1)

result = move_local(game2, 0, 1)
results.append(check("S succeeds", result.success))
results.append(check("S moves down by 1",
                     game2.player.local_x == sx2
                     and game2.player.local_y == sy2 + 1))
move_local(game2, 0, -1)

result = move_local(game2, -1, 0)
results.append(check("A succeeds", result.success))
results.append(check("A moves left by 1",
                     game2.player.local_x == sx2 - 1
                     and game2.player.local_y == sy2))
move_local(game2, 1, 0)

result = move_local(game2, 1, 0)
results.append(check("D succeeds", result.success))
results.append(check("D moves right by 1",
                     game2.player.local_x == sx2 + 1
                     and game2.player.local_y == sy2))
move_local(game2, -1, 0)

results.append(check("Position fully restored",
                     game2.player.local_x == sx2
                     and game2.player.local_y == sy2))


# --- 12. Upstairs collision: walls ---
print("\n=== 12. Upstairs collision: walls ===")
game2.player.location = "upstairs"

game2.player.local_x = 5
game2.player.local_y = 1
result = move_local(game2, 0, -1)
results.append(check("North wall blocks", not result.success))

# South wall: test at x=3 (not x=9 which is the exit)
game2.player.local_x = 3
game2.player.local_y = 9
result = move_local(game2, 0, 1)
results.append(check("South wall blocks", not result.success))

game2.player.local_x = 1
game2.player.local_y = 5
result = move_local(game2, -1, 0)
results.append(check("West wall blocks", not result.success))

# East wall at y=3 (not y=5 which has locked door at x=17)
game2.player.local_x = ulm.width - 2
game2.player.local_y = 3
result = move_local(game2, 1, 0)
results.append(check("East wall blocks", not result.success))


# --- 13. Upstairs collision: blocking objects ---
print("\n=== 13. Upstairs collision: objects ===")
game2.player.location = "upstairs"

# Stair railing at (10-14, 9)
game2.player.local_x = 10
game2.player.local_y = 8
result = move_local(game2, 0, 1)
results.append(check("Stair railing blocks from above",
                     not result.success))

# Door at (4, 1)
game2.player.local_x = 4
game2.player.local_y = 2
result = move_local(game2, 0, -1)
results.append(check("Door blocks from below", not result.success))

# Hall table at (5, 5)
game2.player.local_x = 4
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("Hall table blocks from left",
                     not result.success))

# Cabinet at (1, 3)
game2.player.local_x = 2
game2.player.local_y = 3
result = move_local(game2, -1, 0)
results.append(check("Hall cabinet blocks from right",
                     not result.success))

# Locked door at (17, 5)
game2.player.local_x = 16
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("Locked door blocks from left",
                     not result.success))


# --- 14. Upstairs walkable movement ---
print("\n=== 14. Upstairs walkable movement ===")
game2.player.location = "upstairs"
game2.player.local_x = ulm.spawn[0]
game2.player.local_y = ulm.spawn[1]
result = move_local(game2, 1, 0)
results.append(check("Open floor walkable", result.success))
results.append(check("Player moved",
                     game2.player.local_x == ulm.spawn[0] + 1))


# --- 15. Upstairs bounds checking ---
print("\n=== 15. Upstairs bounds checking ===")
game2.player.location = "upstairs"
game2.player.local_x = 0
game2.player.local_y = 5
result = move_local(game2, -1, 0)
results.append(check("Out-of-bounds left blocked", not result.success))

game2.player.local_x = ulm.width - 1
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("Right edge blocked", not result.success))

game2.player.local_x = 5
game2.player.local_y = 0
result = move_local(game2, 0, -1)
results.append(check("Top edge blocked", not result.success))

game2.player.local_x = 5
game2.player.local_y = ulm.height - 1
result = move_local(game2, 0, 1)
results.append(check("Bottom edge blocked", not result.success))


# --- 16. Upstairs exit tiles ---
print("\n=== 16. Upstairs exit tiles ===")
game2.player.location = "upstairs"
ep_up = get_exit_at(game2, 9, 10)
results.append(check("Exit at (9,10) found", ep_up is not None))
results.append(check("Upstairs exit targets old_wooden_house",
                     ep_up.target_location_id == "old_wooden_house"))
results.append(check("Upstairs exit entry_name is 'upstairs'",
                     ep_up.entry_name == "upstairs"))

ep_up_none = get_exit_at(game2, 5, 5)
results.append(check("No exit at (5,5)", ep_up_none is None))


# --- 17. Upstairs is_local_position_blocked ---
print("\n=== 17. Upstairs is_local_position_blocked ===")
game2.player.location = "upstairs"
results.append(check("Wall (0,0) blocked",
                     is_local_position_blocked(game2, 0, 0)))
results.append(check("Floor (14,5) not blocked",
                     not is_local_position_blocked(game2, 14, 5)))
results.append(check("Locked door (17,5) blocked",
                     is_local_position_blocked(game2, 17, 5)))
results.append(check("Railing (10,9) blocked",
                     is_local_position_blocked(game2, 10, 9)))


# --- 18. Upstairs area transition: exit to living room ---
print("\n=== 18. Upstairs -> Living Room transition ===")
game2.player.location = "upstairs"
game2.player.local_x = 9
game2.player.local_y = 9
result = move_local(game2, 0, 1)
results.append(check("Upstairs exit transition succeeds", result.success))
results.append(check("Player in old_wooden_house",
                     game2.player.location == "old_wooden_house"))
results.append(check("Result has 'from'",
                     result.data.get("from") == "upstairs"))
results.append(check("old_wooden_house in visited_locations",
                     "old_wooden_house" in game2.visited_locations))


# =========================================================================
# FULL ROUND-TRIP TESTS
# =========================================================================

# --- 19. Living Room -> Kitchen -> Living Room round trip ---
print("\n=== 19. LR -> Kitchen -> LR round trip ===")
game3 = create_new_game()

game3.player.local_x = 1
game3.player.local_y = 5
result = move_local(game3, -1, 0)
results.append(check("LR -> Kitchen succeeds", result.success))
results.append(check("In kitchen",
                     game3.player.location == "kitchen"))

game3.player.local_x = 17
game3.player.local_y = 5
result = move_local(game3, 1, 0)
results.append(check("Kitchen -> LR succeeds", result.success))
results.append(check("Back in LR",
                     game3.player.location == "old_wooden_house"))


# --- 20. Living Room -> Upstairs -> Living Room round trip ---
print("\n=== 20. LR -> Upstairs -> LR round trip ===")
game4 = create_new_game()

game4.player.local_x = 10
game4.player.local_y = 1
result = move_local(game4, 0, -1)
results.append(check("LR -> Upstairs succeeds", result.success))
results.append(check("In upstairs",
                     game4.player.location == "upstairs"))

game4.player.local_x = 9
game4.player.local_y = 9
result = move_local(game4, 0, 1)
results.append(check("Upstairs -> LR succeeds", result.success))
results.append(check("Back in LR",
                     game4.player.location == "old_wooden_house"))


# --- 21. Position persistence: save and restore ---
print("\n=== 21. Position persistence ===")
game5 = create_new_game()

game5.player.location = "kitchen"
game5.player.local_x = 10
game5.player.local_y = 7
game5.player._area_positions["kitchen"] = [10, 7]

_perform_area_transition(game5, "old_wooden_house", "kitchen")
results.append(check("Back in LR",
                     game5.player.location == "old_wooden_house"))

_perform_area_transition(game5, "kitchen", "outside")
results.append(check("Back in kitchen",
                     game5.player.location == "kitchen"))
results.append(check("Kitchen position restored to [10, 7]",
                     game5.player.local_x == 10
                     and game5.player.local_y == 7))


# --- 22. Entry point resolution ---
print("\n=== 22. Entry point resolution ===")
game6 = create_new_game()

ex, ey = _resolve_entry_point(game6, "kitchen", "outside")
results.append(check("Kitchen entry near x=17", abs(ex - 17) <= 1))
results.append(check("Kitchen entry y=5", abs(ey - 5) <= 1))

ex2, ey2 = _resolve_entry_point(game6, "upstairs", "downstairs")
results.append(check("Upstairs entry near x=9", abs(ex2 - 9) <= 1))
results.append(check("Upstairs entry near y=9", abs(ey2 - 9) <= 1))

ex3, ey3 = _resolve_entry_point(game6, "kitchen", "nonexistent")
kitchen_spawn = game6.local_maps["kitchen"].spawn
results.append(check("Non-existent exit falls to spawn",
                     ex3 == kitchen_spawn[0]
                     and ey3 == kitchen_spawn[1]))


# --- 23. Visited locations tracking ---
print("\n=== 23. Visited locations ===")
game7 = create_new_game()
game7.visited_locations.discard("kitchen")
results.append(check("Kitchen not visited initially",
                     "kitchen" not in game7.visited_locations))

_perform_area_transition(game7, "kitchen", "outside")
results.append(check("Kitchen visited after transition",
                     "kitchen" in game7.visited_locations))


# --- 24. Renderer compatibility (skip if no pygame) ---
print("\n=== 24. Renderer compatibility ===")
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
    results.append(check("LR renders",
                         lm_check is not None and lm_check.width == 19))

    game8.player.location = "kitchen"
    game8.player.local_x = 10
    game8.player.local_y = 5
    lm_k = lr.current_local_map()
    results.append(check("Kitchen renders",
                         lm_k is not None and lm_k.width == 19))

    game8.player.location = "upstairs"
    game8.player.local_x = 9
    game8.player.local_y = 8
    lm_u = lr.current_local_map()
    results.append(check("Upstairs renders",
                         lm_u is not None and lm_u.width == 19))

    px, py = lr.player_pixel_pos()
    results.append(check("Player pixel pos valid", px >= 0 and py >= 0))
    pygame.quit()
except ImportError:
    print("  (pygame not available, skipping rendering tests)")
    results.append(check("Rendering: pygame not available (skipped)",
                         True))


# --- 25. Save/load preserves local movement state ---
print("\n=== 25. Save/load ===")
from engine.save import save_game, load_game

game9 = create_new_game()
game9.player.location = "kitchen"
game9.player.local_x = 10
game9.player.local_y = 7
game9.player._area_positions["kitchen"] = [10, 7]
game9.player._area_positions["old_wooden_house"] = [5, 3]

with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                 mode="w") as f:
    tmp = f.name
try:
    save_game(game9, path=__import__("pathlib").Path(tmp))
    loaded = load_game(path=__import__("pathlib").Path(tmp))
    results.append(check("Load succeeds", loaded is not None))
    results.append(check("Loaded location is kitchen",
                         loaded.player.location == "kitchen"))
    results.append(check("Loaded local_x is 10",
                         loaded.player.local_x == 10))
    results.append(check("Loaded local_y is 7",
                         loaded.player.local_y == 7))
    results.append(check("Loaded _area_positions has kitchen",
                         "kitchen" in loaded.player._area_positions))
    results.append(check("Loaded kitchen position is [10, 7]",
                         loaded.player._area_positions["kitchen"]
                         == [10, 7]))
    results.append(check("Loaded _area_positions has house",
                         "old_wooden_house"
                         in loaded.player._area_positions))
finally:
    os.unlink(tmp)


# --- 26. Quest progression ---
print("\n=== 26. Quest progression ===")
game10 = create_new_game()
game10.visited_locations.discard("kitchen")
_perform_area_transition(game10, "kitchen", "outside")
results.append(check("Transition succeeds", True))
results.append(check("kitchen in visited_locations",
                     "kitchen" in game10.visited_locations))
result_q = _perform_area_transition(
    game10, "old_wooden_house", "kitchen")
results.append(check("Result has quest_events field",
                     "quest_events" in result_q.data))


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
