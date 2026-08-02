import builtins
import json
import socket

from engine.world import create_new_game
from engine.game import GameEngine
from engine.actions import wait, move_player
from engine.ai import AIClient


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    if detail and not condition:
        print(f"    detail: {detail}")
    return condition


def server_available(host="127.0.0.1", port=1337, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


results = []

if not server_available():
    print("SKIP: AI server not running at http://127.0.0.1:1337")
    print("      Real-model regression cannot run; unit suite covers the mechanics.")
    print()
    print("RESULT: 0/0 checks passed (skipped)")
    raise SystemExit(0)


class RecordingAI(AIClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def ask(self, prompt, system=None, max_tokens=2048, temperature=0.5, json_mode=False):
        raw = super().ask(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
        self.calls.append({"system": system, "prompt": prompt, "raw": raw})
        return raw

    def close(self):
        super().close()


def setup():
    game = create_new_game()
    wait(game, 360)                 # 12:00 -> 18:00; both NPCs move to Kitchen
    move_player(game, "kitchen")
    return game


def parse(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"__parse_error__": str(exc), "raw": raw}


print("=== 1. Scene setup for relationship evolution ===")
engine = GameEngine()
engine.game = setup()
game = engine.game
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
results.append(check(
    "Both NPCs co-located in the Kitchen at 18:00",
    old_man.location == "kitchen"
    and sarah.location == "kitchen"
    and game.player.location == "kitchen"
    and game.world.time == "18:00",
    f"old_man={old_man.location!r} sarah={sarah.location!r} "
    f"player={game.player.location!r} time={game.world.time!r}",
))
results.append(check(
    "Seeded directional edges in place",
    old_man.relationships.get("Sarah") == 3
    and sarah.relationships.get("Old Man") == 10,
    f"old_man={dict(old_man.relationships)!r} sarah={dict(sarah.relationships)!r}",
))

ai = RecordingAI()
engine.ai = ai

print("\n=== 2. Player->NPC probe leaves relationships untouched ===")
rel_before_old = dict(old_man.relationships)
rel_before_sa = dict(sarah.relationships)

old_input = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("ask the old man: do you know sarah well?")
finally:
    builtins.input = old_input

call = ai.calls[-1]
probe_raw = call["raw"]
parsed = parse(probe_raw)
probe_ok = "__parse_error__" not in parsed and parsed.get("actions")

results.append(check(
    "Probe exchange executed",
    probe_ok,
    f"raw={probe_raw[:400]!r}",
))
results.append(check(
    "Player->NPC dialogue changed no relationship edge",
    dict(old_man.relationships) == rel_before_old
    and dict(sarah.relationships) == rel_before_sa,
    f"old_man={dict(old_man.relationships)!r} sarah={dict(sarah.relationships)!r}",
))

print("\n=== 3. NPC->NPC batch advances both edges per distinct event ===")
initiation_inputs = [
    "of his own accord, the old man turns to sarah and tells her the stew is nearly ready",
    "sarah, on her own, mentions to the old man that he should stir the pot more",
    "the old man and sarah start talking to each other about the kitchen, on their own",
]

N_TRIALS = 2
npc_npc_executed = 0
executed_events = set()
seen_events = set()
update_datum_ok = True
repeat_datum_none_ok = True
trial_raises = []

for player_input in initiation_inputs:
    for _ in range(N_TRIALS):
        old_input = builtins.input
        builtins.input = lambda _="": ""
        try:
            result = engine.process_input(player_input)
        finally:
            builtins.input = old_input

        trial_raises.append(ai.calls[-1]["raw"])

        for item in result.get("actions", []):
            requested = item.get("requested", {})
            if (
                requested.get("type") == "interact"
                and requested.get("actor") in {"old_man", "sarah"}
                and requested.get("target") in {"old_man", "sarah"}
                and requested.get("actor") != requested.get("target")
                and item.get("success") is True
            ):
                npc_npc_executed += 1
                event_key = (
                    requested.get("actor"),
                    requested.get("target"),
                    requested.get("topic", ""),
                )
                executed_events.add(event_key)

                update = item.get("data", {}).get("relationship_update")
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    if not (
                        isinstance(update, dict)
                        and update.get("delta") == 1
                        and update.get("target") in {"Old Man", "Sarah"}
                        and isinstance(update.get("actor_score"), int)
                        and isinstance(update.get("target_score"), int)
                        and -100 <= update.get("actor_score", 0) <= 100
                        and -100 <= update.get("target_score", 0) <= 100
                    ):
                        update_datum_ok = False
                elif update is not None:
                    repeat_datum_none_ok = False

distinct_events = len(executed_events)
delta_old = old_man.relationships.get("Sarah", 0) - rel_before_old.get("Sarah", 0)
delta_sa = sarah.relationships.get("Old Man", 0) - rel_before_sa.get("Old Man", 0)

results.append(check(
    "At least one NPC->NPC interaction executed successfully",
    npc_npc_executed > 0,
    f"executed={npc_npc_executed} (real-model nondeterminism)",
))
results.append(check(
    "Both relationship edges advanced by exactly the distinct-event count",
    delta_old == distinct_events and delta_sa == distinct_events,
    f"old_man edge delta={delta_old} sarah edge delta={delta_sa} "
    f"distinct events={distinct_events} executed={sorted(executed_events)!r}",
))
results.append(check(
    "relationship_update datum present on every novel executed event",
    update_datum_ok,
    f"executed={npc_npc_executed} distinct={distinct_events}",
))
results.append(check(
    "Repeated events carry no relationship_update datum",
    repeat_datum_none_ok,
    f"executed={npc_npc_executed} distinct={distinct_events}",
))

print("\n--- Real-model raw responses (small batch) ---")
for i, raw in enumerate(trial_raises, start=1):
    print(f"\nINPUT {i}: {initiation_inputs[(i - 1) // N_TRIALS]!r}")
    print(raw)

print("\n=== 4. Real-model request carried the evolution rules ===")
sent_system = " ".join(ai.calls[1]["system"].split())
results.append(check(
    "NPC RELATIONSHIP EVOLUTION RULES carried in the real request",
    "NPC RELATIONSHIP EVOLUTION RULES:" in ai.calls[1]["system"],
))
results.append(check(
    "AI-side prohibition carried (no narrating deltas)",
    "without narrating the change itself" in sent_system,
))

fails = [r for r in results if not r]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
raise SystemExit(1 if fails else 0)
