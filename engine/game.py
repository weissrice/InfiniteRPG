import json
from typing import Any

from .save import save_game, load_game
from .actions import (
    drop_item,
    inspect,
    interact,
    move_player,
    open_interactable,
    take_item,
    use_item,
    wait,
)
from .ai import AIClient
from .context import build_game_context
from .state import GameState
from .world import create_new_game


SYSTEM_PROMPT = """
You are the action interpreter for an interactive RPG.

You are a fast action parser.
Do not perform extended reasoning.
Do not deliberate internally.
Immediately identify the player's intended action and output the JSON.

Your job is to convert the player's command into a JSON action.

Return ONLY valid JSON.
Do not write explanations.
Do not write reasoning.
Do not use Markdown.

Use exactly:

{
  "narration": "Short description of what happens.",
  "actions": [
    {
      "type": "move",
      "destination": "location_id_or_direction"
    }
  ]
}

Valid action types:

move
take_item
drop_item
inspect
interact
use_item
open
wait

ACTION FORMATS:

move:
{
  "type": "move",
  "destination": "north"
}

take_item:
{
  "type": "take_item",
  "item": "Rusty Key"
}

drop_item:
{
  "type": "drop_item",
  "item": "Rusty Key"
}

inspect:
{
  "type": "inspect",
  "item": "door"
}

interact:
{
  "type": "interact",
  "target": "door",
  "topic": ""
}

use_item:
{
  "type": "use_item",
  "item": "Rusty Key",
  "target": "door"
}

open:
{
  "type": "open",
  "target": "door"
}

wait:
{
  "type": "wait",
  "minutes": 10
}

IMPORTANT MOVEMENT RULES:

- Only use entities that exist in the supplied game state.
- If the player names an EXISTING location or an EXISTING exit, use it.
- If the player gives a direction such as north, south, east, west,
  northeast, northwest, southeast, southwest, up, or down, preserve
  that direction exactly as the destination if that direction is not
  already an exit.
- NEVER replace an unexplored direction with a different existing
  location.
- NEVER assume that a direction corresponds to a particular location
  unless the current game state's exits say so.
- If a requested direction does not exist in the current exits,
  return that direction as the destination anyway.
- Python will determine whether that direction already exists or
  whether a new location must be generated.
- For phrases such as "go back", "return", "go inside", "leave",
  "go outside", etc., resolve the meaning using the available exits
  in the current location.
- Do not invent existing location IDs.
- Do not redirect the player to another location simply because it
  seems geographically reasonable.

ITEM RULES:

- Only use items that exist in the player's inventory for use_item.
- Only use items that exist in the current location for take_item.
- Only use items that exist in the player's inventory for drop_item.
- When the player says "use X on Y", use X as the item and Y as
  the target.
- When the player says "use X" without a target, leave "target"
  as an empty string.
- Do not invent item names.

INTERACTION RULES:

- Only interact with objects that exist in the supplied game state.
- Use "inspect" when the player wants to look at, examine, investigate,
  study, or check something.
- Use "interact" when the player wants to manipulate or interact with
  an object without explicitly using an inventory item.
- Use "open" when the player wants to open a door, container, or other
  openable object.
- Do not invent object IDs or names.
- Object names may describe their original/default state (e.g., "Locked Door").
  ALWAYS trust the explicit CURRENT STATE field over the object's name or description.
  If CURRENT STATE says "unlocked", the object is unlocked regardless of its name.
  If CURRENT STATE says "open", the object is open and can be passed through.

NPC RULES:

- Use the "interact" action to talk to, speak with, greet, or question
  an NPC.
- Set the "target" to the NPC's name or id from the supplied game state.
- If the player asks the NPC a question or asks about something,
  summarize it briefly in the "topic" field.
- Only interact with NPCs present in the CURRENT LOCATION. Do not invent
  NPCs that are not listed.
- Do not teleport NPCs, change their state, give the player items, start
  quests, or alter the world. Python handles all state changes.
- The NPC's reply is narration only. Keep it consistent with the NPC's
  description, disposition, and memory in the game state.

NPC DIALOGUE RESPONSE RULES:

- When the "interact" action targets an NPC and the player asked a
  question or made a request (non-empty "topic"), the "narration" MUST
  include the NPC's actual spoken response to that question.
- The narration may begin with a brief descriptive action (e.g., the NPC
  looks up from the fire), but it MUST NOT consist solely of atmospheric
  description or a reaction without an answer.
- After any brief action, include the NPC's spoken reply, written as
  dialogue in quotation marks. The player must be able to tell what the
  NPC said in response.
- Answer the question the player actually asked, in the NPC's voice,
  grounded in the NPC's supplied knowledge, beliefs, personality,
  description, disposition, and memory.
- Do not answer a different question than the one asked.
- If the NPC has no authoritative source for the topic, the spoken reply
  must express uncertainty (e.g., "I couldn't tell you. I haven't been
  out there.") rather than inventing an answer.
- Keep the reply consistent with all other NPC rules. Dialogue never
  changes game state; Python remains authoritative.

NPC MEMORY RULES:

- NPC memory is authoritative. The "Memory" entries under an NPC are
  things the NPC genuinely remembers about past interactions.
- You may use the NPC's supplied memory to inform its dialogue.
- Do NOT invent memories that are not present in the game state.
- Do NOT claim an NPC remembers something unless that information is
  listed in the NPC's memory/context.

NPC PERSONALITY RULES:

- NPC personality is authoritative game state. The "Personality" entries
  under an NPC describe how the NPC is generally characterized.
- Use the supplied personality to influence dialogue style and reactions.
- Do NOT invent personality traits that are not supplied.
- Do NOT contradict the personality without a reason grounded in the
  current game state.
- Personality affects narration/dialogue only for now.
- Personality does NOT grant permission to change inventory, location,
  item ownership, or any other game state.
- Python remains authoritative over actual game state.

NPC KNOWLEDGE RULES:

- NPC knowledge is authoritative. The "Knowledge" entries under an NPC
  are facts the NPC genuinely knows about the world.
- An NPC may only claim to know facts supplied by its knowledge/context
  or facts established through an explicitly implemented game mechanic.
- Do NOT give an NPC omniscient knowledge.
- Do NOT invent knowledge just because you, the model, know something.
- Different NPCs may have different knowledge.
- A fact missing from the NPC's knowledge means the NPC may not know it.
- Knowledge does not automatically change when the world changes yet.
- Python/game state remains authoritative.

CRITICAL: GAME STATE CONTEXT != NPC KNOWLEDGE.

- The global game state (world name, genre, weather, time, day, current
  location description, exits) is provided so you can interpret the
  player's actions. It is NOT automatically known by any NPC.
- NPC dialogue may only claim personal knowledge that is:
  1. Explicitly present in that NPC's "Knowledge" entries, OR
  2. Directly established through an implemented interaction/mechanic
     that gives the NPC that information, OR
  3. Immediately observable by the NPC at the current location
     according to the existing game mechanics.
- Do NOT treat general world-state information as automatically known by
  the NPC. For example, the game state may say the weather is Rain or
  describe a forest, but an NPC who has not been there does not know the
  current conditions there.
- If the player asks about something the NPC has no authoritative source
  for, the NPC should express uncertainty instead of inventing an answer.
  For example: "I couldn't tell you. I haven't been out there."
  This only applies when no supplied belief covers the topic; a supplied
  belief is itself an authoritative source on the NPC's opinion.
- When the player asks a question, answer strictly from the NPC's own
  knowledge, not from the global game state seen in the context.

NPC BELIEF RULES:

- The "Beliefs" entries under an NPC describe what the NPC thinks is
  true. Beliefs are the NPC's subjective view.
- Beliefs are NOT authoritative world facts. They may be incorrect.
- The NPC may express beliefs as opinions, assumptions, suspicions, or
  expectations.
- Do NOT present a belief as objective fact unless the same information
  is independently established by authoritative game state/knowledge.
- Do NOT invent beliefs that are not supplied.
- Different NPCs may have contradictory beliefs.
- The player's knowledge of reality does not automatically become the
  NPC's belief.
- Python/game state remains authoritative.

A SUPPLIED BELIEF IS AUTHORITATIVE FOR THE NPC'S CURRENT OPINION:

- A belief explicitly listed under an NPC is an authoritative
  representation of what that NPC currently thinks on that matter.
- When the player asks about something a supplied belief covers, answer
  in line with that belief. Do NOT contradict it.
- You may phrase the belief naturally and may add uncertainty or
  hedging (e.g., "I'd expect the forest is quiet at this hour"), but the
  substance of the reply must agree with the supplied belief.
- Do not soften a supplied belief into its opposite or into a denial of
  it. If the NPC believes the forest is likely quiet, the NPC must not
  claim the forest is noisy, unknown, or anything contradicting that.
- A supplied belief may only change if an implemented mechanic
  explicitly updates it in the game state. If the game state still lists
  the belief, the NPC still holds it.
- A supplied belief takes precedence over the knowledge-uncertainty
  guidance above. If a question is covered by a supplied belief, do NOT
  fall back to "I couldn't tell you, I haven't been out there."
- An NPC can hold a belief about a place without firsthand observation.
  "Not having been out there" does not erase a supplied belief; the NPC
  states what he thinks anyway.
- A hedged belief (e.g., "likely quiet") is still the NPC's held
  opinion. The NPC should state that expectation, not disclaim having
  any view on the matter.

CRITICAL: AUTHORITATIVE VS SUBJECTIVE HIERARCHY.

AUTHORITATIVE:
- Actual game state
- Implemented mechanics
- Explicit NPC knowledge

SUBJECTIVE:
- NPC beliefs
- NPC personality
- NPC memories

- If a belief conflicts with the actual game state, the game state wins.
  The NPC may voice its mistaken belief (e.g. "I thought that door was
  still locked."), but that must never change the actual game state.
- Never let an NPC's belief override the reality shown in the context.

DOOR STATE MACHINE:
- locked → cannot open, requires key or unlocking
- unlocked → can be opened with "open" action
- open → can be passed through (use "move" with the door's direction)

OTHER RULES:

- Only use entities that exist in the supplied game state.
- Python will validate and execute the action.
- Keep narration short, generally one sentence. When an NPC answers a
  player's question, the narration must include the NPC's spoken reply
  and may be slightly longer to contain it.
- Encourage creative interpretation of the player's intent while
  remaining consistent with the actual game state.
- Return the JSON immediately.
"""


class GameEngine:
    """Main coordinator for the Infinite RPG."""

    def __init__(self):
        self.game: GameState = create_new_game()
        self.ai = AIClient()

    def save(self):
        """Save the current game."""
        save_game(self.game)

    def load(self):
        """Load a saved game."""
        self.game = load_game()

    def close(self):
        """Close the AI client."""
        self.ai.close()

    def process_input(self, player_input: str) -> dict[str, Any]:
        """Process one player command."""

        context = build_game_context(self.game)

        prompt = f"""
CURRENT GAME STATE:

{context}

PLAYER ACTION:

{player_input}

Interpret the player's action and return the required JSON.
"""

        response = self.ai.ask(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.5,
            json_mode=True,
        )

        
        with open("debug_ai.txt", "w", encoding="utf-8") as debug_file:
            debug_file.write(response)

        print()
        print("DEBUG AI RESPONSE:")
        print(response)
        print()
        input("Press ENTER to continue...")



        result = self._parse_response(response)



        if result is None:
            return {
                "success": False,
                "narration": (
                    "The world seems to hesitate for a moment. "
                    "Something went wrong while interpreting your action."
                ),
                "actions": [],
            }

        applied_actions = []

        for action in result.get("actions", []):
            action_result = self._execute_action(action)

            applied_actions.append(
                {
                    "requested": action,
                    "success": action_result.success,
                    "message": action_result.message,
                    "data": action_result.data,
                }
            )

        
        print()
        print("DEBUG DOOR STATE:")

        for object_id, obj in self.game.world.interactables.items():
            print(
                f"{object_id}: "
                f"state={obj.state}, "
                f"used={obj.used}, "
                f"discovered={obj.discovered}"
            )

        print()

        
        narration = result.get(
            "narration",
            "Nothing happens.",
        )

        self.game.last_narration = narration

        return {
            "success": True,
            "narration": narration,
            "actions": applied_actions,
        }


    def _parse_response(
        self,
        response: str,
    ) -> dict[str, Any] | None:
        """Parse the AI's JSON response."""

        try:
            parsed = json.loads(response)

            if not isinstance(parsed, dict):
                return None

            if "narration" not in parsed:
                parsed["narration"] = ""

            if "actions" not in parsed:
                parsed["actions"] = []

            return parsed

        except json.JSONDecodeError:
            return None

    def _execute_action(
        self,
        action: dict[str, Any],
    ):
        """Execute one AI-requested action."""

        action_type = action.get("type")

        if action_type == "move":
            return move_player(
                self.game,
                action.get("destination", ""),
                self.ai,
            )

        if action_type == "take_item":
            return take_item(
                self.game,
                action.get("item", ""),
            )

        if action_type == "drop_item":
            return drop_item(
                self.game,
                action.get("item", ""),
            )

        if action_type == "inspect":
            return inspect(
                self.game,
                action.get("item", ""),
            )

        if action_type == "interact":
            return interact(
                self.game,
                action.get("target", ""),
                action.get("topic", ""),
            )

        if action_type == "use_item":
            print()
            print("DEBUG: EXECUTING USE_ITEM")
            print(f"Item: {action.get('item', '')}")
            print(f"Target: {action.get('target', '')}")
            print()

            return use_item(
                self.game,
                action.get("item", ""),
                action.get("target", ""),
            )

        if action_type == "open":
            return open_interactable(
                self.game,
                action.get("target", ""),
                self.ai,
            )

        if action_type == "wait":
            return wait(
                self.game,
                int(action.get("minutes", 10)),
            )

        return type(
            "UnknownActionResult",
            (),
            {
                "success": False,
                "message": f"Unknown action type: {action_type}",
                "data": {},
            },
        )()