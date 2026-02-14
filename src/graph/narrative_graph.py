from typing import Dict, List, Any
from langgraph.graph import StateGraph, END
from ..config import StoryConfig
from ..schemas import StoryState, DialogueTurn
from ..agents.character_agent import CharacterAgent
from ..agents.director_agent import DirectorAgent
from ..story_state import StoryStateManager
from ..actions import validate_action, execute_action, get_action_count


class NarrativeGraph:
    def __init__(self, config: StoryConfig, characters: List[CharacterAgent],
                 director: DirectorAgent):
        self.config = config
        self.characters = {c.name: c for c in characters}
        self.director = director
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(StoryState)

        workflow.add_node("director_select", self._director_select_node)
        workflow.add_node("character_respond", self._character_respond_node)
        workflow.add_node("check_conclusion", self._check_conclusion_node)
        workflow.add_node("conclude", self._conclude_node)

        workflow.set_entry_point("director_select")
        workflow.add_edge("director_select", "character_respond")
        workflow.add_edge("character_respond", "check_conclusion")

        workflow.add_conditional_edges(
            "check_conclusion",
            self._route_conclusion,
            {
                "conclude": "conclude",
                "continue": "director_select"
            }
        )
        workflow.add_edge("conclude", END)

        return workflow.compile()

    def _format_world_state(self, state: StoryState) -> str:
        """Format world_state dict into readable text for prompts."""
        if not state.world_state:
            return "Nothing notable yet."
        lines = []
        for key, value in state.world_state.items():
            # Make keys readable
            readable_key = key.replace("_", " ").title()
            lines.append(f"- {readable_key}: {value}")
        return "\n".join(lines)

    async def _director_select_node(self, state: StoryState) -> Dict:
        """Director selects the next speaker."""
        available = list(self.characters.keys())
        next_speaker, narration = await self.director.select_next_speaker(state, available)

        print("********************************")
        print(f"Director Narration: {narration}")
        print(f"Next Speaker: {next_speaker}")
        print("********************************\n")

        events_update = []
        if narration:
            events_update.append({
                "type": "narration",
                "content": narration,
                "turn": state.current_turn
            })

        return {
            "next_speaker": next_speaker,
            "director_notes": state.director_notes + [f"Selected: {next_speaker}"],
            "story_narration": state.story_narration + [narration] if narration else state.story_narration,
            "events": state.events + events_update
        }

    def _build_character_context(self, state: StoryState, character_name: str) -> str:
        """Build context for a character including goals, inventory, memory, and dialogue."""
        profile = state.character_profiles.get(character_name)

        goals_text = "\n".join(f"- {g}" for g in profile.goals) if profile and profile.goals else "None"
        inventory_text = ", ".join(profile.inventory) if profile and profile.inventory else "Nothing"

        memories = state.character_memories.get(character_name, [])
        memory_text = "\n".join(f"- {m}" for m in memories[-10:]) if memories else "No memories yet."

        recent_turns = state.dialogue_history[-15:]
        history_text = "\n".join([
            f"{turn.speaker}: {turn.dialogue}"
            for turn in recent_turns
        ])

        narration = state.story_narration[-1] if state.story_narration else ""

        # Count actions so far
        action_count = get_action_count(state)

        return f"""Initial Event: {state.seed_story.get('description', 'Unknown event')}

Director Narration: {narration}

Your Goals:
{goals_text}

Your Inventory: {inventory_text}

Your Memory (things you remember):
{memory_text}

Actions taken so far in the story: {action_count}
(The story needs at least 7 actions before it can conclude. Perform physical actions to advance the plot — don't just talk!)

Recent Dialogue and Actions:
{history_text}
"""

    async def _character_respond_node(self, state: StoryState) -> Dict:
        """Selected character generates dialogue and/or action."""
        next_speaker = state.next_speaker

        if not next_speaker or next_speaker not in self.characters:
            next_speaker = list(self.characters.keys())[0]

        character = self.characters[next_speaker]

        # Build context and world state text
        context = self._build_character_context(state, next_speaker)
        world_state_text = self._format_world_state(state)

        # Get structured response (dialogue + optional action)
        dialogue, action = await character.respond(state, context, world_state_text)

        print("********************************")
        print(f"{next_speaker}: {dialogue}")
        if action:
            print(f"  [ACTION] {action.get('type')}" +
                  (f" → {action.get('target')}" if action.get('target') else "") +
                  f" ({action.get('description', '')})")
        print("********************************\n")

        # Build state updates
        new_turn = DialogueTurn(
            turn_number=state.current_turn + 1,
            speaker=next_speaker,
            dialogue=dialogue
        )

        new_events = []
        updated_world = dict(state.world_state)
        updated_memories = dict(state.character_memories)

        # Add dialogue event
        new_events.append({
            "type": "dialogue",
            "speaker": next_speaker,
            "content": dialogue,
            "turn": state.current_turn + 1
        })

        # Process action if present
        if action and isinstance(action, dict) and action.get("type"):
            action_type = action["type"]
            target = action.get("target")
            description = action.get("description", "")

            is_valid, reason = validate_action(action_type, next_speaker, target, state)

            if is_valid:
                # Execute the action
                result = execute_action(action_type, next_speaker, target, description, state)

                updated_world = result["world_state"]
                updated_memories = result["character_memories"]
                action_narration = result["narration"]

                # Add action event
                new_events.append({
                    "type": "action",
                    "speaker": next_speaker,
                    "action_type": action_type,
                    "target": target,
                    "content": action_narration,
                    "description": description,
                    "turn": state.current_turn + 1
                })

                print(f"  >> Action executed: {action_narration}")
            else:
                print(f"  >> Action rejected: {reason}")

        # Update dialogue memory for all characters
        speaker_mem = list(updated_memories.get(next_speaker, []))
        speaker_mem.append(f"Turn {state.current_turn + 1}: I said: {dialogue[:150]}")
        if len(speaker_mem) > 20:
            speaker_mem = speaker_mem[-20:]
        updated_memories[next_speaker] = speaker_mem

        for char_name in state.character_profiles:
            if char_name != next_speaker:
                other_mem = list(updated_memories.get(char_name, []))
                other_mem.append(f"Turn {state.current_turn + 1}: {next_speaker} said: {dialogue[:150]}")
                if len(other_mem) > 20:
                    other_mem = other_mem[-20:]
                updated_memories[char_name] = other_mem

        return {
            "dialogue_history": state.dialogue_history + [new_turn],
            "current_turn": state.current_turn + 1,
            "events": state.events + new_events,
            "character_memories": updated_memories,
            "world_state": updated_world
        }

    async def _check_conclusion_node(self, state: StoryState) -> Dict:
        """Check if story should end. Enforce ≥5 actions AND min_turns."""
        action_count = get_action_count(state)

        # HARD BLOCK: Do not allow conclusion before min_turns
        if state.current_turn < self.config.min_turns:
            return {"is_concluded": False}

        # HARD BLOCK: Do not allow conclusion before 7 actions (need variety)
        if action_count < 7:
            return {"is_concluded": False}

        # Force conclusion at max_turns
        if state.current_turn >= self.config.max_turns:
            return {
                "is_concluded": True,
                "conclusion_reason": "Maximum turns reached."
            }

        should_end, reason = await self.director.check_conclusion(state)

        if should_end:
            events_update = []
            if reason:
                events_update.append({
                    "type": "narration",
                    "content": reason,
                    "turn": state.current_turn,
                    "metadata": {"conclusion": True}
                })

            return {
                "is_concluded": True,
                "conclusion_reason": str(reason),
                "events": state.events + events_update
            }
        return {"is_concluded": False}

    async def _conclude_node(self, state: StoryState) -> Dict:
        """Finalize story with proper ending narration."""
        conclusion = state.conclusion_reason or "The story has concluded."

        print("\n" + "=" * 60)
        print("STORY CONCLUSION")
        print("=" * 60)
        print(conclusion)
        print("=" * 60 + "\n")

        return {"is_concluded": True}

    def _route_conclusion(self, state: StoryState) -> str:
        if state.is_concluded:
            return "conclude"
        return "continue"

    async def run(self, seed_story: Dict, character_profiles: Dict[str, Any] = None,
                  character_memories: Dict[str, list] = None) -> StoryState:
        """Execute the narrative game loop."""
        initial_state = StoryState(
            seed_story=seed_story,
            character_profiles=character_profiles or {},
            dialogue_history=[],
            director_notes=[],
            character_memories=character_memories or {},
            world_state={}
        )

        final_state = await self.graph.ainvoke(initial_state)
        return final_state
