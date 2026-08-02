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
    print("      Real-model regression cannot run; unit suite covers the prompt rules.")
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


print("=== 1. Automated NPC->NPC social sequence (no manual typing) ===")
engine = GameEngine()
engine.game = setup()
game = engine.game
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
pot = game.world.interactables["kitchen_stew_pot"]
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
    "Old Man bound to the Stew Pot for the 18:00 activity",
    old_man.current_activity_object == "kitchen_stew_pot",
    f"current_activity_object={old_man.current_activity_object!r}",
))
results.append(check(
    "Sarah has no activity object (present but unbounded)",
    sarah.current_activity_object == "",
    f"sarah activity_object={sarah.current_activity_object!r}",
))

ai = RecordingAI()
engine.ai = ai

print("\n=== 2. Player->NPC direction preserved in a two-NPC scene ===")
probe_attempts = 0
probe_ok = False
probe_narration = ""
probe_prompt = ""
probe_raw = ""

for _ in range(3):
    probe_attempts += 1
    old_input = builtins.input
    builtins.input = lambda _="": ""
    try:
        engine.process_input("ask the old man: who is Sarah, and what is she doing?")
    finally:
        builtins.input = old_input

    call = ai.calls[-1]
    probe_prompt = call["prompt"]
    probe_raw = call["raw"]
    parsed = parse(call["raw"])
    raw_ok = "__parse_error__" not in parsed
    actions = parsed.get("actions", []) if raw_ok else []

    if (
        actions
        and not any("actor" in action for action in actions)
        and any(
            action.get("type") == "interact"
            and action.get("target") == "old_man"
            for action in actions
        )
    ):
        probe_ok = True
        probe_narration = parsed.get("narration", "")
        break

results.append(check(
    "Player question produced a PLAYER interact (no actor field)",
    probe_ok,
    f"raw={probe_raw[:400]} (after {probe_attempts} attempts)",
))
results.append(check(
    "Narration carries a spoken exchange by the NPC",
    '"' in probe_narration or "'" in probe_narration,
    f"narration={probe_narration!r}",
))
results.append(check(
    "Request carried Sarah's presence in the scene",
    "Sarah" in probe_prompt,
))
results.append(check(
    "Request carried the co-location note",
    "may speak to one another" in probe_prompt,
))
results.append(check(
    "Narration references the two-NPC scene",
    "sarah" in probe_narration.lower()
    or "stirring" in probe_narration.lower()
    or "table" in probe_narration.lower(),
    f"narration={probe_narration!r}",
))

print("\n=== 3. NPC-initiated NPC->NPC exchanges (small repeated batch) ===")
initiation_inputs = [
    "of his own accord, the old man turns to sarah and tells her the stew is nearly ready",
    "sarah, on her own, mentions to the old man that he should stir the pot more",
    "the old man and sarah start talking to each other about the kitchen, on their own",
]

N_TRIALS = 2
attempted = 0
npc_npc_proposed = 0
npc_npc_executed = 0
self_target_proposed = False
illegal_types = True

mem_before_om = list(old_man.memory)
mem_before_sa = list(sarah.memory)
rel_before_old = dict(old_man.relationships)
rel_before_sa = dict(sarah.relationships)
trial_raises = []

for player_input in initiation_inputs:
    for _ in range(N_TRIALS):
        attempted += 1
        old_input = builtins.input
        builtins.input = lambda _="": ""
        try:
            result = engine.process_input(player_input)
        finally:
            builtins.input = old_input

        call = ai.calls[-1]
        trial_raises.append(call["raw"])
        parsed = parse(call["raw"])
        raw_ok = "__parse_error__" not in parsed
        actions = parsed.get("actions", []) if raw_ok else []

        for action in actions:
            if not action.get("actor"):
                continue

            if action.get("type") not in {"interact", "interact_object"}:
                illegal_types = False

            if action.get("type") == "interact":
                actor = action.get("actor")
                target = action.get("target")

                if actor in {"old_man", "sarah"} and target in {"old_man", "sarah"}:
                    if actor == target:
                        self_target_proposed = True
                    else:
                        npc_npc_proposed += 1

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

results.append(check(
    "Repeated batch produced at least one NPC->NPC proposal",
    npc_npc_proposed > 0,
    f"{npc_npc_proposed} proposed over {attempted} attempts "
    "(real-model nondeterminism); unit suite covers the execution path.",
))
results.append(check(
    "No self-targeted NPC interact was ever proposed",
    not self_target_proposed,
))
results.append(check(
    "At least one NPC->NPC interaction executed successfully",
    npc_npc_executed > 0,
))
results.append(check(
    "AI never proposed an illegal NPC action type",
    illegal_types,
))

new_old = set(old_man.memory) - set(mem_before_om)
new_sa = set(sarah.memory) - set(mem_before_sa)
pair_old_init = any("Old Man spoke to Sarah" in e for e in new_old)
pair_sa_init = any("Sarah spoke to Old Man" in e for e in new_sa)
pair_old_recv = any("Sarah spoke with Old Man" in e for e in new_old)
pair_sa_recv = any("Old Man spoke with Sarah" in e for e in new_sa)
mutual = (pair_old_init and pair_sa_recv) or (pair_sa_init and pair_old_recv)

results.append(check(
    "Conversation recorded on BOTH NPCs (initiation + reception)",
    mutual,
    f"new_old_man={sorted(new_old)!r} new_sarah={sorted(new_sa)!r}",
))
results.append(check(
    "Relationships unchanged after all exchanges",
    dict(old_man.relationships) == rel_before_old
    and dict(sarah.relationships) == rel_before_sa,
))
results.append(check(
    "Object/activity state untouched after all exchanges",
    pot.state == "default"
    and pot.used is False
    and old_man.current_activity_object == "kitchen_stew_pot",
))

print("\n=== 4. Real-model request carried the social grounding ===")
sent_system = " ".join(ai.calls[1]["system"].split())
results.append(check(
    "NPC SOCIAL INTERACTION RULES carried in the real request",
    "NPC SOCIAL INTERACTION RULES:" in ai.calls[1]["system"]
    and "must never target itself" in sent_system,
))
results.append(check(
    "EACH-OWN-STATE grounding carried",
    "each npc in its own supplied state" in sent_system.lower(),
))
results.append(check(
    "No-autonomy rule carried",
    "not autonomous" in sent_system.lower(),
))

print("\n--- Real-model raw responses (small batch) ---")
for i, raw in enumerate(trial_raises, start=1):
    print(f"\nINPUT {i}: {initiation_inputs[(i - 1) // N_TRIALS]!r}")
    print(raw)

engine.close()

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
print(f"  attempted NPC->NPC inputs: {attempted}")
print(f"  NPC->NPC interactions proposed: {npc_npc_proposed}")
print(f"  NPC->NPC interactions executed: {npc_npc_executed}")