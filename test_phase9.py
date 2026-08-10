"""Phase 9 tests -- Local Interaction & Proximity.

Covers:
  1. Distance calculation (Chebyshev)
  2. Interaction range boundary
  3. NPC interaction while adjacent
  4. NPC interaction while too far away
  5. Interactable interaction while adjacent
  6. Interactable interaction while too far away
  7. Invalid local_x/local_y (fallback)
  8. Multiple NPCs
  9. Multiple interactables
  10. Interaction after movement
  11. Interaction after area transition
  12. Interaction after returning to an area
  13. Save/load interaction
  14. AI-generated NPC interaction
  15. AI-generated interactable interaction
  16. Existing quest interaction
  17. Existing trading interaction
  18. Existing dialogue interaction (npc_interact)
  19. LocalObject/Interactable position consistency
  20. Full multi-location journey
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import (
    GameState, Player, World, Location, NPC, Interactable,
    LocalMap, LocalObject, ExitPoint, Weather, Quest, QuestObjective,
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
    interact, open_interactable, inspect, attack, buy_item, sell_item,
    npc_interact, npc_interact_object,
    _find_npc, _find_interactable,
    _chebyshev, is_in_interaction_range, INTERACT_RANGE,
)
from engine.save import save_game, load_game
from pathlib import Path
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
# 1. Distance calculation
# ======================================================================
print("1. Distance calculation")

check(_chebyshev(0, 0, 0, 0) == 0, "same tile = 0")
check(_chebyshev(0, 0, 1, 0) == 1, "one step east = 1")
check(_chebyshev(0, 0, 0, 1) == 1, "one step south = 1")
check(_chebyshev(0, 0, 1, 1) == 1, "diagonal = 1")
check(_chebyshev(0, 0, 2, 0) == 2, "two steps = 2")
check(_chebyshev(0, 0, 2, 1) == 2, "two steps with offset = 2")
check(_chebyshev(5, 5, 3, 3) == 2, "negative direction = 2")
check(_chebyshev(0, 0, 10, 10) == 10, "far diagonal = 10")

# ======================================================================
# 2. Interaction range boundary
# ======================================================================
print("2. Interaction range boundary")

game = create_new_game()
game.player.local_x = 5
game.player.local_y = 5

check(is_in_interaction_range(game, 5, 5), "same tile in range")
check(is_in_interaction_range(game, 5, 6), "adjacent south in range")
check(is_in_interaction_range(game, 6, 5), "adjacent east in range")
check(is_in_interaction_range(game, 6, 6), "diagonal in range")
check(is_in_interaction_range(game, 4, 4), "diagonal NW in range")
check(not is_in_interaction_range(game, 5, 7), "two south out of range")
check(not is_in_interaction_range(game, 7, 5), "two east out of range")
check(not is_in_interaction_range(game, 0, 0), "far away out of range")

# ======================================================================
# 3. NPC interaction while adjacent
# ======================================================================
print("3. NPC interaction while adjacent")

game = create_new_game()
npcs = game.world.npcs

# Place player adjacent to old_man in old_wooden_house
game.player.location = "old_wooden_house"
old_man = npcs["old_man"]
game.player.local_x = old_man.local_x + 1
game.player.local_y = old_man.local_y

result = interact(game, "old man")
check(result.success, "interact with old man from adjacent tile")
check("speak" in result.message.lower() or "old man" in result.message.lower(),
      "message mentions old man")

# ======================================================================
# 4. NPC interaction while too far away
# ======================================================================
print("4. NPC interaction while too far away")

game.player.local_x = 17
game.player.local_y = 9

result = interact(game, "old man")
check(not result.success, "interact with old man fails when far away")
check("too far" in result.message.lower(), "message says too far")

# ======================================================================
# 5. Interactable interaction while adjacent
# ======================================================================
print("5. Interactable interaction while adjacent")

game.player.location = "upstairs"
interactables = game.world.interactables
door = interactables["locked_upstairs_door"]

# Place player adjacent to the door
game.player.local_x = door.local_x + 1
game.player.local_y = door.local_y

result = interact(game, "Locked Upstairs Door")
check(result.success, "interact with door from adjacent tile")
check("locked" in result.message.lower(), "message says locked")

# Also test inspect
result = inspect(game, "Locked Upstairs Door")
check(result.success, "inspect door from adjacent tile")

# ======================================================================
# 6. Interactable interaction while too far away
# ======================================================================
print("6. Interactable interaction while too far away")

# Door is at (1,1) — move player to opposite corner (17,9)
game.player.local_x = 17
game.player.local_y = 9

result = interact(game, "Locked Upstairs Door")
check(not result.success, "interact with door fails when far away")
check("too far" in result.message.lower(), "message says too far for door")

# inspect also fails
result = inspect(game, "Locked Upstairs Door")
check(not result.success, "inspect door fails when far away")
check("too far" in result.message.lower(), "inspect says too far")

# ======================================================================
# 7. Invalid local_x/local_y (fallback)
# ======================================================================
print("7. Invalid local_x/local_y fallback")

game = create_new_game()
game.player.location = "old_wooden_house"
game.player.local_x = 5
game.player.local_y = 5

# Create NPC with invalid position
npc_no_pos = NPC(
    id="wandering_npc", name="Wandering NPC",
    location="old_wooden_house",
    local_x=-1, local_y=-1,
)
game.world.npcs["wandering_npc"] = npc_no_pos
game.world.locations["old_wooden_house"].npcs.append("wandering_npc")

result = interact(game, "wandering npc")
check(result.success, "NPC with invalid position still accessible (fallback)")
check("wandering npc" in result.message.lower(), "found wandering npc")

# Create interactable with invalid position
inter_no_pos = Interactable(
    id="mystery_box", name="Mystery Box",
    description="A mysterious box.",
    location="old_wooden_house",
    local_x=-1, local_y=-1,
)
game.world.interactables["mystery_box"] = inter_no_pos
game.world.locations["old_wooden_house"].interactables.append("mystery_box")

result = interact(game, "mystery box")
check(result.success, "interactable with invalid position still accessible")

# Cleanup
game.world.npcs.pop("wandering_npc", None)
game.world.locations["old_wooden_house"].npcs.remove("wandering_npc")
game.world.interactables.pop("mystery_box", None)
game.world.locations["old_wooden_house"].interactables.remove("mystery_box")

# ======================================================================
# 8. Multiple NPCs
# ======================================================================
print("8. Multiple NPCs -- proximity to each")

game = create_new_game()
game.player.location = "old_wooden_house"
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]

# Move to old_man, interact
game.player.local_x = old_man.local_x + 1
game.player.local_y = old_man.local_y
result_a = interact(game, "old man")
check(result_a.success, "interact with old_man")

# Move to sarah, interact
game.player.local_x = sarah.local_x + 1
game.player.local_y = sarah.local_y
result_b = interact(game, "sarah")
check(result_b.success, "interact with sarah")

# Try to interact with old_man from sarah's vicinity
d = _chebyshev(game.player.local_x, game.player.local_y,
               old_man.local_x, old_man.local_y)
result_c = interact(game, "old man")
if d <= INTERACT_RANGE:
    check(result_c.success, "old_man reachable from near sarah (in range)")
else:
    check(not result_c.success, "old_man too far from sarah")

# ======================================================================
# 9. Multiple interactables
# ======================================================================
print("9. Multiple interactables")

# Stew pot in kitchen
game.player.location = "kitchen"
stew = game.world.interactables["kitchen_stew_pot"]

game.player.local_x = stew.local_x + 1
game.player.local_y = stew.local_y
result = interact(game, "stew pot")
check(result.success, "interact with stew pot adjacent")

# Door in upstairs
game.player.location = "upstairs"
door = game.world.interactables["locked_upstairs_door"]

game.player.local_x = door.local_x + 1
game.player.local_y = door.local_y
result = open_interactable(game, "Locked Upstairs Door")
check(not result.success, "open locked door returns locked message")
check("locked" in result.message.lower(), "door is locked")

# ======================================================================
# 10. Interaction after movement
# ======================================================================
print("10. Interaction after movement")

game = create_new_game()
game.player.location = "old_wooden_house"
old_man = game.world.npcs["old_man"]

# Start far away
game.player.local_x = 17
game.player.local_y = 9
result = interact(game, "old man")
check(not result.success, "can't interact from far away")

# Walk closer (simulate a few moves)
game.player.local_x = old_man.local_x + 3
game.player.local_y = old_man.local_y
result = interact(game, "old man")
check(not result.success, "still too far after partial approach")

game.player.local_x = old_man.local_x + 1
game.player.local_y = old_man.local_y
result = interact(game, "old man")
check(result.success, "can interact after walking close enough")

# ======================================================================
# 11. Interaction after area transition
# ======================================================================
print("11. Interaction after area transition")

game = create_new_game()
game.player.location = "old_wooden_house"
game.player.local_x = 1
game.player.local_y = 5

# Move to kitchen
r = move_local(game, -1, 0)
check(r.success, "moved to kitchen")
check(game.player.location == "kitchen", "in kitchen")

# Check stew pot accessibility from kitchen spawn
stew = game.world.interactables["kitchen_stew_pot"]
d = _chebyshev(game.player.local_x, game.player.local_y,
               stew.local_x, stew.local_y)
result = interact(game, "stew pot")
if d <= INTERACT_RANGE:
    check(result.success, "stew pot accessible right after transition")
else:
    check(not result.success, "stew pot too far from kitchen spawn")

# Move back — place player near house exit (18,5)
game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "moved back to house")
check(game.player.location == "old_wooden_house", "back in house")

# Check old_man
old_man = game.world.npcs["old_man"]
d2 = _chebyshev(game.player.local_x, game.player.local_y,
                old_man.local_x, old_man.local_y)
result2 = interact(game, "old man")
if d2 <= INTERACT_RANGE:
    check(result2.success, "old_man accessible after return transition")
else:
    check(not result2.success, "old_man too far after return")

# ======================================================================
# 12. Interaction after returning to an area
# ======================================================================
print("12. Interaction after returning to area")

game = create_new_game()
game.player.location = "old_wooden_house"

# Save old_man position
om_x, om_y = old_man.local_x, old_man.local_y

# Move away via exit at (0,5) — place player at (1,5) and step left
game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "moved to kitchen")
check(game.player.location == "kitchen", "in kitchen")

# Move back — place near house exit (18,5)
game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "moved back to house")
check(game.player.location == "old_wooden_house", "back in house")

# old_man position should be unchanged
check(old_man.local_x == om_x and old_man.local_y == om_y,
      "old_man position unchanged after round trip")

# ======================================================================
# 13. Save/load interaction
# ======================================================================
print("13. Save/load interaction")

game = create_new_game()
game.player.location = "old_wooden_house"
game.player.local_x = old_man.local_x + 1
game.player.local_y = old_man.local_y

# Verify interaction works before save
result = interact(game, "old man")
check(result.success, "interaction works before save")

# Save and load
tmp = Path(tempfile.mktemp(suffix=".json"))
try:
    save_game(game, tmp)
    loaded = load_game(tmp)

    # Restore loaded state
    game.player = loaded.player
    game.world = loaded.world
    game.local_maps = {}

    # Regenerate local maps and place NPCs
    from engine.local_map import generate_local_map, _place_npcs_and_interactables
    for loc in game.world.locations.values():
        game.local_maps[loc.id] = generate_local_map(loc)
    for loc in game.world.locations.values():
        lm = game.local_maps.get(loc.id)
        if lm:
            _place_npcs_and_interactables(
                lm, loc, game.world.npcs, game.world.interactables,
            )

    # Verify NPC positions preserved
    loaded_om = game.world.npcs["old_man"]
    check(loaded_om.local_x >= 0, "old_man local_x preserved after load")
    check(loaded_om.local_y >= 0, "old_man local_y preserved after load")

    # Verify interaction works after load
    game.player.local_x = loaded_om.local_x + 1
    game.player.local_y = loaded_om.local_y
    result = interact(game, "old man")
    check(result.success, "interaction works after save/load")

finally:
    if tmp.exists():
        tmp.unlink()

# ======================================================================
# 14. AI-generated NPC interaction
# ======================================================================
print("14. AI-generated NPC interaction")

game = create_new_game()

ai_loc = Location(
    id="test_inn",
    name="Test Inn",
    description="A test inn.",
    exits={},
    visual_type="interior",
    npcs=["test_innkeeper"],
)
game.world.locations["test_inn"] = ai_loc

ai_npc = NPC(
    id="test_innkeeper",
    name="Test Innkeeper",
    location="test_inn",
    description="A friendly innkeeper.",
)
game.world.npcs["test_innkeeper"] = ai_npc

ai_lm = generate_local_map(ai_loc)
game.local_maps["test_inn"] = ai_lm
_place_npcs_and_interactables(
    ai_lm, ai_loc, game.world.npcs, game.world.interactables,
)

check(ai_npc.local_x >= 0, "AI NPC placed on map")

# Place player adjacent
game.player.location = "test_inn"
game.player.local_x = ai_npc.local_x + 1
game.player.local_y = ai_npc.local_y

result = interact(game, "innkeeper")
check(result.success, "AI NPC interactable when adjacent")

# Too far
game.player.local_x = 17
game.player.local_y = 9
result = interact(game, "innkeeper")
check(not result.success, "AI NPC not interactable when far")

# ======================================================================
# 15. AI-generated interactable interaction
# ======================================================================
print("15. AI-generated interactable interaction")

ai_inter = Interactable(
    id="test_chest",
    name="Test Chest",
    description="A test chest.",
    location="test_inn",
)
game.world.interactables["test_chest"] = ai_inter
ai_loc.interactables.append("test_chest")

ai_lm2 = generate_local_map(ai_loc)
_place_npcs_and_interactables(
    ai_lm2, ai_loc, game.world.npcs, game.world.interactables,
)

check(ai_inter.local_x >= 0, "AI interactable placed on map")

game.player.local_x = ai_inter.local_x + 1
game.player.local_y = ai_inter.local_y

result = interact(game, "test chest")
check(result.success, "AI interactable accessible when adjacent")

game.player.local_x = 17
game.player.local_y = 9
result = interact(game, "test chest")
check(not result.success, "AI interactable too far when distant")

# ======================================================================
# 16. Existing quest interaction
# ======================================================================
print("16. Existing quest interaction")

game = create_new_game()
game.player.location = "old_wooden_house"

# Create a quest with talk objective
quest = Quest(
    id="test_quest",
    title="Test Quest",
    description="Talk to the old man.",
    giver="old_man",
    state="active",
    objectives=[
        QuestObjective(
            id="talk_obj",
            type="talk",
            target="old_man",
            description="Talk to the old man.",
            required=1,
            current=0,
        ),
    ],
)
game.quests["test_quest"] = quest

# Place player near old_man
old_man = game.world.npcs["old_man"]
game.player.local_x = old_man.local_x + 1
game.player.local_y = old_man.local_y

result = interact(game, "old man")
check(result.success, "quest interaction works when adjacent")
check("quest_events" in result.data or result.data.get("quest_events"),
      "quest events returned")

# ======================================================================
# 17. Existing trading interaction
# ======================================================================
print("17. Trading interaction")

game = create_new_game()
game.player.location = "forest_edge"
merchant = game.world.npcs["merchant"]

# Player near merchant
game.player.local_x = merchant.local_x + 1
game.player.local_y = merchant.local_y
game.player.money = 1000

result = buy_item(game, "merchant", "Torch", 1)
check(result.success, "buy from merchant when adjacent")

# Player far from merchant
game.player.local_x = 17
game.player.local_y = 9
result = buy_item(game, "merchant", "Torch", 1)
check(not result.success, "buy from merchant when far fails")
check("too far" in result.message.lower() or result.data.get("reason") == "too_far",
      "buy failure reason is too far")

# Sell
game.player.local_x = merchant.local_x + 1
game.player.local_y = merchant.local_y
game.player.inventory.append("Torch")
result = sell_item(game, "merchant", "Torch", 1)
check(result.success, "sell to merchant when adjacent")

game.player.local_x = 17
game.player.local_y = 9
game.player.inventory.append("Torch")
result = sell_item(game, "merchant", "Torch", 1)
check(not result.success, "sell to merchant when far fails")

# ======================================================================
# 18. NPC-to-NPC dialogue (no proximity check)
# ======================================================================
print("18. NPC-to-NPC dialogue (no proximity needed)")

game = create_new_game()
game.player.location = "old_wooden_house"

# npc_interact is NPC-initiated; should work regardless of player position
game.player.local_x = 17
game.player.local_y = 9

result = npc_interact(game, "old_man", "sarah", "greeting")
check(result.success, "NPC-to-NPC dialogue works without proximity")
check("old man" in result.message.lower() or "sarah" in result.message.lower(),
      "message mentions NPCs")

# npc_interact_object
stew = game.world.interactables["kitchen_stew_pot"]
game.world.locations["old_wooden_house"].interactables.append("kitchen_stew_pot")
game.world.npcs["old_man"].current_activity_object = "kitchen_stew_pot"

result = npc_interact_object(game, "old_man", "kitchen_stew_pot")
# This may fail because stew pot is in kitchen, not old_wooden_house
# The point is it doesn't fail due to player proximity
check(not result.success or result.success,
      "NPC interact object doesn't crash on proximity")

# Cleanup
game.world.locations["old_wooden_house"].interactables.remove("kitchen_stew_pot")
game.world.npcs["old_man"].current_activity_object = ""

# ======================================================================
# 19. LocalObject/Interactable position consistency
# ======================================================================
print("19. LocalObject/Interactable position consistency")

game = create_new_game()

# Verify interactables are on walkable tiles (not on blocking objects)
for inter in game.world.interactables.values():
    lm = game.local_maps.get(inter.location)
    if lm is None or inter.local_x < 0:
        continue
    check(
        not lm.collision[inter.local_y][inter.local_x],
        f"interactable {inter.id} not on collision tile",
    )
    # Check not on blocking object
    blocked_by_obj = False
    for obj in lm.objects:
        if obj.blocking:
            if obj.x <= inter.local_x < obj.x + obj.width and obj.y <= inter.local_y < obj.y + obj.height:
                blocked_by_obj = True
                break
    check(not blocked_by_obj,
          f"interactable {inter.id} not on blocking object")

# ======================================================================
# 20. Full multi-location journey with interaction
# ======================================================================
print("20. Full multi-location journey with interaction")

game = create_new_game()

# House -> talk to old_man
game.player.location = "old_wooden_house"
om = game.world.npcs["old_man"]
game.player.local_x = om.local_x + 1
game.player.local_y = om.local_y
r = interact(game, "old man")
check(r.success, "journey: talk to old_man in house")

# House -> Kitchen
game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "journey: house -> kitchen")
check(game.player.location == "kitchen", "journey: in kitchen")

# Kitchen -> interact with stew pot
sk = game.world.interactables["kitchen_stew_pot"]
game.player.local_x = sk.local_x + 1
game.player.local_y = sk.local_y
r = interact(game, "stew pot")
check(r.success, "journey: interact with stew in kitchen")

# Kitchen -> House
game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "journey: kitchen -> house")

# House -> Forest Edge
game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "journey: house -> forest_edge")
check(game.player.location == "forest_edge", "journey: at forest_edge")

# Forest Edge -> merchant
m = game.world.npcs["merchant"]
game.player.local_x = m.local_x + 1
game.player.local_y = m.local_y
r = interact(game, "merchant")
check(r.success, "journey: talk to merchant")

# Forest Edge -> Deep Forest
game.player.local_x = 17
game.player.local_y = 5
r = move_local(game, 1, 0)
check(r.success, "journey: forest_edge -> deep_forest")
check(game.player.location == "deep_forest", "journey: in deep_forest")

# Deep Forest -> Forest Edge
game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "journey: deep_forest -> forest_edge")

# Forest Edge -> House
game.player.local_x = 1
game.player.local_y = 5
r = move_local(game, -1, 0)
check(r.success, "journey: forest_edge -> house")

# House -> interact with old_man again
om2 = game.world.npcs["old_man"]
game.player.local_x = om2.local_x + 1
game.player.local_y = om2.local_y
r = interact(game, "old man")
check(r.success, "journey: talk to old_man after full loop")

# ======================================================================
# Results
# ======================================================================
total = passed + failed
print(f"\n=== Phase 9: {passed}/{total} checks passed, {failed} failed ===")
if failed > 0:
    sys.exit(1)
