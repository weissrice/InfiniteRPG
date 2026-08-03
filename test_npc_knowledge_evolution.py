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


def knowledge_snapshot(game):
    om = game.world.npcs["old_man"]
    sa = game.world.npcs["sarah"]
    return {
        "om_knowledge": list(om.knowledge),
        "sa_knowledge": list(sa.knowledge),
        "om_relationships": dict(om.relationships),
        "sa_relationships": dict(sa.relationships),
    }


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt - NPC KNOWLEDGE TRANSFER RULES ===")
results.append(check(
    "NPC KNOWLEDGE TRANSFER RULES section present",
    "NPC KNOWLEDGE TRANSFER RULES:" in system,
))
results.append(check(
    "AI may propose candidate knowledge",
    "The AI may propose a candidate knowledge string" in normalized,
))
results.append(check(
    "Python validates candidate against actor.knowledge",
    "Python validates whether the actor actually possesses this exact knowledge" in normalized,
))
results.append(check(
    "Transfer only on new NPC-to-NPC event",
    "genuinely new NPC-to-NPC conversation" in normalized,
))
results.append(check(
    "Knowledge transfer never affects relationships",
    "Knowledge transfer does NOT affect relationships" in normalized,
))
results.append(check(
    "Authoritative/subjective hierarchy present",
    "CRITICAL: AUTHORITATIVE VS SUBJECTIVE HIERARCHY" in normalized,
))

print("\n=== 1. Seed state and directionality ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]

knowledge_before = knowledge_snapshot(game)
results.append(check(
    "Seed knowledge present and distinct",
    old_man.knowledge == [
        "The house has an upstairs floor.",
        "The house has been here for many years.",
        "The upstairs door is old and has a lock.",
        "The northern road leads toward the forest.",
    ]
    and sarah.knowledge == [
        "The old house has a kitchen and an upstairs floor.",
        "The Old Man has lived in this house for years.",
        "The evening meal is prepared in the kitchen.",
    ],
))

print("\n=== 2. Valid knowledge transfer succeeds ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
knowledge_before = knowledge_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "the upstairs door", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation succeeded",
    res.success is True,
))
results.append(check(
    "Actor possessed the exact knowledge",
    "The upstairs door is old and has a lock." in old_man.knowledge,
))
results.append(check(
    "Target did not already know the fact",
    "The upstairs door is old and has a lock." not in knowledge_before["sa_knowledge"],
))
results.append(check(
    "Target learned the fact (knowledge addition)",
    knowledge_after["sa_knowledge"] == [
        "The old house has a kitchen and an upstairs floor.",
        "The Old Man has lived in this house for years.",
        "The evening meal is prepared in the kitchen.",
        "The upstairs door is old and has a lock.",
    ],
))
results.append(check(
    "knowledge_update datum present",
    res.data.get("knowledge_update") == {"knowledge": "The upstairs door is old and has a lock."},
))
results.append(check(
    "relationship_update unchanged (no additional delta)",
    knowledge_after["sa_relationships"]["Old Man"] == 11,
))

print("\n=== 3. Knowledge transfer respects new-event gate ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the upstairs door", knowledge_transfer="The upstairs door is old and has a lock.")
res = npc_interact(game, "old_man", "sarah", "the upstairs door", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation still succeeds",
    res.success is True,
))
results.append(check(
    "Knowledge transfer did not repeat",
    "The upstairs door is old and has a lock." in knowledge_after["sa_knowledge"],
))
results.append(check(
    "Target knowledge unchanged after repeat",
    knowledge_after["sa_knowledge"].count("The upstairs door is old and has a lock.") == 1,
))

print("\n=== 4. Knowledge transfer respects knowledge uniqueness ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "topic a", knowledge_transfer="The upstairs door is old and has a lock.")
npc_interact(game, "old_man", "sarah", "topic b", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Target knows the fact",
    "The upstairs door is old and has a lock." in sarah.knowledge,
))
results.append(check(
    "Fact appears only once in target knowledge",
    sarah.knowledge.count("The upstairs door is old and has a lock.") == 1,
))

print("\n=== 5. Invalid knowledge proposal does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
knowledge_before = knowledge_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", knowledge_transfer="The forest is quiet")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation succeeds even with invalid knowledge",
    res.success is True,
))
results.append(check(
    "Invalid knowledge rejected (actor does not possess it)",
    "The forest is quiet" not in old_man.knowledge,
))
results.append(check(
    "Target knowledge unchanged",
    knowledge_after["sa_knowledge"] == knowledge_before["sa_knowledge"],
))
results.append(check(
    "knowledge_update datum absent on rejection",
    res.data.get("knowledge_update") is None,
))

print("\n=== 6. Non-knowledge actor -> player does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
res = npc_interact(game, "old_man", "traveler", "topic", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "NPC -> player succeeds",
    res.success is True,
))
results.append(check(
    "knowledge_update datum absent (player target)",
    res.data.get("knowledge_update") is None,
))
results.append(check(
    "Old Man knowledge unchanged",
    "The upstairs door is old and has a lock." in old_man.knowledge,
))
results.append(check(
    "Target knowledge unchanged",
    knowledge_after["om_knowledge"] == old_man.knowledge,
))

print("\n=== 7. Self-target rejection blocks knowledge transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
knowledge_before = knowledge_snapshot(game)
res = npc_interact(game, "old_man", "old_man", "topic", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Self-target rejected",
    res.success is False,
))
results.append(check(
    "Knowledge transfer rejected (zero mutation)",
    knowledge_after["om_knowledge"] == knowledge_before["om_knowledge"],
    f"om_knowledge={knowledge_after['om_knowledge']!r}",
))

print("\n=== 8. Co-location requirement enforced ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
sarah.location = "old_wooden_house"
from_location = game.world.locations["kitchen"]
from_location.npcs.remove("sarah")
game.world.locations["old_wooden_house"].npcs.append("sarah")
knowledge_before = knowledge_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation rejected (not co-located)",
    res.success is False,
))
results.append(check(
    "Knowledge transfer blocked (zero mutation)",
    knowledge_after["om_knowledge"] == knowledge_before["om_knowledge"],
    f"om_knowledge={knowledge_after['om_knowledge']!r}",
))

print("\n=== 9. Empty/knowledge_transfer does not trigger transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "topic", knowledge_transfer="")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "Knowledge transfer absent (empty string)",
    res.data.get("knowledge_update") is None,
))

print("\n=== 10. Duplicate knowledge within actor doesn't trigger transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
# Add duplicate to actor's knowledge (simulate)
old_man.knowledge.append("The upstairs door is old and has a lock.")
res = npc_interact(game, "old_man", "sarah", "topic", knowledge_transfer="The upstairs door is old and has a lock.")
knowledge_after = knowledge_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "knowledge_update datum present (actor has it)",
    res.data.get("knowledge_update") == {"knowledge": "The upstairs door is old and has a lock."},
))
results.append(check(
    "Target may still learn if it didn't know it",
    "The upstairs door is old and has a lock." in sarah.knowledge,
))

print("\n=== 11. Save/load persists transferred knowledge ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "the upstairs door", knowledge_transfer="The upstairs door is old and has a lock.")
path = Path(os.environ.get("TEMP", ".")) / "test_knowledge_evolution.json"
save_game(game, path)
loaded = load_game(path)
try:
    path.unlink()
except OSError:
    pass
loaded_old = loaded.world.npcs["old_man"]
loaded_sa = loaded.world.npcs["sarah"]

results.append(check(
    "Actor knowledge persisted",
    loaded_old.knowledge == old_man.knowledge,
))
results.append(check(
    "Target knowledge persisted",
    loaded_sa.knowledge == sarah.knowledge,
))
results.append(check(
    "Knowledge transferred in saved state",
    "The upstairs door is old and has a lock." in loaded_sa.knowledge,
))

ctx = build_game_context(loaded)
results.append(check(
    "Transferred knowledge rendered in context",
    "The upstairs door is old and has a lock." in ctx,
))

print("\n=== 12. Knowledge transfer distinct from relationship evolution ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
before_knowledge = knowledge_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", knowledge_transfer="The upstairs door is old and has a lock.")
after_knowledge = knowledge_snapshot(game)

results.append(check(
    "Knowledge transfer triggered (actor has it, target doesn't)",
    after_knowledge["sa_knowledge"] == [
        "The old house has a kitchen and an upstairs floor.",
        "The Old Man has lived in this house for years.",
        "The evening meal is prepared in the kitchen.",
        "The upstairs door is old and has a lock.",
    ],
))
results.append(check(
    "Relationship delta still applied separately",
    after_knowledge["sa_relationships"]["Old Man"] == 11,
))

print()
fails = [r for r in results if not r]
print(f"{len(results) - len(fails)}/{len(results)} checks passed")
raise SystemExit(1 if fails else 0)
