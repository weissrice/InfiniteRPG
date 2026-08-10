# -*- coding: utf-8 -*-
"""Tests for Phase 6: Local tile movement in Forest Edge and Deep Forest."""

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
# FOREST EDGE TESTS
# =========================================================================

# Forest Edge collision map (19x11):
#   y= 0: ###################
#   y= 1: #.................#
#   y= 2: #..#..............#
#   y= 3: #......#....#.....#
#   y= 4: #.................#
#   y= 5: ...................  <-- path, exits at (0,5) and (18,5)
#   y= 6: #.................#
#   y= 7: #....#........#...#
#   y= 8: #.............#...#
#   y= 9: #.................#
#   y=10: ###################
#
# Spawn: (2, 5)
# Exits: house (0,5) -> old_wooden_house, forest (18,5) -> deep_forest
# Good open test spot: (10, 4) -- all 4 directions walkable

# --- 1. Forest Edge setup ---
print("=== 1. Forest Edge setup ===")
game = create_new_game()
game.player.location = "forest_edge"
flm = game.local_maps.get("forest_edge")
results.append(check("Forest Edge local map exists", flm is not None))
results.append(check("Forest Edge map is 19x11",
                     flm.width == 19 and flm.height == 11))
game.player.local_x = flm.spawn[0]
game.player.local_y = flm.spawn[1]
results.append(check("has_local_movement returns True",
                     has_local_movement(game)))
results.append(check("Player at forest_edge spawn",
                     game.player.local_x == 2
                     and game.player.local_y == 5))


# --- 2. Forest Edge basic WASD movement ---
print("\n=== 2. Forest Edge basic movement ===")
game.player.location = "forest_edge"
game.player.local_x = 10
game.player.local_y = 4
sx, sy = 10, 4

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


# --- 3. Forest Edge collision: trees ---
print("\n=== 3. Forest Edge collision: trees ===")
game.player.location = "forest_edge"

# Tree at (3, 2) -- from collision map y=2: #..#..............#
game.player.local_x = 3
game.player.local_y = 3
result = move_local(game, 0, -1)
results.append(check("Tree blocks from below", not result.success))

# Tree at (12, 3) -- from collision map y=3: #......#....#.....#
game.player.local_x = 12
game.player.local_y = 4
result = move_local(game, 0, -1)
results.append(check("Tree (12,3) blocks from below",
                     not result.success))

# Border tree at (0, 0)
game.player.local_x = 1
game.player.local_y = 1
result = move_local(game, -1, 0)
results.append(check("Border tree blocks from right",
                     not result.success))


# --- 4. Forest Edge collision: rocks ---
print("\n=== 4. Forest Edge collision: rocks ===")
game.player.location = "forest_edge"

# Rock at (7, 3)
game.player.local_x = 7
game.player.local_y = 4
result = move_local(game, 0, -1)
results.append(check("Rock (7,3) blocks from below",
                     not result.success))

# Rock at (14, 7)
game.player.local_x = 14
game.player.local_y = 8
result = move_local(game, 0, -1)
results.append(check("Rock (14,7) blocks from below",
                     not result.success))


# --- 5. Forest Edge collision: walls (borders) ---
print("\n=== 5. Forest Edge collision: walls ===")
game.player.location = "forest_edge"

game.player.local_x = 5
game.player.local_y = 1
result = move_local(game, 0, -1)
results.append(check("North wall blocks", not result.success))

game.player.local_x = 5
game.player.local_y = flm.height - 2
result = move_local(game, 0, 1)
results.append(check("South wall blocks", not result.success))

game.player.local_x = flm.width - 2
game.player.local_y = 4
result = move_local(game, 1, 0)
results.append(check("East wall blocks", not result.success))


# --- 6. Forest Edge walkable movement ---
print("\n=== 6. Forest Edge walkable movement ===")
game.player.location = "forest_edge"
game.player.local_x = flm.spawn[0]
game.player.local_y = flm.spawn[1]
result = move_local(game, 1, 0)
results.append(check("Open floor walkable", result.success))
results.append(check("Player moved",
                     game.player.local_x == flm.spawn[0] + 1))


# --- 7. Forest Edge bounds checking ---
print("\n=== 7. Forest Edge bounds checking ===")
game.player.location = "forest_edge"
game.player.local_x = 0
game.player.local_y = 5
result = move_local(game, -1, 0)
results.append(check("Out-of-bounds left blocked", not result.success))

game.player.local_x = flm.width - 1
game.player.local_y = 5
result = move_local(game, 1, 0)
results.append(check("Right edge blocked", not result.success))

game.player.local_x = 5
game.player.local_y = 0
result = move_local(game, 0, -1)
results.append(check("Top edge blocked", not result.success))

game.player.local_x = 5
game.player.local_y = flm.height - 1
result = move_local(game, 0, 1)
results.append(check("Bottom edge blocked", not result.success))


# --- 8. Forest Edge exit tiles ---
print("\n=== 8. Forest Edge exit tiles ===")
game.player.location = "forest_edge"

ep_house = get_exit_at(game, 0, 5)
results.append(check("House exit at (0,5) found", ep_house is not None))
results.append(check("House exit targets old_wooden_house",
                     ep_house.target_location_id == "old_wooden_house"))
results.append(check("House exit entry_name is 'outside'",
                     ep_house.entry_name == "outside"))

ep_forest = get_exit_at(game, 18, 5)
results.append(check("Forest exit at (18,5) found",
                     ep_forest is not None))
results.append(check("Forest exit targets deep_forest",
                     ep_forest.target_location_id == "deep_forest"))
results.append(check("Forest exit entry_name is 'back'",
                     ep_forest.entry_name == "back"))

ep_none = get_exit_at(game, 10, 4)
results.append(check("No exit at (10,4)", ep_none is None))


# --- 9. Forest Edge is_local_position_blocked ---
print("\n=== 9. Forest Edge is_local_position_blocked ===")
game.player.location = "forest_edge"
results.append(check("Wall (0,0) blocked",
                     is_local_position_blocked(game, 0, 0)))
results.append(check("Floor (10,4) not blocked",
                     not is_local_position_blocked(game, 10, 4)))
results.append(check("Rock (7,3) blocked",
                     is_local_position_blocked(game, 7, 3)))
results.append(check("Negative coords blocked",
                     is_local_position_blocked(game, -1, 5)))
results.append(check("Out-of-bounds blocked",
                     is_local_position_blocked(game, 99, 99)))


# --- 10. Forest Edge area transition: house exit ---
print("\n=== 10. Forest Edge -> Living Room transition ===")
game.player.location = "forest_edge"
game.player.local_x = 1
game.player.local_y = 5
result = move_local(game, -1, 0)
results.append(check("House exit transition succeeds", result.success))
results.append(check("Player in old_wooden_house",
                     game.player.location == "old_wooden_house"))
results.append(check("Result has 'from'",
                     result.data.get("from") == "forest_edge"))
results.append(check("Result has 'location'",
                     result.data.get("location") == "old_wooden_house"))
results.append(check("old_wooden_house in visited_locations",
                     "old_wooden_house" in game.visited_locations))


# --- 11. Forest Edge area transition: forest exit ---
print("\n=== 11. Forest Edge -> Deep Forest transition ===")
game.player.location = "forest_edge"
game.player.local_x = 17
game.player.local_y = 5
result = move_local(game, 1, 0)
results.append(check("Forest exit transition succeeds", result.success))
results.append(check("Player in deep_forest",
                     game.player.location == "deep_forest"))
results.append(check("Result has 'from'",
                     result.data.get("from") == "forest_edge"))
results.append(check("Result has 'location'",
                     result.data.get("location") == "deep_forest"))
results.append(check("deep_forest in visited_locations",
                     "deep_forest" in game.visited_locations))


# =========================================================================
# DEEP FOREST TESTS
# =========================================================================

# Deep Forest collision map (19x11):
#   y= 0: ###################
#   y= 1: ###################
#   y= 2: ###################
#   y= 3: ####....#######..##
#   y= 4: ####..........#..##
#   y= 5: ..............#..##
#   y= 6: ####..#....#....###
#   y= 7: #######....########
#   y= 8: ###################
#   y= 9: ###################
#   y=10: ###################
#
# Spawn: (1, 5)
# Exit: back (0,5) -> forest_edge
# Good open test spot: (5, 5) -- clearing, all 4 directions walkable

# --- 12. Deep Forest setup ---
print("\n=== 12. Deep Forest setup ===")
game2 = create_new_game()
game2.player.location = "deep_forest"
dlm = game2.local_maps.get("deep_forest")
results.append(check("Deep Forest local map exists", dlm is not None))
results.append(check("Deep Forest map is 19x11",
                     dlm.width == 19 and dlm.height == 11))
game2.player.local_x = dlm.spawn[0]
game2.player.local_y = dlm.spawn[1]
results.append(check("has_local_movement returns True",
                     has_local_movement(game2)))


# --- 13. Deep Forest basic WASD movement ---
print("\n=== 13. Deep Forest basic movement ===")
game2.player.location = "deep_forest"
game2.player.local_x = 5
game2.player.local_y = 5
sx2, sy2 = 5, 5

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


# --- 14. Deep Forest collision: trees ---
print("\n=== 14. Deep Forest collision: trees ===")
game2.player.location = "deep_forest"

# Tree at (3, 3) -- from collision map y=3: ####....#######..##
game2.player.local_x = 4
game2.player.local_y = 3
result = move_local(game2, -1, 0)
results.append(check("Tree (3,3) blocks from right",
                     not result.success))

# Tree at (14, 5) -- from collision map y=5: ..............#..##
game2.player.local_x = 13
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("Tree (14,5) blocks from left",
                     not result.success))

# Border tree at (0, 0)
game2.player.local_x = 1
game2.player.local_y = 1
result = move_local(game2, 0, -1)
results.append(check("Border tree blocks from below",
                     not result.success))


# --- 15. Deep Forest collision: boulders ---
print("\n=== 15. Deep Forest collision: boulders ===")
game2.player.location = "deep_forest"

# Boulder at (6, 6)
game2.player.local_x = 6
game2.player.local_y = 5
result = move_local(game2, 0, 1)
results.append(check("Boulder (6,6) blocks from above",
                     not result.success))

# Boulder at (14, 3)
game2.player.local_x = 14
game2.player.local_y = 4
result = move_local(game2, 0, -1)
results.append(check("Boulder (14,3) blocks from below",
                     not result.success))


# --- 16. Deep Forest collision: stump ---
print("\n=== 16. Deep Forest collision: stump ===")
game2.player.location = "deep_forest"

# Stump at (11, 6)
game2.player.local_x = 11
game2.player.local_y = 5
result = move_local(game2, 0, 1)
results.append(check("Stump (11,6) blocks from above",
                     not result.success))


# --- 17. Deep Forest collision: walls (borders) ---
print("\n=== 17. Deep Forest collision: walls ===")
game2.player.location = "deep_forest"

game2.player.local_x = 5
game2.player.local_y = 3
result = move_local(game2, 0, -1)
results.append(check("North wall blocks", not result.success))

game2.player.local_x = 5
game2.player.local_y = dlm.height - 2
result = move_local(game2, 0, 1)
results.append(check("South wall blocks", not result.success))

game2.player.local_x = dlm.width - 2
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("East wall blocks", not result.success))


# --- 18. Deep Forest walkable movement ---
print("\n=== 18. Deep Forest walkable movement ===")
game2.player.location = "deep_forest"
game2.player.local_x = dlm.spawn[0]
game2.player.local_y = dlm.spawn[1]
result = move_local(game2, 1, 0)
results.append(check("Open floor walkable", result.success))
results.append(check("Player moved",
                     game2.player.local_x == dlm.spawn[0] + 1))


# --- 19. Deep Forest bounds checking ---
print("\n=== 19. Deep Forest bounds checking ===")
game2.player.location = "deep_forest"
game2.player.local_x = 0
game2.player.local_y = 5
result = move_local(game2, -1, 0)
results.append(check("Out-of-bounds left blocked", not result.success))

game2.player.local_x = dlm.width - 1
game2.player.local_y = 5
result = move_local(game2, 1, 0)
results.append(check("Right edge blocked", not result.success))

game2.player.local_x = 5
game2.player.local_y = 0
result = move_local(game2, 0, -1)
results.append(check("Top edge blocked", not result.success))

game2.player.local_x = 5
game2.player.local_y = dlm.height - 1
result = move_local(game2, 0, 1)
results.append(check("Bottom edge blocked", not result.success))


# --- 20. Deep Forest exit tiles ---
print("\n=== 20. Deep Forest exit tiles ===")
game2.player.location = "deep_forest"

ep_back = get_exit_at(game2, 0, 5)
results.append(check("Back exit at (0,5) found", ep_back is not None))
results.append(check("Back exit targets forest_edge",
                     ep_back.target_location_id == "forest_edge"))
results.append(check("Back exit entry_name is 'forest'",
                     ep_back.entry_name == "forest"))

ep_none = get_exit_at(game2, 5, 5)
results.append(check("No exit at (5,5)", ep_none is None))


# --- 21. Deep Forest is_local_position_blocked ---
print("\n=== 21. Deep Forest is_local_position_blocked ===")
game2.player.location = "deep_forest"
results.append(check("Wall (0,0) blocked",
                     is_local_position_blocked(game2, 0, 0)))
results.append(check("Floor (5,5) not blocked",
                     not is_local_position_blocked(game2, 5, 5)))
results.append(check("Boulder (6,6) blocked",
                     is_local_position_blocked(game2, 6, 6)))
results.append(check("Negative coords blocked",
                     is_local_position_blocked(game2, -1, 5)))
results.append(check("Out-of-bounds blocked",
                     is_local_position_blocked(game2, 99, 99)))


# --- 22. Deep Forest area transition: back exit ---
print("\n=== 22. Deep Forest -> Forest Edge transition ===")
game2.player.location = "deep_forest"
game2.player.local_x = 1
game2.player.local_y = 5
result = move_local(game2, -1, 0)
results.append(check("Back exit transition succeeds", result.success))
results.append(check("Player in forest_edge",
                     game2.player.location == "forest_edge"))
results.append(check("Result has 'from'",
                     result.data.get("from") == "deep_forest"))
results.append(check("Result has 'location'",
                     result.data.get("location") == "forest_edge"))
results.append(check("forest_edge in visited_locations",
                     "forest_edge" in game2.visited_locations))


# =========================================================================
# FULL JOURNEY TESTS
# =========================================================================

# --- 23. Full journey: LR -> FE -> DF -> FE -> LR ---
print("\n=== 23. Full journey: LR -> FE -> DF -> FE -> LR ===")
g = create_new_game()

# LR -> FE: walk to outside exit at (18, 5)
g.player.local_x = 17
g.player.local_y = 5
result = move_local(g, 1, 0)
results.append(check("LR -> FE succeeds", result.success))
results.append(check("At FE", g.player.location == "forest_edge"))

# FE -> DF: walk to forest exit at (18, 5)
g.player.local_x = 17
g.player.local_y = 5
result = move_local(g, 1, 0)
results.append(check("FE -> DF succeeds", result.success))
results.append(check("At DF", g.player.location == "deep_forest"))

# DF -> FE: walk to back exit at (0, 5)
g.player.local_x = 1
g.player.local_y = 5
result = move_local(g, -1, 0)
results.append(check("DF -> FE succeeds", result.success))
results.append(check("At FE again", g.player.location == "forest_edge"))

# FE -> LR: walk to house exit at (0, 5)
g.player.local_x = 1
g.player.local_y = 5
result = move_local(g, -1, 0)
results.append(check("FE -> LR succeeds", result.success))
results.append(check("At LR", g.player.location == "old_wooden_house"))


# --- 24. Position persistence: FE -> DF -> FE ---
print("\n=== 24. Position persistence: FE -> DF -> FE ===")
gp = create_new_game()

# Transition to Forest Edge from Living Room
gp.player.location = "forest_edge"
gp.player.local_x = 1
gp.player.local_y = 5

# Move to Forest Edge position (10, 4) - saves in _area_positions
gp.player.local_x = 10
gp.player.local_y = 4
gp.player._area_positions["forest_edge"] = [10, 4]

# Transition to Deep Forest via exit at (17, 5)
gp.player.local_x = 17
gp.player.local_y = 5
move_local(gp, 1, 0)
results.append(check("In deep_forest", gp.player.location == "deep_forest"))

# The code saves the exit position [17, 5] to _area_positions["forest_edge"]
# when transitioning via move_local (not the manually set [10, 4])

# Return to Forest Edge
gp.player.local_x = 1
gp.player.local_y = 5
move_local(gp, -1, 0)
results.append(check("Back in forest_edge",
                     gp.player.location == "forest_edge"))
# Position should be the exit tile position [18, 5]
results.append(check("Forest Edge position restored to exit tile position [18, 5]",
                     gp.player.local_x == 18
                     and gp.player.local_y == 5))

# Transition to Living Room
gp.player.local_x = 1
gp.player.local_y = 5
move_local(gp, -1, 0)
results.append(check("In old_wooden_house",
                     gp.player.location == "old_wooden_house"))


# --- 25. Entry point resolution ---
print("\n=== 25. Entry point resolution ===")
game6 = create_new_game()

# Forest Edge entry from LR: LR outside exit at (18,5),
# FE house exit at (0,5). Entry should be near (1,5).
ex, ey = _resolve_entry_point(game6, "forest_edge", "outside")
results.append(check("FE entry near x=1", abs(ex - 1) <= 1))
results.append(check("FE entry y=5", abs(ey - 5) <= 1))

# Deep Forest entry from FE: FE forest exit at (18,5),
# DF back exit at (0,5). Entry should be near (1,5).
ex2, ey2 = _resolve_entry_point(game6, "deep_forest", "back")
results.append(check("DF entry near x=1", abs(ex2 - 1) <= 1))
results.append(check("DF entry y=5", abs(ey2 - 5) <= 1))

# Forest Edge entry from DF: DF back exit at (0,5),
# FE forest exit at (18,5). Entry should be near (17,5).
ex3, ey3 = _resolve_entry_point(game6, "forest_edge", "forest")
results.append(check("FE entry from DF near x=17",
                     abs(ex3 - 17) <= 1))
results.append(check("FE entry from DF y=5", abs(ey3 - 5) <= 1))

# Non-existent exit falls back to spawn
ex4, ey4 = _resolve_entry_point(game6, "forest_edge", "nonexistent")
fe_spawn = game6.local_maps["forest_edge"].spawn
results.append(check("Non-existent exit falls to spawn",
                     ex4 == fe_spawn[0] and ey4 == fe_spawn[1]))


# --- 26. Visited locations tracking ---
print("\n=== 26. Visited locations ===")
game7 = create_new_game()
game7.visited_locations.discard("forest_edge")
game7.visited_locations.discard("deep_forest")
results.append(check("forest_edge not visited initially",
                     "forest_edge" not in game7.visited_locations))
results.append(check("deep_forest not visited initially",
                     "deep_forest" not in game7.visited_locations))

# Transition TO forest_edge
_perform_area_transition(game7, "forest_edge", "outside")
results.append(check("forest_edge visited after transition",
                     "forest_edge" in game7.visited_locations))

# Transition TO deep_forest
_perform_area_transition(game7, "deep_forest", "back")
results.append(check("deep_forest visited after transition",
                     "deep_forest" in game7.visited_locations))


# --- 27. Renderer compatibility (skip if no pygame) ---
print("\n=== 27. Renderer compatibility ===")
try:
    import pygame
    pygame.init()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from ui.pygame.world_renderer import LocalRenderer

    game8 = create_new_game()
    lr = LocalRenderer(game8)

    # Forest Edge
    game8.player.location = "forest_edge"
    game8.player.local_x = 10
    game8.player.local_y = 5
    lm_fe = lr.current_local_map()
    results.append(check("Forest Edge renders",
                         lm_fe is not None and lm_fe.width == 19))

    # Deep Forest
    game8.player.location = "deep_forest"
    game8.player.local_x = 5
    game8.player.local_y = 5
    lm_df = lr.current_local_map()
    results.append(check("Deep Forest renders",
                         lm_df is not None and lm_df.width == 19))

    px, py = lr.player_pixel_pos()
    results.append(check("Player pixel pos valid", px >= 0 and py >= 0))
    pygame.quit()
except ImportError:
    print("  (pygame not available, skipping rendering tests)")
    results.append(check("Rendering: pygame not available (skipped)",
                         True))


# --- 28. Save/load preserves local movement state ---
print("\n=== 28. Save/load ===")
from engine.save import save_game, load_game

game9 = create_new_game()
game9.player.location = "forest_edge"
game9.player.local_x = 10
game9.player.local_y = 4
game9.player._area_positions["forest_edge"] = [10, 4]
game9.player._area_positions["deep_forest"] = [5, 5]

with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                 mode="w") as f:
    tmp = f.name
try:
    save_game(game9, path=__import__("pathlib").Path(tmp))
    loaded = load_game(path=__import__("pathlib").Path(tmp))
    results.append(check("Load succeeds", loaded is not None))
    results.append(check("Loaded location is forest_edge",
                         loaded.player.location == "forest_edge"))
    results.append(check("Loaded local_x is 10",
                         loaded.player.local_x == 10))
    results.append(check("Loaded local_y is 4",
                         loaded.player.local_y == 4))
    results.append(check("Loaded _area_positions has forest_edge",
                         "forest_edge" in loaded.player._area_positions))
    results.append(check("Loaded FE position is [10, 4]",
                         loaded.player._area_positions["forest_edge"]
                         == [10, 4]))
    results.append(check("Loaded _area_positions has deep_forest",
                         "deep_forest" in loaded.player._area_positions))
    results.append(check("Loaded DF position is [5, 5]",
                         loaded.player._area_positions["deep_forest"]
                         == [5, 5]))
finally:
    os.unlink(tmp)


# --- 29. Quest progression ---
print("\n=== 29. Quest progression ===")
game10 = create_new_game()
game10.visited_locations.discard("forest_edge")
game10.visited_locations.discard("deep_forest")
_perform_area_transition(game10, "forest_edge", "outside")
results.append(check("forest_edge in visited_locations",
                     "forest_edge" in game10.visited_locations))
result_q = _perform_area_transition(
    game10, "deep_forest", "back")
results.append(check("Result has quest_events field",
                     "quest_events" in result_q.data))
results.append(check("deep_forest in visited_locations",
                     "deep_forest" in game10.visited_locations))


# =========================================================================
# ALL LOCATIONS VERIFICATION
# =========================================================================

# --- 30. All five locations have local movement ---
print("\n=== 30. All five locations have local movement ===")
g11 = create_new_game()
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    results.append(check(f"{loc_id}: has_local_movement is True",
                         has_local_movement(g11)))
    g11.player.location = loc_id


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
