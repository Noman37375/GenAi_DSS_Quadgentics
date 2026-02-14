import json
from typing import List, Tuple, Optional
from .base_agent import BaseAgent
from ..config import StoryConfig
from ..schemas import StoryState
from ..actions import get_action_count
from ..prompts.director_prompts import DIRECTOR_SELECT_SPEAKER_PROMPT, DIRECTOR_CONCLUSION_PROMPT


class DirectorAgent(BaseAgent):
    def __init__(self, config: StoryConfig):
        super().__init__("Director", config)

    def _format_world_state(self, state: StoryState) -> str:
        """Format world_state for prompt."""
        if not state.world_state:
            return "Nothing notable yet."
        lines = []
        for key, value in state.world_state.items():
            readable_key = key.replace("_", " ").title()
            lines.append(f"- {readable_key}: {value}")
        return "\n".join(lines)

    async def select_next_speaker(self, story_state: StoryState,
                                   available_characters: List[str]) -> str:
        """Decide who speaks next."""
        if story_state.dialogue_history:
            recent_dialogue = "\n".join(
                f"{turn.speaker}: {turn.dialogue}"
                for turn in story_state.dialogue_history[-5:]
            )
        else:
            recent_dialogue = "No dialogue yet. The story is just starting. Select the character most likely to speak first based on the Context."

        # Build character descriptions with goals
        char_lines = []
        for name in available_characters:
            profile = story_state.character_profiles.get(name)
            if profile:
                goals_str = ", ".join(profile.goals) if profile.goals else "none"
                char_lines.append(f"- {name}: {profile.description} (Goals: {goals_str})")
            else:
                char_lines.append(f"- {name}")
        character_descriptions = "\n".join(char_lines)

        prompt = DIRECTOR_SELECT_SPEAKER_PROMPT.format(
            description=story_state.seed_story.get('description', ''),
            world_state_text=self._format_world_state(story_state),
            recent_dialogue=recent_dialogue,
            character_descriptions=character_descriptions,
            action_count=get_action_count(story_state),
            max_consecutive=self.config.max_consecutive_same_character
        )

        response = await self.generate_response(prompt)

        try:
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            next_speaker = data.get("next_speaker")
            narration = data.get("narration")

            if next_speaker not in available_characters:
                next_speaker = available_characters[0]

            # HARD ENFORCEMENT: prevent same speaker more than max_consecutive times in a row
            max_consec = self.config.max_consecutive_same_character
            if len(story_state.dialogue_history) >= max_consec:
                last_speakers = [t.speaker for t in story_state.dialogue_history[-max_consec:]]
                if all(s == next_speaker for s in last_speakers):
                    # Force a different speaker
                    alternatives = [c for c in available_characters if c != next_speaker]
                    if alternatives:
                        forced = alternatives[0]
                        print(f"  [Anti-Repetition] Blocked {next_speaker} (spoke {max_consec}x in a row), forcing {forced}")
                        next_speaker = forced

            return next_speaker, narration

        except Exception as e:
            print(f"Error parsing director selection: {e}")
            print(f"Raw response: {response}")
            return available_characters[0], ""

    async def check_conclusion(self, story_state: StoryState) -> Tuple[bool, Optional[str]]:
        """Check if the story should end."""
        action_count = get_action_count(story_state)

        # Build character descriptions for conclusion context
        char_lines = []
        for name, profile in story_state.character_profiles.items():
            if profile:
                goals_str = ", ".join(profile.goals) if profile.goals else "none"
                char_lines.append(f"- {name}: {profile.description[:100]}... (Goals: {goals_str})")
        character_descriptions = "\n".join(char_lines)

        prompt = DIRECTOR_CONCLUSION_PROMPT.format(
            story_summary=f"Context: {story_state.seed_story.get('description', '')}\nLast Turns:\n" +
                          "\n".join([f"{t.speaker}: {t.dialogue}" for t in story_state.dialogue_history[-8:]]),
            world_state_text=self._format_world_state(story_state),
            character_descriptions=character_descriptions,
            current_turn=story_state.current_turn,
            max_turns=self.config.max_turns,
            min_turns=self.config.min_turns,
            action_count=action_count
        )

        response = await self.generate_response(prompt)

        try:
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            return data.get("should_end", False), data.get("conclusion_narration")
        except Exception as e:
            print(f"Error parsing director conclusion: {e}")
            return False, None
