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


def belief_snapshot(game):
    om = game.world.npcs["old_man"]
    sa = game.world.npcs["sarah"]
    return {
        "om_beliefs": list(om.beliefs),
        "sa_beliefs": list(sa.beliefs),
        "om_relationships": dict(om.relationships),
        "sa_relationships": dict(sa.relationships),
        "om_knowledge": list(om.knowledge),
        "sa_knowledge": list(sa.knowledge),
    }


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt - NPC BELIEF TRANSFER RULES ===")
results.append(check(
    "NPC BELIEF TRANSFER RULES section present",
    "NPC BELIEF TRANSFER RULES:" in system,
))
results.append(check(
    "AI may propose candidate belief",
    "The AI may propose a candidate belief string" in normalized,
))
results.append(check(
    "Python validates exact possession",
    "Python validates whether the actor actually possesses this exact belief" in normalized,
))
results.append(check(
    "Transfer only on new NPC-to-NPC event",
    "genuinely new NPC-to-NPC conversation" in normalized,
))
results.append(check(
    "Belief transfer never affects relationships",
    "Belief transfer does NOT affect relationships" in normalized,
))
results.append(check(
    "Authoritative/subjective hierarchy present",
    "CRITICAL: AUTHORITATIVE VS SUBJECTIVE HIERARCHY" in normalized,
))

print("\n=== 1. Seed state and directionality ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]

belief_before = belief_snapshot(game)
results.append(check(
    "Seed beliefs present and distinct",
    old_man.beliefs == [
        "Nobody has entered the upstairs room recently.",
        "The house is probably safe despite its age.",
        "The forest is likely quiet this time of day.",
    ]
    and sarah.beliefs == [
        "The Old Man talks more than he stirs.",
        "The meal must be ready before nightfall.",
    ],
))

print("\n=== 2. Valid belief transfer succeeds ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
belief_before = belief_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "the forest", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation succeeded",
    res.success is True,
))
results.append(check(
    "Actor possessed the exact belief",
    "The forest is likely quiet this time of day." in old_man.beliefs,
))
results.append(check(
    "Target did not already hold the belief",
    "The forest is likely quiet this time of day." not in belief_before["sa_beliefs"],
))
results.append(check(
    "Target learned the belief (belief addition)",
    belief_after["sa_beliefs"] == [
        "The Old Man talks more than he stirs.",
        "The meal must be ready before nightfall.",
        "The forest is likely quiet this time of day.",
    ],
))
results.append(check(
    "belief_update datum present",
    res.data.get("belief_update") == {"belief": "The forest is likely quiet this time of day."},
))
results.append(check(
    "relationship_update unchanged (no additional delta)",
    belief_after["sa_relationships"]["Old Man"] == 11,
))

print("\n=== 3. Belief transfer respects new-event gate ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the forest", belief_transfer="The forest is likely quiet this time of day.")
res = npc_interact(game, "old_man", "sarah", "the forest", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation still succeeds",
    res.success is True,
))
results.append(check(
    "Belief transfer did not repeat",
    "The forest is likely quiet this time of day." in belief_after["sa_beliefs"],
))
results.append(check(
    "Target belief unchanged after repeat",
    belief_after["sa_beliefs"].count("The forest is likely quiet this time of day.") == 1,
))

print("\n=== 4. Belief transfer respects belief uniqueness ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "topic a", belief_transfer="The forest is likely quiet this time of day.")
npc_interact(game, "old_man", "sarah", "topic b", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Target knows the belief",
    "The forest is likely quiet this time of day." in sarah.beliefs,
))
results.append(check(
    "Belief appears only once in target beliefs",
    sarah.beliefs.count("The forest is likely quiet this time of day.") == 1,
))

print("\n=== 5. Invalid belief proposal does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
belief_before = belief_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="The sky is always blue")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation succeeds even with invalid belief",
    res.success is True,
))
results.append(check(
    "Invalid belief rejected (actor does not possess it)",
    "The sky is always blue" not in old_man.beliefs,
))
results.append(check(
    "Target belief unchanged",
    belief_after["sa_beliefs"] == belief_before["sa_beliefs"],
))
results.append(check(
    "belief_update datum absent on rejection",
    res.data.get("belief_update") is None,
))

print("\n=== 6. Non-belief actor -> player does not transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
res = npc_interact(game, "old_man", "traveler", "topic", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "NPC -> player succeeds",
    res.success is True,
))
results.append(check(
    "belief_update datum absent (player target)",
    res.data.get("belief_update") is None,
))
results.append(check(
    "Old Man belief unchanged",
    "The forest is likely quiet this time of day." in old_man.beliefs,
))
results.append(check(
    "Target belief unchanged",
    belief_after["om_beliefs"] == old_man.beliefs,
))

print("\n=== 7. Self-target rejection blocks belief transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
belief_before = belief_snapshot(game)
res = npc_interact(game, "old_man", "old_man", "topic", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Self-target rejected",
    res.success is False,
))
results.append(check(
    "Belief transfer rejected (zero mutation)",
    belief_after["om_beliefs"] == belief_before["om_beliefs"],
    f"om_beliefs={belief_after['om_beliefs']!r}",
))

print("\n=== 8. Co-location requirement enforced ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
sarah.location = "old_wooden_house"
from_location = game.world.locations["kitchen"]
from_location.npcs.remove("sarah")
game.world.locations["old_wooden_house"].npcs.append("sarah")
belief_before = belief_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation rejected (not co-located)",
    res.success is False,
))
results.append(check(
    "Belief transfer blocked (zero mutation)",
    belief_after["om_beliefs"] == belief_before["om_beliefs"],
    f"om_beliefs={belief_after['om_beliefs']!r}",
))

print("\n=== 9. Empty/belief_transfer does not trigger transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "Belief transfer absent (empty string)",
    res.data.get("belief_update") is None,
))

print("\n=== 10. Duplicate belief within actor doesn't block transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
old_man.beliefs.append("The forest is likely quiet this time of day.")
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="The forest is likely quiet this time of day.")
belief_after = belief_snapshot(game)

results.append(check(
    "Conversation succeeds",
    res.success is True,
))
results.append(check(
    "belief_update datum present (actor has it)",
    res.data.get("belief_update") == {"belief": "The forest is likely quiet this time of day."},
))
results.append(check(
    "Target may still learn if it didn't hold it",
    "The forest is likely quiet this time of day." in sarah.beliefs,
))

print("\n=== 11. Save/load persists transferred beliefs ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "the forest", belief_transfer="The forest is likely quiet this time of day.")
path = Path(os.environ.get("TEMP", ".")) / "test_belief_evolution.json"
save_game(game, path)
loaded = load_game(path)
try:
    path.unlink()
except OSError:
    pass
loaded_old = loaded.world.npcs["old_man"]
loaded_sa = loaded.world.npcs["sarah"]

results.append(check(
    "Actor belief persisted",
    loaded_old.beliefs == old_man.beliefs,
))
results.append(check(
    "Target belief persisted",
    loaded_sa.beliefs == sarah.beliefs,
))
results.append(check(
    "Belief transferred in saved state",
    "The forest is likely quiet this time of day." in loaded_sa.beliefs,
))

ctx = build_game_context(loaded)
results.append(check(
    "Transferred belief rendered in context",
    "The forest is likely quiet this time of day." in ctx,
))

print("\n=== 12. Belief transfer distinct from relationship evolution ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
before_belief = belief_snapshot(game)
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="The forest is likely quiet this time of day.")
after_belief = belief_snapshot(game)

results.append(check(
    "Belief transfer triggered (actor has it, target doesn't)",
    after_belief["sa_beliefs"] == [
        "The Old Man talks more than he stirs.",
        "The meal must be ready before nightfall.",
        "The forest is likely quiet this time of day.",
    ],
))
results.append(check(
    "Relationship delta still applied separately",
    after_belief["sa_relationships"]["Old Man"] == 11,
))

print("\n=== 13. Belief transfer distinct from knowledge transfer ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(
    game, "old_man", "sarah", "topic",
    knowledge_transfer="The upstairs door is old and has a lock.",
    belief_transfer="The forest is likely quiet this time of day.",
)
after = belief_snapshot(game)

results.append(check(
    "Belief transfer succeeds alongside knowledge transfer",
    res.data.get("belief_update") == {"belief": "The forest is likely quiet this time of day."},
))
results.append(check(
    "Knowledge transfer succeeds alongside belief transfer",
    res.data.get("knowledge_update") == {"knowledge": "The upstairs door is old and has a lock."},
))
results.append(check(
    "Target gained the knowledge",
    "The upstairs door is old and has a lock." in after["sa_knowledge"],
))
results.append(check(
    "Target gained the belief",
    "The forest is likely quiet this time of day." in after["sa_beliefs"],
))

print("\n=== 14. Conflicting beliefs coexist ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
sarah.beliefs.append("The forest is dangerous at night.")
res = npc_interact(game, "old_man", "sarah", "topic", belief_transfer="The forest is likely quiet this time of day.")
after = belief_snapshot(game)

results.append(check(
    "Conversation succeeds with conflicting beliefs present",
    res.success is True,
))
results.append(check(
    "New belief added alongside conflicting belief",
    "The forest is likely quiet this time of day." in after["sa_beliefs"]
    and "The forest is dangerous at night." in after["sa_beliefs"],
))
results.append(check(
    "Both beliefs present in target belief list",
    len(after["sa_beliefs"]) == 4,
))

print()
fails = [r for r in results if not r]
print(f"{len(results) - len(fails)}/{len(results)} checks passed")
raise SystemExit(1 if fails else 0)
