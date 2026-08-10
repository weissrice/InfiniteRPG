import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import (
    wait,
    move_player,
    npc_interact,
)
from engine.save import save_game, load_game


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    if detail and not condition:
        print(f"    detail: {detail}")
    return condition


def kitchen_evening():
    game = create_new_game()
    wait(game, 360)
    move_player(game, "kitchen")
    return game


def goal_snapshot(game):
    om = game.world.npcs["old_man"]
    sa = game.world.npcs["sarah"]
    return {
        "om_goals": list(om.goals),
        "sa_goals": list(sa.goals),
        "om_relationships": dict(om.relationships),
        "sa_relationships": dict(sa.relationships),
        "om_knowledge": list(om.knowledge),
        "sa_knowledge": list(sa.knowledge),
        "om_beliefs": list(om.beliefs),
        "sa_beliefs": list(sa.beliefs),
    }


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt - NPC goal transfer rules ===")
results.append(check(
    "RULES section present",
    "RULES:" in system,
))
results.append(check(
    "AI may propose candidate goal",
    "The AI may propose a candidate goal string" in normalized,
))
results.append(check(
    "Python validates exact possession",
    "Python validates whether the actor actually possesses this exact goal" in normalized,
))
results.append(check(
    "Transfer only on new NPC-to-NPC event",
    "genuinely new NPC-to-NPC conversation" in normalized,
))
results.append(check(
    "Goal transfer never affects relationships",
    "Goal transfer does NOT affect relationships" in normalized,
))
results.append(check(
    "Authoritative/subjective hierarchy present",
    "CRITICAL: AUTHORITATIVE VS SUBJECTIVE HIERARCHY" in normalized,
))

print("\n=== 1. Seed state and directionality ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]

goal_before = goal_snapshot(game)
results.append(check(
    "Seed goals present and distinct",
    old_man.goals == [
        "Keep the house safe.",
        "Stay near the fireplace during the rain.",
        "Protect the upstairs area from unwanted visitors.",
    ]
    and sarah.goals == [
        "Get the evening meal ready before dark.",
        "Keep the house running smoothly.",
    ],
))

print("\n=== 2. Valid goal transfer succeeds ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
goal_before = goal_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "protecting the house", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation succeeded",
    res.success is True,
))
results.append(check(
    "Actor possessed the exact goal",
    "Keep the house safe." in old_man.goals,
))
results.append(check(
    "Target did not already hold the goal",
    "Keep the house safe." not in goal_before["sa_goals"],
))
results.append(check(
    "Target learned the goal (goal addition)",
    goal_after["sa_goals"] == [
        "Get the evening meal ready before dark.",
        "Keep the house running smoothly.",
        "Keep the house safe.",
    ],
))
results.append(check(
    "goal_update datum present",
    res.data.get("goal_update") == {"goal": "Keep the house safe."},
))
results.append(check(
    "relationship_update unchanged (no additional delta)",
    goal_after["sa_relationships"]["Old Man"] == 11,
))

print("\n=== 3. Goal transfer respects new-event gate ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "protecting the house", goal_transfer="Keep the house safe.")
res = npc_interact(game, "old_man", "sarah", "protecting the house", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation still succeeds",
    res.success is True,
))
results.append(check(
    "Goal transfer did not repeat",
    "Keep the house safe." in goal_after["sa_goals"],
))
results.append(check(
    "Target goal unchanged after repeat",
    goal_after["sa_goals"].count("Keep the house safe.") == 1,
))

print("\n=== 4. Goal transfer respects goal uniqueness ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "topic a", goal_transfer="Keep the house safe.")
npc_interact(game, "old_man", "sarah", "topic b", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Target knows the goal",
    "Keep the house safe." in sarah.goals,
))
results.append(check(
    "Goal appears only once in target goals",
    sarah.goals.count("Keep the house safe.") == 1,
))

print("\n=== 5. Invalid goal proposal does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
goal_before = goal_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="Explore the deep forest")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation succeeds even with invalid goal",
    res.success is True,
))
results.append(check(
    "Invalid goal rejected (actor does not possess it)",
    "Explore the deep forest" not in old_man.goals,
))
results.append(check(
    "Target goal unchanged",
    goal_after["sa_goals"] == goal_before["sa_goals"],
))
results.append(check(
    "goal_update datum absent on rejection",
    res.data.get("goal_update") is None,
))

print("\n=== 6. Non-goal actor -> player does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
res = npc_interact(game, "old_man", "traveler", "topic", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "NPC -> player succeeds",
    res.success is True,
))
results.append(check(
    "goal_update datum absent (player target)",
    res.data.get("goal_update") is None,
))
results.append(check(
    "Old Man goal unchanged",
    "Keep the house safe." in old_man.goals,
))
results.append(check(
    "Target goal unchanged",
    goal_after["om_goals"] == old_man.goals,
))

print("\n=== 7. Self-target rejection blocks goal transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
goal_before = goal_snapshot(game)
res = npc_interact(game, "old_man", "old_man", "topic", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Self-target rejected",
    res.success is False,
))
results.append(check(
    "Goal transfer rejected (zero mutation)",
    goal_after["om_goals"] == goal_before["om_goals"],
    f"om_goals={goal_after['om_goals']!r}",
))

print("\n=== 8. Co-location requirement enforced ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
sarah.location = "old_wooden_house"
from_location = game.world.locations["kitchen"]
from_location.npcs.remove("sarah")
game.world.locations["old_wooden_house"].npcs.append("sarah")
goal_before = goal_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation rejected (not co-located)",
    res.success is False,
))
results.append(check(
    "Goal transfer blocked (zero mutation)",
    goal_after["om_goals"] == goal_before["om_goals"],
    f"om_goals={goal_after['om_goals']!r}",
))

print("\n=== 9. Empty/goal_transfer does not trigger transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "Goal transfer absent (empty string)",
    res.data.get("goal_update") is None,
))

print("\n=== 10. Duplicate goal within actor doesn't block transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
old_man.goals.append("Keep the house safe.")
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="Keep the house safe.")
goal_after = goal_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "goal_update datum present (actor has it)",
    res.data.get("goal_update") == {"goal": "Keep the house safe."},
))
results.append(check(
    "Target may still learn if it didn't hold it",
    "Keep the house safe." in sarah.goals,
))

print("\n=== 11. Save/load persists transferred goals ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "protecting the house", goal_transfer="Keep the house safe.")
path = Path(os.environ.get("TEMP", ".")) / "test_goal_evolution.json"
save_game(game, path)
loaded = load_game(path)
try:
    path.unlink()
except OSError:
    pass
loaded_old = loaded.world.npcs["old_man"]
loaded_sa = loaded.world.npcs["sarah"]

results.append(check(
    "Actor goal persisted",
    loaded_old.goals == old_man.goals,
))
results.append(check(
    "Target goal persisted",
    loaded_sa.goals == sarah.goals,
))
results.append(check(
    "Goal transferred in saved state",
    "Keep the house safe." in loaded_sa.goals,
))

ctx = build_game_context(loaded)
results.append(check(
    "Transferred goal rendered in context",
    "Keep the house safe." in ctx,
))

print("\n=== 12. Goal transfer distinct from relationship evolution ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
before_goal = goal_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="Keep the house safe.")
after_goal = goal_snapshot(game)

results.append(check(
    "Goal transfer triggered (actor has it, target doesn't)",
    after_goal["sa_goals"] == [
        "Get the evening meal ready before dark.",
        "Keep the house running smoothly.",
        "Keep the house safe.",
    ],
))
results.append(check(
    "Relationship delta still applied separately",
    after_goal["sa_relationships"]["Old Man"] == 11,
))

print("\n=== 13. Goal transfer distinct from knowledge transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(
    game, "old_man", "sarah", "topic",
    knowledge_transfer="The upstairs door is old and has a lock.",
    goal_transfer="Keep the house safe.",
)
after = goal_snapshot(game)

results.append(check(
    "Goal transfer succeeds alongside knowledge transfer",
    res.data.get("goal_update") == {"goal": "Keep the house safe."},
))
results.append(check(
    "Knowledge transfer succeeds alongside goal transfer",
    res.data.get("knowledge_update") == {"knowledge": "The upstairs door is old and has a lock."},
))
results.append(check(
    "Target gained the knowledge",
    "The upstairs door is old and has a lock." in after["sa_knowledge"],
))
results.append(check(
    "Target gained the goal",
    "Keep the house safe." in after["sa_goals"],
))

print("\n=== 14. Goal transfer distinct from belief transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(
    game, "old_man", "sarah", "topic",
    belief_transfer="The forest is likely quiet this time of day.",
    goal_transfer="Keep the house safe.",
)
after = goal_snapshot(game)

results.append(check(
    "Goal transfer succeeds alongside belief transfer",
    res.data.get("goal_update") == {"goal": "Keep the house safe."},
))
results.append(check(
    "Belief transfer succeeds alongside goal transfer",
    res.data.get("belief_update") == {"belief": "The forest is likely quiet this time of day."},
))
results.append(check(
    "Target gained the belief",
    "The forest is likely quiet this time of day." in after["sa_beliefs"],
))
results.append(check(
    "Target gained the goal",
    "Keep the house safe." in after["sa_goals"],
))

print("\n=== 15. Conflicting goals coexist ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
sarah.goals.append("Abandon the house and leave.")
res = npc_interact(game, "old_man", "sarah", "topic", goal_transfer="Keep the house safe.")
after = goal_snapshot(game)

results.append(check(
    "Conversation succeeds with conflicting goals present",
    res.success is True,
))
results.append(check(
    "New goal added alongside conflicting goal",
    "Keep the house safe." in after["sa_goals"]
    and "Abandon the house and leave." in after["sa_goals"],
))
results.append(check(
    "All original target goals preserved",
    len(after["sa_goals"]) == 4,
))

print()
fails = [r for r in results if not r]
print(f"{len(results) - len(fails)}/{len(results)} checks passed")
raise SystemExit(1 if fails else 0)
