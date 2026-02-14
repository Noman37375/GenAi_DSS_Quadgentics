from ..schemas import CharacterProfile
from ..actions import get_available_actions_text

def get_character_prompt(character_name: str, character_profile: CharacterProfile,
                         context: str, config, world_state_text: str = "",
                         available_actions: str = "") -> str:

    if not available_actions:
        available_actions = get_available_actions_text()

    return f"""You are {character_name}, a character in a street scene in Karachi, Pakistan.
Your Personality: {character_profile.description}

{context}

World State (what has happened so far):
{world_state_text if world_state_text else "Nothing notable yet."}

IMPORTANT GUIDELINES:
- You are on a busy Karachi road during rush hour. Act like a REAL person on a Karachi street — not a drama character.
- Use natural Urdu-English mix (Roman Urdu). Speak the way real people speak on Karachi streets.
- You can TALK (say dialogue) or ACT (do a physical action) or BOTH in one turn.
- Physical actions matter: blocking a car, grabbing keys, sitting on the ground, pulling out your phone to record — these change the situation more than words alone.
- React to the crowd around you. The crowd is watching, judging, taking sides. Use them. Appeal to them. Fear them.
- React to the world state above — if someone took an action, you must acknowledge and respond to it.

Available Actions you can perform:
{available_actions}

You MUST respond with valid JSON ONLY in this exact format:
{{
    "reasoning": "brief internal thought about what to do next (1 sentence)",
    "decision": "talk" or "act" or "both",
    "dialogue": "your spoken words (or null if only acting)",
    "action": {{
        "type": "ActionType from the list above",
        "target": "character name or null",
        "description": "brief description of what you do"
    }} or null if only talking
}}

Keep dialogue under {config.max_dialogue_length} tokens. Respond with JSON ONLY, no extra text.
"""
