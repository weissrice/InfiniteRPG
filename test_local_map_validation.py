# -*- coding: utf-8 -*-
"""Automated LocalMap reachability and layout validation.

Uses BFS flood-fill from each location's spawn to verify:
- All exits are reachable
- No blocking objects overlap exits
- Spawns are valid
- Object footprints are in bounds
- Entry points are escapable
"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import LocalMap, LocalObject


def check(label, condition):
    print("PASS" if condition else "FAIL", label, sep=": ")
    return condition


def bfs_reachable(lm, sx, sy):
    """Return set of all reachable tiles from (sx, sy) via BFS."""
    visited = set()
    queue = deque([(sx, sy)])
    visited.add((sx, sy))
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < lm.width and 0 <= ny < lm.height:
                if (nx, ny) not in visited and not lm.collision[ny][nx]:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return visited


def validate_location(loc_id, lm, results):
    """Run all validations for a single location."""
    sx, sy = lm.spawn

    # --- Spawn validity ---
    spawn_in_bounds = (0 <= sx < lm.width and 0 <= sy < lm.height)
    spawn_not_blocked = spawn_in_bounds and not lm.collision[sy][sx]
    results.append(check(
        "%s: spawn (%d,%d) in bounds" % (loc_id, sx, sy),
        spawn_in_bounds))
    results.append(check(
        "%s: spawn (%d,%d) not blocked" % (loc_id, sx, sy),
        spawn_not_blocked))

    # Spawn must have at least one walkable neighbor
    spawn_neighbors = False
    if spawn_not_blocked:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = sx + dx, sy + dy
            if 0 <= nx < lm.width and 0 <= ny < lm.height:
                if not lm.collision[ny][nx]:
                    spawn_neighbors = True
                    break
    results.append(check(
        "%s: spawn has walkable neighbor" % loc_id,
        spawn_neighbors))

    # --- BFS reachability ---
    reachable = bfs_reachable(lm, sx, sy) if spawn_not_blocked else set()

    # --- Exit validation ---
    for ename, ep in lm.exits.items():
        ep_in_bounds = (0 <= ep.x < lm.width and 0 <= ep.y < lm.height)
        results.append(check(
            "%s: exit '%s' (%d,%d) in bounds" % (loc_id, ename, ep.x, ep.y),
            ep_in_bounds))

        ep_not_blocked = ep_in_bounds and not lm.collision[ep.y][ep.x]
        results.append(check(
            "%s: exit '%s' (%d,%d) not blocked" % (loc_id, ename, ep.x, ep.y),
            ep_not_blocked))

        ep_reachable = (ep.x, ep.y) in reachable
        results.append(check(
            "%s: exit '%s' (%d,%d) reachable from spawn" % (
                loc_id, ename, ep.x, ep.y),
            ep_reachable))

        # Exit must have at least one walkable neighbor
        ep_neighbor = False
        if ep_in_bounds:
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = ep.x + dx, ep.y + dy
                if 0 <= nx < lm.width and 0 <= ny < lm.height:
                    if not lm.collision[ny][nx]:
                        ep_neighbor = True
                        break
        results.append(check(
            "%s: exit '%s' has walkable neighbor" % (loc_id, ename),
            ep_neighbor))

    # --- Object footprint validation ---
    for obj in lm.objects:
        # Width/height >= 1
        results.append(check(
            "%s: '%s' dimensions valid" % (loc_id, obj.id),
            obj.width >= 1 and obj.height >= 1))

        # Footprint in bounds
        in_bounds = (obj.x >= 0 and obj.y >= 0
                     and obj.x + obj.width <= lm.width
                     and obj.y + obj.height <= lm.height)
        results.append(check(
            "%s: '%s' in bounds" % (loc_id, obj.id),
            in_bounds))

        # Blocking objects: collision grid matches footprint
        if obj.blocking and in_bounds:
            for dy in range(obj.height):
                for dx in range(obj.width):
                    ox, oy = obj.x + dx, obj.y + dy
                    results.append(check(
                        "%s: '%s' (%d,%d) collision=True" % (
                            loc_id, obj.id, ox, oy),
                        lm.collision[oy][ox]))

        # No blocking object overlaps an exit
        if obj.blocking and in_bounds:
            for ename, ep in lm.exits.items():
                overlaps = (obj.x <= ep.x < obj.x + obj.width
                            and obj.y <= ep.y < obj.y + obj.height)
                results.append(check(
                    "%s: '%s' does not overlap exit '%s'" % (
                        loc_id, obj.id, ename),
                    not overlaps))

    # --- Terrain/collision consistency ---
    exit_tiles = set((ep.x, ep.y) for ep in lm.exits.values())
    for y in range(lm.height):
        for x in range(lm.width):
            t = lm.terrain[y][x]
            c = lm.collision[y][x]
            # Exit tiles (actual exits, not decorative doors) must be walkable
            if t == "+" and (x, y) in exit_tiles:
                results.append(check(
                    "%s: exit tile (%d,%d) walkable" % (loc_id, x, y),
                    not c))


results = []


# =========================================================================
# 1. Validate all 5 existing local maps
# =========================================================================
print("=== 1. Local map validation ===")
game = create_new_game()
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    lm = game.local_maps.get(loc_id)
    if lm is None:
        results.append(check("%s: map exists" % loc_id, False))
        continue
    results.append(check("%s: map exists" % loc_id, True))
    validate_location(loc_id, lm, results)


# =========================================================================
# 2. Full journey validation (area-transition consistency)
# =========================================================================
print("\n=== 2. Full journey validation ===")
from engine.actions import move_local, has_local_movement

g2 = create_new_game()

# LR -> Kitchen
g2.player.location = "old_wooden_house"
g2.player.local_x = 1
g2.player.local_y = 5
r = move_local(g2, -1, 0)
results.append(check("LR -> Kitchen transition", r.success))
results.append(check("Arrived in kitchen", g2.player.location == "kitchen"))

# Kitchen -> LR
g2.player.local_x = 17
g2.player.local_y = 5
r = move_local(g2, 1, 0)
results.append(check("Kitchen -> LR transition", r.success))
results.append(check("Arrived in LR", g2.player.location == "old_wooden_house"))

# LR -> Upstairs
g2.player.local_x = 10
g2.player.local_y = 1
r = move_local(g2, 0, -1)
results.append(check("LR -> Upstairs transition", r.success))
results.append(check("Arrived in upstairs", g2.player.location == "upstairs"))

# Upstairs -> LR
g2.player.local_x = 9
g2.player.local_y = 9
r = move_local(g2, 0, 1)
results.append(check("Upstairs -> LR transition", r.success))
results.append(check("Arrived in LR", g2.player.location == "old_wooden_house"))

# LR -> Forest Edge
g2.player.local_x = 17
g2.player.local_y = 5
r = move_local(g2, 1, 0)
results.append(check("LR -> Forest Edge transition", r.success))
results.append(check("Arrived in FE", g2.player.location == "forest_edge"))

# Forest Edge -> Deep Forest
g2.player.local_x = 17
g2.player.local_y = 5
r = move_local(g2, 1, 0)
results.append(check("FE -> Deep Forest transition", r.success))
results.append(check("Arrived in DF", g2.player.location == "deep_forest"))

# Deep Forest -> Forest Edge
g2.player.local_x = 1
g2.player.local_y = 5
r = move_local(g2, -1, 0)
results.append(check("DF -> FE transition", r.success))
results.append(check("Arrived in FE", g2.player.location == "forest_edge"))

# Forest Edge -> LR
g2.player.local_x = 1
g2.player.local_y = 5
r = move_local(g2, -1, 0)
results.append(check("FE -> LR transition", r.success))
results.append(check("Arrived in LR", g2.player.location == "old_wooden_house"))


# =========================================================================
# 3. Entry point escapability
# =========================================================================
print("\n=== 3. Entry point escapability ===")
from engine.actions import _resolve_entry_point

g3 = create_new_game()
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    lm = g3.local_maps.get(loc_id)
    if lm is None:
        continue
    for ename, ep in lm.exits.items():
        # Get entry point in the target location
        target_lm = g3.local_maps.get(ep.target_location_id)
        if target_lm is None:
            continue
        ex, ey = _resolve_entry_point(g3, ep.target_location_id, ep.entry_name)
        # Entry must be in bounds and not blocked
        in_bounds = (0 <= ex < target_lm.width and 0 <= ey < target_lm.height)
        not_blocked = in_bounds and not target_lm.collision[ey][ex]
        results.append(check(
            "%s -> %s entry (%d,%d) valid" % (
                loc_id, ep.target_location_id, ex, ey),
            in_bounds and not_blocked))
        # Entry must have at least one walkable neighbor
        has_neighbor = False
        if not_blocked:
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = ex + dx, ey + dy
                if 0 <= nx < target_lm.width and 0 <= ny < target_lm.height:
                    if not target_lm.collision[ny][nx]:
                        has_neighbor = True
                        break
        results.append(check(
            "%s -> %s entry has escape path" % (
                loc_id, ep.target_location_id),
            has_neighbor))


# =========================================================================
# 4. has_local_movement consistency
# =========================================================================
print("\n=== 4. has_local_movement consistency ===")
g4 = create_new_game()
for loc_id in ["old_wooden_house", "kitchen", "upstairs",
               "forest_edge", "deep_forest"]:
    g4.player.location = loc_id
    results.append(check(
        "%s: has_local_movement" % loc_id,
        has_local_movement(g4)))


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print("%d/%d checks passed, %d failed" % (passed, total, total - passed))
