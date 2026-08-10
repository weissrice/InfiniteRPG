"""Phase 8 tests -- NPC + Interactable Local Integration.

Covers:
  1. NPC placement in hand-authored local maps
  2. NPC bounds checking
  3. NPC non-blocking behavior
  4. NPC rendering setup
  5. Multiple NPCs
  6. Interactable placement
  7. Interactable bounds
  8. Interaction compatibility
  9. Area transitions
  10. Position persistence
  11. Save/load
  12. AI-generated locations
  13. AI-generated NPCs
  14. AI-generated interactables
  15. LocalMap validation with NPCs/interactables
  16. Full multi-location journey
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import (
    GameState, Player, World, Location, NPC, Interactable,
    LocalMap, LocalObject, ExitPoint, Weather,
)
from engine.world import create_new_game
from engine.local_map import (
    generate_local_map, validate_local_map,
    place_npcs_on_local_map, place_interactables_on_local_map,
    _place_npcs_and_interactables,
    MAP_WIDTH, MAP_HEIGHT,
)
from engine.actions import (
    move_local, has_local_movement, is_local_position_blocked,
    _find_npc, _find_interactable,
)
from engine.save import save_game, load_game
from pathlib import Path
import json
import tempfile

passed = 0
failed = 0

def check(condition, label):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {label}")


# ======================================================================
# 1. NPC placement in hand-authored local maps
# ======================================================================
print("1. NPC placement in hand-authored maps")

game = create_new_game()
npcs = game.world.npcs

old_man = npcs["old_man"]
check(old_man.local_x >= 0, "old_man local_x set")
check(old_man.local_y >= 0, "old_man local_y set")
check(old_man.location == "old_wooden_house", "old_man in house")

sarah = npcs["sarah"]
check(sarah.local_x >= 0, "sarah local_x set")
check(sarah.local_y >= 0, "sarah local_y set")
check(sarah.location == "old_wooden_house", "sarah in house")

merchant = npcs["merchant"]
check(merchant.local_x >= 0, "merchant local_x set")
check(merchant.local_y >= 0, "merchant local_y set")
check(merchant.location == "forest_edge", "merchant in forest_edge")

# ======================================================================
# 2. NPC bounds checking
# ======================================================================
print("2. NPC bounds checking")

for npc in npcs.values():
    lm = game.local_maps.get(npc.location)
    check(lm is not None, f"NPC {npc.id} has local map")
    if lm:
        check(0 <= npc.local_x < lm.width, f"NPC {npc.id} local_x in bounds")
        check(0 <= npc.local_y < lm.height, f"NPC {npc.id} local_y in bounds")

# ======================================================================
# 3. NPC non-blocking behavior
# ======================================================================
print("3. NPC non-blocking behavior")

for npc in npcs.values():
    check(not is_local_position_blocked(game, npc.local_x, npc.local_y),
          f"{npc.id} position not blocked for player movement")

# ======================================================================
# 4. NPC rendering setup (positions valid for renderer)
# ======================================================================
print("4. NPC rendering setup")

for npc in npcs.values():
    check(npc.local_x >= 0 and npc.local_y >= 0,
          f"NPC {npc.id} has valid render position")
    lm = game.local_maps.get(npc.location)
    if lm:
        check(lm.terrain[npc.local_y][npc.local_x] != "#",
              f"NPC {npc.id} not on wall terrain")

# ======================================================================
# 5. Multiple NPCs in the same location
# ======================================================================
print("5. Multiple NPCs in same location")

check(old_man.local_x != sarah.local_x or old_man.local_y != sarah.local_y,
      "old_man and sarah are at different positions")

# ======================================================================
# 6. Interactable placement
# ======================================================================
print("6. Interactable placement")

interactables = game.world.interactables

door = interactables["locked_upstairs_door"]
check(door.local_x >= 0, "locked_upstairs_door local_x set")
check(door.local_y >= 0, "locked_upstairs_door local_y set")

stew = interactables["kitchen_stew_pot"]
check(stew.local_x >= 0, "kitchen_stew_pot local_x set")
check(stew.local_y >= 0, "kitchen_stew_pot local_y set")

# ======================================================================
# 7. Interactable bounds
# ======================================================================
print("7. Interactable bounds")

for inter in interactables.values():
    lm = game.local_maps.get(inter.location)
    check(lm is not None, f"Interactable {inter.id} has local map")
    if lm:
        check(0 <= inter.local_x < lm.width,
              f"Interactable {inter.id} local_x in bounds")
        check(0 <= inter.local_y < lm.height,
              f"Interactable {inter.id} local_y in bounds")

# ======================================================================
# 8. Interaction compatibility
# ======================================================================
print("8. Interaction compatibility")

# Move player to kitchen to find stew pot
game.player.location = "kitchen"
found_stew = _find_interactable(game, "stew")
check(found_stew is not None, "_find_interactable finds stew pot from kitchen")

# Move player to old_wooden_house to find old_man
game.player.location = "old_wooden_house"
found_old_man = _find_npc(game, "Old Man")
check(found_old_man is not None, "_find_npc finds Old Man from house")

found_sarah = _find_npc(game, "sarah")
check(found_sarah is not None, "_find_npc finds Sarah from house")

# Move to upstairs for door
game.player.location = "upstairs"
found_door = _find_interactable(game, "Locked Upstairs Door")
check(found_door is not None, "_find_interactable finds locked door from upstairs")

# Verify that interaction does NOT require local position
check(found_old_man.local_x >= 0 if found_old_man else False,
      "old_man has local_x accessible from interaction")

# ======================================================================
# 9. Area transitions -- NPC positions persist
# ======================================================================
print("9. Area transitions -- NPC positions persist")

game.player.location = "old_wooden_house"
game.player.local_x = 1  # one tile to the right of kitchen exit (0,5)
game.player.local_y = 5
check(has_local_movement(game), "house has local movement")

old_man_x, old_man_y = old_man.local_x, old_man.local_y

# Move left onto exit tile (0,5) -> triggers transition to kitchen
r = move_local(game, -1, 0)
check(r.success, "moved to kitchen via exit")
check(game.player.location == "kitchen", "player in kitchen after transition")

# old_man position should be unchanged
check(old_man.local_x == old_man_x and old_man.local_y == old_man_y,
      "old_man position unchanged after player area transition")

# Move back: place player near the house exit (18,5)
game.player.local_x = 17  # one tile to the left of exit
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "moved back to house via exit")
check(game.player.location == "old_wooden_house",
      "player back in old_wooden_house")

# ======================================================================
# 10. Position persistence (_area_positions)
# ======================================================================
print("10. Position persistence via _area_positions")

game.player.location = "old_wooden_house"
game.player.local_x = 5
game.player.local_y = 5
game.player._area_positions["old_wooden_house"] = [5, 5]

# Move away
game.player.location = "kitchen"
game.player.local_x = 10
game.player.local_y = 5

# Simulate re-entry
saved = game.player._area_positions.get("old_wooden_house")
check(saved is not None, "saved position exists")
if saved:
    game.player.location = "old_wooden_house"
    game.player.local_x = saved[0]
    game.player.local_y = saved[1]
    check(game.player.local_x == 5, "restored x")
    check(game.player.local_y == 5, "restored y")

# ======================================================================
# 11. Save/load preserves NPC local positions
# ======================================================================
print("11. Save/load")

game.player.location = "old_wooden_house"
game.player.local_x = 12
game.player.local_y = 5

tmp = Path(tempfile.mktemp(suffix=".json"))
try:
    save_game(game, tmp)
    loaded = load_game(tmp)

    loaded_old_man = loaded.world.npcs.get("old_man")
    check(loaded_old_man is not None, "loaded old_man exists")
    if loaded_old_man:
        check(loaded_old_man.local_x == old_man.local_x,
              "old_man local_x preserved after save/load")
        check(loaded_old_man.local_y == old_man.local_y,
              "old_man local_y preserved after save/load")

    loaded_sarah = loaded.world.npcs.get("sarah")
    check(loaded_sarah is not None, "loaded sarah exists")
    if loaded_sarah:
        check(loaded_sarah.local_x == sarah.local_x,
              "sarah local_x preserved after save/load")

    loaded_merchant = loaded.world.npcs.get("merchant")
    check(loaded_merchant is not None, "loaded merchant exists")
    if loaded_merchant:
        check(loaded_merchant.local_x == merchant.local_x,
              "merchant local_x preserved after save/load")

    loaded_door = loaded.world.interactables.get("locked_upstairs_door")
    check(loaded_door is not None, "loaded door exists")
    if loaded_door:
        check(loaded_door.local_x == door.local_x,
              "door local_x preserved")
        check(loaded_door.local_y == door.local_y,
              "door local_y preserved")

    loaded_stew = loaded.world.interactables.get("kitchen_stew_pot")
    check(loaded_stew is not None, "loaded stew exists")
    if loaded_stew:
        check(loaded_stew.local_x == stew.local_x,
              "stew local_x preserved")
        check(loaded_stew.local_y == stew.local_y,
              "stew local_y preserved")
finally:
    if tmp.exists():
        tmp.unlink()

# ======================================================================
# 12. AI-generated location receives LocalMap
# ======================================================================
print("12. AI-generated location")

ai_loc = Location(
    id="test_tavern",
    name="Test Tavern",
    description="A test tavern.",
    exits={"forest_edge": "forest_edge"},
    visual_type="interior",
)
game.world.locations["test_tavern"] = ai_loc

ai_lm = generate_local_map(ai_loc)
check(ai_lm.width == MAP_WIDTH, "AI map width")
check(ai_lm.height == MAP_HEIGHT, "AI map height")
check(validate_local_map(ai_lm), "AI map validates")

# ======================================================================
# 13. AI-generated NPCs get placed
# ======================================================================
print("13. AI-generated NPCs")

ai_npc = NPC(
    id="test_barkeep",
    name="Test Barkeep",
    location="test_tavern",
    description="A test barkeep.",
)
game.world.npcs["test_barkeep"] = ai_npc
ai_loc.npcs = ["test_barkeep"]

ai_lm = generate_local_map(ai_loc)
_place_npcs_and_interactables(
    ai_lm, ai_loc, game.world.npcs, game.world.interactables,
)
check(ai_npc.local_x >= 0, "AI NPC local_x set")
check(ai_npc.local_y >= 0, "AI NPC local_y set")
check(0 <= ai_npc.local_x < ai_lm.width, "AI NPC local_x in bounds")
check(0 <= ai_npc.local_y < ai_lm.height, "AI NPC local_y in bounds")
check(not ai_lm.collision[ai_npc.local_y][ai_npc.local_x],
      "AI NPC not on collision tile")

# ======================================================================
# 14. AI-generated interactables get placed
# ======================================================================
print("14. AI-generated interactables")

ai_inter = Interactable(
    id="test_sign",
    name="Test Sign",
    description="A test sign.",
    location="test_tavern",
)
game.world.interactables["test_sign"] = ai_inter
ai_loc.interactables = ["test_sign"]

ai_lm2 = generate_local_map(ai_loc)
_place_npcs_and_interactables(
    ai_lm2, ai_loc, game.world.npcs, game.world.interactables,
)
check(ai_inter.local_x >= 0, "AI interactable local_x set")
check(ai_inter.local_y >= 0, "AI interactable local_y set")
check(0 <= ai_inter.local_x < ai_lm2.width, "AI interactable local_x in bounds")
check(0 <= ai_inter.local_y < ai_lm2.height, "AI interactable local_y in bounds")

# ======================================================================
# 15. Validation with NPCs/interactables
# ======================================================================
print("15. Validation with NPCs/interactables")

valid_npc = NPC(id="v1", name="V1", location="test", local_x=3, local_y=3)
check(validate_local_map(ai_lm, [valid_npc]), "valid map + valid NPC passes")

bad_npc = NPC(id="b1", name="B1", location="test", local_x=99, local_y=99)
check(not validate_local_map(ai_lm, [bad_npc]), "NPC out of bounds fails")

bad_npc2 = NPC(id="b2", name="B2", location="test", local_x=0, local_y=0)
check(not validate_local_map(ai_lm, [bad_npc2]), "NPC on wall fails")

overlap_a = NPC(id="oa", name="OA", location="t", local_x=5, local_y=5)
overlap_b = NPC(id="ob", name="OB", location="t", local_x=5, local_y=5)
check(not validate_local_map(ai_lm, [overlap_a, overlap_b]),
      "overlapping NPCs fail")

# Validate all hand-authored maps
for loc_id in ["old_wooden_house", "kitchen", "upstairs", "forest_edge", "deep_forest"]:
    lm = game.local_maps.get(loc_id)
    loc_npcs = [n for n in game.world.npcs.values() if n.location == loc_id]
    loc_inters = [i for i in game.world.interactables.values() if i.location == loc_id]
    if lm:
        check(validate_local_map(lm, loc_npcs, loc_inters),
              f"{loc_id} map validates with NPCs/interactables")

# ======================================================================
# 16. Full multi-location journey
# ======================================================================
print("16. Full multi-location journey")

game.player.location = "old_wooden_house"
game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "house -> kitchen")
check(game.player.location == "kitchen", "in kitchen")

game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "kitchen -> house")
check(game.player.location == "old_wooden_house", "back in house")

game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "house -> forest_edge")
check(game.player.location == "forest_edge", "at forest_edge")

found_m = _find_npc(game, "Merchant")
check(found_m is not None, "find merchant at forest_edge")

game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "forest_edge -> deep_forest")
check(game.player.location == "deep_forest", "in deep_forest")

game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "deep_forest -> forest_edge")

game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "forest_edge -> house")

# ======================================================================
# 17. Old saves without NPC local positions
# ======================================================================
print("17. Backward-compatible save/load")

game.player.location = "old_wooden_house"
game.player.local_x = 12
game.player.local_y = 5

tmp2 = Path(tempfile.mktemp(suffix=".json"))
try:
    save_game(game, tmp2)
    with tmp2.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for npc_data in data["world"]["npcs"].values():
        npc_data.pop("local_x", None)
        npc_data.pop("local_y", None)
    for inter_data in data["world"].get("interactables", {}).values():
        inter_data.pop("local_x", None)
        inter_data.pop("local_y", None)

    with tmp2.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    loaded_old = load_game(tmp2)
    check("old_man" in loaded_old.world.npcs, "old save loads old_man")
    check("sarah" in loaded_old.world.npcs, "old save loads sarah")
    loaded_om = loaded_old.world.npcs["old_man"]
    check(loaded_om.local_x == -1, "old save has default local_x=-1")
    check(loaded_om.local_y == -1, "old save has default local_y=-1")
finally:
    if tmp2.exists():
        tmp2.unlink()

# ======================================================================
# Results
# ======================================================================
total = passed + failed
print(f"\n=== Phase 8: {passed}/{total} checks passed, {failed} failed ===")
if failed > 0:
    sys.exit(1)
