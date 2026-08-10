import json
from pathlib import Path
from typing import Any

from .save import save_game, load_game
from .actions import (
    accept_quest,
    abandon_quest,
    allocate_stat,
    attack,
    buy_item,
    craft,
    decline_quest,
    drop_item,
    inspect,
    interact,
    move_player,
    npc_interact,
    npc_interact_object,
    offer_quest,
    open_interactable,
    record_conversation_response,
    sell_item,
    take_item,
    tick_npc_autonomy,
    update_npc_local_movement,
    use_item,
    wait,
)
from .ai import AIClient
from .context import build_game_context
from .state import GameState
from .world import create_new_game
from .world_gen import generate_world_content



_PROMPT_FILE = Path(__file__).resolve().parent.parent / "assets" / "system_prompt.txt"


def _load_system_prompt() -> str:
    """Load the system prompt from the external resource file."""
    return _PROMPT_FILE.read_text(encoding="utf-8")


SYSTEM_PROMPT = _load_system_prompt()


class SimulationClock:
    """Tracks elapsed simulation ticks.

    This is a minimal, deterministic clock that advances when the player
    performs time-consuming actions. It contains no scheduling, LOD, or
    event functionality.
    """

    def __init__(self):
        self._ticks: int = 0

    @property
    def ticks(self) -> int:
        """Return the total elapsed simulation ticks."""
        return self._ticks

    def advance(self, ticks: int = 1) -> None:
        """Advance the clock by the given number of ticks.

        Args:
            ticks: Number of ticks to advance. Must be positive.
        """
        if ticks < 1:
            return
        self._ticks += ticks


class GameEngine:
    """Main coordinator for the Infinite RPG."""

    def __init__(self):
        self.game: GameState = create_new_game()
        self.ai = AIClient()
        self.clock = SimulationClock()

    def save(self):
        """Save the current game."""
        save_game(self.game)

    def load(self):
        """Load a saved game."""
        self.game = load_game()

    def close(self):
        """Close the AI client."""
        self.ai.close()

    def tick_npc_movement(self):
        """Tick NPC local movement for the current location.

        Should be called once after each successful player local
        movement action.
        """
        update_npc_local_movement(self.game)

    def step_turn(self, ticks: int = 1) -> list[str]:
        """Advance the simulation by one turn.

        Advances the clock first, then ticks NPC local movement,
        then processes autonomous NPC actions.

        This is the unified entry point for simulation time progression.

        Args:
            ticks: Number of ticks to advance. Defaults to 1. If 0 or negative,
                no simulation time passes.

        Returns:
            List of narration strings from autonomous NPC actions.
        """
        if ticks < 1:
            return []
        self.clock.advance(ticks)
        self.tick_npc_movement()
        return tick_npc_autonomy(self.game)

    def process_input(self, player_input: str) -> dict[str, Any]:
        """Process one player command."""

        context = build_game_context(self.game)

        prompt = f"""
CURRENT GAME STATE:

{context}

PLAYER ACTION:

{player_input}

You are the Game Master. Narrate what happens based on the game state and the player's action.
Return the JSON with your narration and any mechanical actions.
"""

        response = self.ai.ask(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=4096,
            temperature=0.6,
            json_mode=True,
        )

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
        player_moved_locally = False

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

            if action_result.success and action.get("type") == "move":
                player_moved_locally = True

        # Advance simulation turn once after a successful player move
        if player_moved_locally:
            self.step_turn()

        narration = result.get(
            "narration",
            "Nothing happens.",
        )

        for action in result.get("actions", []):
            if action.get("type") == "interact" and not action.get("actor"):
                topic = action.get("topic", "")

                if topic.strip():
                    record_conversation_response(
                        self.game,
                        action.get("target", ""),
                        narration,
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
        actor = action.get("actor")

        if actor:
            return self._execute_npc_action(action)

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

        if action_type == "attack":
            return attack(
                self.game,
                "player",
                action.get("target", ""),
                action.get("weapon", ""),
            )

        if action_type == "offer_quest":
            return offer_quest(
                self.game,
                action.get("actor", ""),
                action.get("quest_id", ""),
                action.get("title", ""),
                action.get("description", ""),
                action.get("objectives", []),
                action.get("rewards"),
            )

        if action_type == "accept_quest":
            return accept_quest(
                self.game,
                action.get("quest_id", ""),
            )

        if action_type == "decline_quest":
            return decline_quest(
                self.game,
                action.get("quest_id", ""),
            )

        if action_type == "abandon_quest":
            return abandon_quest(
                self.game,
                action.get("quest_id", ""),
            )

        if action_type == "allocate_stat":
            return allocate_stat(
                self.game,
                action.get("stat", ""),
                action.get("amount", 1),
            )

        if action_type == "craft":
            return craft(
                self.game,
                action.get("recipe_id", ""),
            )

        if action_type == "buy_item":
            return buy_item(
                self.game,
                action.get("npc", ""),
                action.get("item", ""),
                action.get("quantity", 1),
            )

        if action_type == "sell_item":
            return sell_item(
                self.game,
                action.get("npc", ""),
                action.get("item", ""),
                action.get("quantity", 1),
            )

        if action_type == "generate_world":
            travel_dest = action.get("travel_destination", False)
            result = generate_world_content(
                game=self.game,
                ai=self.ai,
                reference_location_id=action.get(
                    "reference", self.game.player.location,
                ),
                direction=action.get("direction", "east"),
                context_hint=action.get("hint", ""),
            )

            if result.success and result.location:
                # Create a LocalMap for the generated location
                from engine.local_map import generate_local_map, validate_local_map, _place_npcs_and_interactables
                lm = generate_local_map(result.location)
                # Place NPCs and interactables before validation
                _place_npcs_and_interactables(
                    lm, result.location,
                    self.game.world.npcs, self.game.world.interactables,
                )
                if validate_local_map(lm, list(self.game.world.npcs.values()), list(self.game.world.interactables.values()), location_id=result.location.id):
                    self.game.local_maps[result.location.id] = lm
                else:
                    # Fallback: create a minimal valid map
                    lm = generate_local_map(result.location)
                    self.game.local_maps[result.location.id] = lm

                # Also ensure the reference location has a LocalMap
                if result.location.id not in self.game.local_maps:
                    ref_loc = self.game.world.locations.get(
                        action.get("reference", self.game.player.location)
                    )
                    if ref_loc and ref_loc.id not in self.game.local_maps:
                        ref_lm = generate_local_map(ref_loc)
                        self.game.local_maps[ref_loc.id] = ref_lm

            if travel_dest and result.success and result.location:
                self.game.player.location = result.location.id
                self.game.visited_locations.add(result.location.id)
                # Set player spawn position in the new location
                new_lm = self.game.local_maps.get(result.location.id)
                if new_lm:
                    self.game.player.local_x = new_lm.spawn[0]
                    self.game.player.local_y = new_lm.spawn[1]

            return type(
                "GenResult",
                (),
                {
                    "success": result.success,
                    "message": (
                        f"You discover {result.location.name}."
                        if result.location
                        else result.error
                    ),
                    "data": {
                        "location": result.location.id if result.location else None,
                        "generated": result.success,
                        "moved": travel_dest and result.success,
                    },
                },
            )()

        return type(
            "UnknownActionResult",
            (),
            {
                "success": False,
                "message": f"Unknown action type: {action_type}",
                "data": {},
            },
        )()

    def _execute_npc_action(
        self,
        action: dict[str, Any],
    ):
        """Execute one NPC-proposed action (V1: interact, interact_object, attack)."""

        action_type = action.get("type")

        if (
            action_type != "interact"
            and action_type != "interact_object"
            and action_type != "attack"
        ):
            return type(
                "NpcActionNotAllowed",
                (),
                {
                    "success": False,
                    "message": (
                        f"NPCs cannot perform action type: {action_type}"
                    ),
                    "data": {},
                },
            )()

        if action_type == "interact":
            return npc_interact(
                self.game,
                action.get("actor", ""),
                action.get("target", ""),
                action.get("topic", ""),
                action.get("knowledge_transfer", ""),
                action.get("belief_transfer", ""),
                action.get("goal_transfer", ""),
            )

        if action_type == "attack":
            return attack(
                self.game,
                action.get("actor", ""),
                action.get("target", ""),
                action.get("weapon", ""),
            )

        return npc_interact_object(
            self.game,
            action.get("actor", ""),
            action.get("target", ""),
        )