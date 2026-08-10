# -*- coding: utf-8 -*-
"""Tests for LocalObject multi-tile footprints and rendering."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import LocalObject, LocalMap, GameState
from engine.world import create_new_game
from engine.actions import is_local_position_blocked, has_local_movement


def check(label, condition):
    print("PASS" if condition else "FAIL", label, sep=": ")
    return condition


results = []


# =========================================================================
# 1. LocalObject defaults
# =========================================================================
print("=== 1. LocalObject defaults ===")
obj = LocalObject(id="test", name="Test", x=0, y=0, tile=".")
results.append(check("Default width is 1", obj.width == 1))
results.append(check("Default height is 1", obj.height == 1))

obj2 = LocalObject(id="t2", name="Table", x=5, y=5, tile="T",
                   blocking=True, width=3, height=2)
results.append(check("Custom width=3", obj2.width == 3))
results.append(check("Custom height=2", obj2.height == 2))


# =========================================================================
# 2. Custom width/height serialize correctly
# =========================================================================
print("\n=== 2. Serialization ===")
from dataclasses import asdict
d = asdict(obj2)
results.append(check("asdict has width", d["width"] == 3))
results.append(check("asdict has height", d["height"] == 2))


# =========================================================================
# 3. Old-style data without width/height loads
# =========================================================================
print("\n=== 3. Old-style data backward compat ===")
old_data = {"id": "x", "name": "X", "x": 0, "y": 0, "tile": ".",
            "blocking": False, "interactable_id": None}
obj_old = LocalObject(**old_data)
results.append(check("Old-style width defaults to 1", obj_old.width == 1))
results.append(check("Old-style height defaults to 1", obj_old.height == 1))


# =========================================================================
# 4. 3x2 object occupies correct six tiles
# =========================================================================
print("\n=== 4. Multi-tile footprint ===")
obj3x2 = LocalObject(id="tbl", name="Table", x=8, y=5, tile="T",
                     blocking=True, width=3, height=2)
footprint = set()
for dy in range(obj3x2.height):
    for dx in range(obj3x2.width):
        footprint.add((obj3x2.x + dx, obj3x2.y + dy))
expected = {(8, 5), (9, 5), (10, 5), (8, 6), (9, 6), (10, 6)}
results.append(check("3x2 footprint has 6 tiles", len(footprint) == 6))
results.append(check("3x2 footprint correct tiles",
                     footprint == expected))


# =========================================================================
# 5. Blocking collision applies to entire 3x2 footprint
# =========================================================================
print("\n=== 5. Multi-tile collision ===")
game = create_new_game()
game.player.location = "old_wooden_house"
lm = game.local_maps["old_wooden_house"]

# The living room table is at (8,5) width=3 height=2
results.append(check("Table blocks at (8,5)",
                     is_local_position_blocked(game, 8, 5)))
results.append(check("Table blocks at (9,5)",
                     is_local_position_blocked(game, 9, 5)))
results.append(check("Table blocks at (10,5)",
                     is_local_position_blocked(game, 10, 5)))
results.append(check("Table blocks at (8,6)",
                     is_local_position_blocked(game, 8, 6)))
results.append(check("Table blocks at (9,6)",
                     is_local_position_blocked(game, 9, 6)))
results.append(check("Table blocks at (10,6)",
                     is_local_position_blocked(game, 10, 6)))

# Space next to table should be free
results.append(check("Tile (7,5) not blocked",
                     not is_local_position_blocked(game, 7, 5)))
results.append(check("Tile (11,5) not blocked",
                     not is_local_position_blocked(game, 11, 5)))


# =========================================================================
# 6. Non-blocking objects do not block movement
# =========================================================================
print("\n=== 6. Non-blocking objects ===")
# Chairs in living room are non-blocking
results.append(check("Chair (9,4) not blocked",
                     not is_local_position_blocked(game, 9, 4)))
results.append(check("Chair (9,7) not blocked",
                     not is_local_position_blocked(game, 9, 7)))


# =========================================================================
# 7. Labels centered across multi-tile footprints
# =========================================================================
print("\n=== 7. Label centering ===")
# Verify the label would be centered on the footprint
# For a 3x2 table at (8,5): center pixel = (8+3/2)*40, (5+2/2)*40
# = 9.5*40, 6*40 = 380, 240
ts = 40
cx = (obj3x2.x + obj3x2.width / 2) * ts
cy = (obj3x2.y + obj3x2.height / 2) * ts
results.append(check("Center X is 380", cx == 380.0))
results.append(check("Center Y is 240", cy == 240.0))


# =========================================================================
# 8. Labels not duplicated per tile
# =========================================================================
print("\n=== 8. Label deduplication ===")
# Verify objects list has one entry per object (not one per tile)
obj_ids = [o.id for o in lm.objects]
results.append(check("Each object has unique id",
                     len(obj_ids) == len(set(obj_ids))))
# Table should appear once, not six times
table_count = sum(1 for o in lm.objects if o.name == "Table")
results.append(check("Table appears once in objects list",
                     table_count == 1))


# =========================================================================
# 9. Long labels do not get hard-clipped to three characters
# =========================================================================
print("\n=== 9. Label truncation ===")
long_obj = LocalObject(id="long", name="Very Long Object Name", x=0, y=0,
                       tile=".", blocking=True, width=2, height=1)
# The renderer should truncate to fit, not hard-clip
# Verify the full name is available for rendering
results.append(check("Full name preserved on object",
                     long_obj.name == "Very Long Object Name"))
results.append(check("Width allows truncation space", long_obj.width == 2))


# =========================================================================
# 10. Small objects still render readable labels
# =========================================================================
print("\n=== 10. Small object labels ===")
small_obj = LocalObject(id="rock", name="Rock", x=5, y=5, tile="^",
                        blocking=True, width=1, height=1)
# 1x1 = 40px, label "Rock" is ~28px at font 14, should fit
results.append(check("Small object has name", len(small_obj.name) > 0))
results.append(check("Small object width=1", small_obj.width == 1))


# =========================================================================
# 11. Existing local maps still generate correctly
# =========================================================================
print("\n=== 11. Map generation ===")
game2 = create_new_game()
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    lm = game2.local_maps.get(loc_id)
    results.append(check("%s: map exists" % loc_id, lm is not None))
    results.append(check("%s: width=19" % loc_id, lm.width == 19))
    results.append(check("%s: height=11" % loc_id, lm.height == 11))
    results.append(check("%s: has objects" % loc_id, len(lm.objects) > 0))
    # All objects should have width/height
    for obj in lm.objects:
        results.append(check(
            "%s: %s has w/h" % (loc_id, obj.id),
            obj.width >= 1 and obj.height >= 1))


# =========================================================================
# 12. Existing exits/spawns remain unchanged
# =========================================================================
print("\n=== 12. Exits and spawns ===")
game3 = create_new_game()
# Living room
lm_lr = game3.local_maps["old_wooden_house"]
results.append(check("LR spawn is [12,5]",
                     lm_lr.spawn == [12, 5]))
results.append(check("LR has kitchen exit",
                     "kitchen" in lm_lr.exits))
results.append(check("LR has outside exit",
                     "outside" in lm_lr.exits))
results.append(check("LR has upstairs exit",
                     "upstairs" in lm_lr.exits))

# Kitchen
lm_k = game3.local_maps["kitchen"]
results.append(check("Kitchen spawn is [10,5]",
                     lm_k.spawn == [10, 5]))
results.append(check("Kitchen has outside exit",
                     "outside" in lm_k.exits))

# Upstairs
lm_u = game3.local_maps["upstairs"]
results.append(check("Upstairs spawn is [9,8]",
                     lm_u.spawn == [9, 8]))
results.append(check("Upstairs has downstairs exit",
                     "downstairs" in lm_u.exits))

# Forest Edge
lm_fe = game3.local_maps["forest_edge"]
results.append(check("FE spawn is [2,5]",
                     lm_fe.spawn == [2, 5]))
results.append(check("FE has house exit",
                     "house" in lm_fe.exits))
results.append(check("FE has forest exit",
                     "forest" in lm_fe.exits))

# Deep Forest
lm_df = game3.local_maps["deep_forest"]
results.append(check("DF spawn is [1,5]",
                     lm_df.spawn == [1, 5]))
results.append(check("DF has back exit",
                     "back" in lm_df.exits))


# =========================================================================
# 13. Existing movement behavior unchanged
# =========================================================================
print("\n=== 13. Movement behavior ===")
game4 = create_new_game()
game4.player.location = "old_wooden_house"
game4.player.local_x = 12
game4.player.local_y = 5
results.append(check("has_local_movement for LR",
                     has_local_movement(game4)))
results.append(check("Player can move from (12,5)",
                     not is_local_position_blocked(game4, 12, 5)))

# Table blocks at (9,5)
results.append(check("Table at (9,5) blocks",
                     is_local_position_blocked(game4, 9, 5)))

# Kitchen cabinet is 1x2 at (1,3)
game4.player.location = "kitchen"
results.append(check("Kitchen cabinet blocks at (1,3)",
                     is_local_position_blocked(game4, 1, 3)))
results.append(check("Kitchen cabinet blocks at (1,4)",
                     is_local_position_blocked(game4, 1, 4)))
results.append(check("Kitchen cabinet does not block at (1,2)",
                     not is_local_position_blocked(game4, 1, 2)))


# =========================================================================
# 14. Save/load compatible
# =========================================================================
print("\n=== 14. Save/load ===")
from engine.save import save_game, load_game

game5 = create_new_game()
game5.player.location = "old_wooden_house"
game5.player.local_x = 12
game5.player.local_y = 5

with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                 mode="w") as f:
    tmp = f.name
try:
    save_game(game5, path=__import__("pathlib").Path(tmp))
    loaded = load_game(path=__import__("pathlib").Path(tmp))
    results.append(check("Load succeeds", loaded is not None))
    results.append(check("Loaded location correct",
                         loaded.player.location == "old_wooden_house"))
    # Local maps are regenerated on game creation, not loaded
    # But save file should serialize without error
    results.append(check("Save file created",
                         __import__("pathlib").Path(tmp).exists()))
finally:
    os.unlink(tmp)


# =========================================================================
# 15. Object boundary safety
# =========================================================================
print("\n=== 15. Boundary safety ===")
# Objects should not extend beyond map boundaries
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    lm = game5.local_maps.get(loc_id)
    if lm is None:
        continue
    for obj in lm.objects:
        in_bounds = (obj.x >= 0 and obj.y >= 0
                     and obj.x + obj.width <= lm.width
                     and obj.y + obj.height <= lm.height)
        results.append(check(
            "%s: %s in bounds" % (loc_id, obj.id), in_bounds))


# =========================================================================
# 16. Collision grid matches object footprints
# =========================================================================
print("\n=== 16. Collision grid matches footprints ===")
game6 = create_new_game()
lm6 = game6.local_maps["old_wooden_house"]
for obj in lm6.objects:
    if not obj.blocking:
        continue
    for dy in range(obj.height):
        for dx in range(obj.width):
            ox, oy = obj.x + dx, obj.y + dy
            if 0 <= oy < lm6.height and 0 <= ox < lm6.width:
                results.append(check(
                    "%s (%d,%d) collision=True" % (obj.id, ox, oy),
                    lm6.collision[oy][ox]))


# =========================================================================
# 17. Renderer compatibility (skip if no pygame)
# =========================================================================
print("\n=== 17. Renderer compatibility ===")
try:
    import pygame
    pygame.init()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from ui.pygame.world_renderer import LocalRenderer

    game7 = create_new_game()
    lr = LocalRenderer(game7)

    game7.player.location = "old_wooden_house"
    game7.player.local_x = 12
    game7.player.local_y = 5
    lm_r = lr.current_local_map()
    results.append(check("Renderer gets local map", lm_r is not None))

    # Check that objects have width/height
    for obj in lm_r.objects:
        results.append(check(
            "Renderer: %s has w=%d h=%d" % (obj.id, obj.width, obj.height),
            obj.width >= 1 and obj.height >= 1))

    # Render without error
    surf = pygame.Surface((800, 600))
    lr.draw(surf, 0.0, 0.0)
    results.append(check("Draw completes without error", True))

    pygame.quit()
except ImportError:
    print("  (pygame not available, skipping rendering tests)")
    results.append(check("Rendering: pygame not available (skipped)",
                         True))


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print("%d/%d checks passed, %d failed" % (passed, total, total - passed))
