# -*- coding: utf-8 -*-
"""Tests for Phase 3: Local tile movement in the Living Room."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import GameState, LocalMap
from engine.actions import (
    move_local, has_local_movement, is_local_position_blocked,
    get_exit_at, ActionResult,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


# --- Setup ---
print("=== Setup ===")
game = create_new_game()
lm = game.local_maps.get("old_wooden_house")
results.append(check("Living Room local map exists", lm is not None))
results.append(check("Player starts in old_wooden_house",
                     game.player.location == "old_wooden_house"))
results.append(check("Player local_x matches spawn",
                     game.player.local_x == lm.spawn[0]))
results.append(check("Player local_y matches spawn",
                     game.player.local_y == lm.spawn[1]))
results.append(check("has_local_movement returns True",
                     has_local_movement(game)))
results.append(check("Living Room map is 19x11",
                     lm.width == 19 and lm.height == 11))


# --- 1. Basic movement ---
print("\n=== 1. Basic movement ===")
start_x, start_y = game.player.local_x, game.player.local_y

# W (up): dy = -1
result = move_local(game, 0, -1)
results.append(check("W succeeds", result.success))
results.append(check("W moves player up by 1",
                     game.player.local_x == start_x
                     and game.player.local_y == start_y - 1))

# Undo: S (down)
result = move_local(game, 0, 1)
results.append(check("S undoes W", result.success))
results.append(check("Position restored",
                     game.player.local_x == start_x
                     and game.player.local_y == start_y))

# S (down): dy = +1
result = move_local(game, 0, 1)
results.append(check("S succeeds", result.success))
results.append(check("S moves player down by 1",
                     game.player.local_x == start_x
                     and game.player.local_y == start_y + 1))

# Undo: W
move_local(game, 0, -1)

# A (left): dx = -1
result = move_local(game, -1, 0)
results.append(check("A succeeds", result.success))
results.append(check("A moves player left by 1",
                     game.player.local_x == start_x - 1
                     and game.player.local_y == start_y))

# Undo: D
move_local(game, 1, 0)

# D (right): dx = +1
result = move_local(game, 1, 0)
results.append(check("D succeeds", result.success))
results.append(check("D moves player right by 1",
                     game.player.local_x == start_x + 1
                     and game.player.local_y == start_y))

# Undo: A
move_local(game, -1, 0)
results.append(check("Position fully restored",
                     game.player.local_x == start_x
                     and game.player.local_y == start_y))


# --- 2. Collision: walls ---
print("\n=== 2. Collision: walls ===")
# Move to spawn and then try to walk into the north wall
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]

# Walk up to the wall (spawn is at y=5, wall at y=0)
for _ in range(4):
    move_local(game, 0, -1)
# Now at y=1 (just below the wall)
result = move_local(game, 0, -1)
results.append(check("Wall blocks movement", not result.success))
results.append(check("Position unchanged at wall",
                     game.player.local_y == 1))

# Walk back to center
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]


# --- 3. Collision: blocking furniture ---
print("\n=== 3. Collision: blocking furniture ===")
# Table is at (8,5) to (10,6) — try to walk into it
game.player.local_x = 7
game.player.local_y = 5
result = move_local(game, 1, 0)  # try to walk into table
results.append(check("Table blocks movement", not result.success))
results.append(check("Position unchanged at table",
                     game.player.local_x == 7 and game.player.local_y == 5))


# --- 4. Walkable movement ---
print("\n=== 4. Walkable movement ===")
# Walk on open floor
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]
result = move_local(game, -1, 0)
results.append(check("Open floor is walkable", result.success))
results.append(check("Player moved to open floor",
                     game.player.local_x == lm.spawn[0] - 1))


# --- 5. Bounds checking ---
print("\n=== 5. Bounds checking ===")
# Walk into top wall (non-exit position)
game.player.local_x = 3
game.player.local_y = 1
result = move_local(game, 0, -1)  # would be y=0 (wall)
results.append(check("Top wall blocks", not result.success))

# Walk into bottom wall
game.player.local_x = 3
game.player.local_y = lm.height - 2
result = move_local(game, 0, 1)  # would be y=height-1 (wall)
results.append(check("Bottom wall blocks", not result.success))

# Walk into couch (blocking object at (1,4))
game.player.local_x = 2
game.player.local_y = 4
result = move_local(game, -1, 0)  # would be (1,4) couch
results.append(check("Couch blocks from right", not result.success))

# Walk into cabinet (blocking at (2,9))
game.player.local_x = 3
game.player.local_y = 8
result = move_local(game, 0, 1)  # would be (3,9) cabinet
results.append(check("Cabinet blocks from above", not result.success))


# --- 6. Exit tiles: transition to target ---
print("\n=== 6. Exit tiles ===")
# Reset to living room
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]

# Kitchen exit is at (0, 5) — walk there
game.player.local_x = 1
game.player.local_y = 5
result = move_local(game, -1, 0)  # walk onto exit at (0,5)
results.append(check("Exit tile triggers transition", result.success))
results.append(check("Player moved to kitchen",
                     game.player.location == "kitchen"))
results.append(check("Result has 'from' field",
                     result.data.get("from") == "old_wooden_house"))

# Reset back for remaining tests
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]


# --- 7. get_exit_at ---
print("\n=== 7. get_exit_at ===")
ep = get_exit_at(game, 0, 5)
results.append(check("Exit at (0,5) found", ep is not None))
results.append(check("Kitchen exit target", ep.target_location_id == "kitchen"))

ep_none = get_exit_at(game, 5, 5)
results.append(check("No exit at (5,5)", ep_none is None))


# --- 8. is_local_position_blocked ---
print("\n=== 8. is_local_position_blocked ===")
results.append(check("Wall (0,0) is blocked",
                     is_local_position_blocked(game, 0, 0)))
results.append(check("Floor (5,5) is not blocked",
                     not is_local_position_blocked(game, 5, 5)))
results.append(check("Table (8,5) is blocked",
                     is_local_position_blocked(game, 8, 5)))
results.append(check("Negative coords blocked",
                     is_local_position_blocked(game, -1, 5)))
results.append(check("Out-of-bounds blocked",
                     is_local_position_blocked(game, 99, 99)))


# --- 9. Other locations: all have local movement now (Phase 6) ---
print("\n=== 9. Other locations ===")
kitchen_lm = game.local_maps.get("kitchen")
results.append(check("Kitchen local map exists", kitchen_lm is not None))
game.player.location = "kitchen"
game.player.local_x = kitchen_lm.spawn[0]
game.player.local_y = kitchen_lm.spawn[1]
results.append(check("Kitchen: has_local_movement is True",
                     has_local_movement(game)))
result = move_local(game, 1, 0)
results.append(check("Kitchen: move_local succeeds",
                     result.success))

fe_lm = game.local_maps.get("forest_edge")
results.append(check("Forest Edge local map exists", fe_lm is not None))
game.player.location = "forest_edge"
game.player.local_x = fe_lm.spawn[0]
game.player.local_y = fe_lm.spawn[1]
results.append(check("Forest Edge: has_local_movement is True",
                     has_local_movement(game)))

df_lm = game.local_maps.get("deep_forest")
results.append(check("Deep Forest local map exists", df_lm is not None))
game.player.location = "deep_forest"
game.player.local_x = df_lm.spawn[0]
game.player.local_y = df_lm.spawn[1]
results.append(check("Deep Forest: has_local_movement is True",
                     has_local_movement(game)))

game.player.location = "upstairs"
up_lm = game.local_maps.get("upstairs")
results.append(check("Upstairs local map exists", up_lm is not None))
game.player.local_x = up_lm.spawn[0]
game.player.local_y = up_lm.spawn[1]
results.append(check("Upstairs: has_local_movement is True",
                     has_local_movement(game)))

# Reset to living room for remaining tests
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]


# --- 10. Area transition on exit ---
print("\n=== 10. Area transition on exit ===")
# Reset to living room
game.player.location = "old_wooden_house"
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]

# Walk to the upstairs exit at (10, 0)
game.player.local_x = 10
game.player.local_y = 1
result = move_local(game, 0, -1)  # walk onto exit at (10,0)
results.append(check("Upstairs exit transitions", result.success))
results.append(check("Player moved to upstairs",
                     game.player.location == "upstairs"))
results.append(check("Result has 'from' field",
                     result.data.get("from") == "old_wooden_house"))
results.append(check("Result has location field",
                     result.data.get("location") == "upstairs"))


# --- 11. ActionResult consistency ---
print("\n=== 11. ActionResult consistency ===")
game.player.local_x = lm.spawn[0]
game.player.local_y = lm.spawn[1]
result = move_local(game, 1, 0)
results.append(check("Result is ActionResult", isinstance(result, ActionResult)))
results.append(check("Result has success attr", hasattr(result, "success")))
results.append(check("Result has message attr", hasattr(result, "message")))
results.append(check("Result has data attr", hasattr(result, "data")))


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
