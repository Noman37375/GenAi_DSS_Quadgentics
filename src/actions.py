"""
Action System for GenAI_DSS Multi-Agent Narrative.

Defines scenario-specific actions, validates them, and executes them
by updating world_state and character inventories.
"""

from typing import Dict, List, Optional, Tuple
from .schemas import StoryState

# Valid action types for the Rickshaw Accident scenario
VALID_ACTIONS = {
    "Give_Money": {
        "description": "Hand over money to someone",
        "requires_target": True,
        "effects": "Transfers money from actor's inventory to target"
    },
    "Offer_Bribe": {
        "description": "Offer chai-pani / bribe to someone",
        "requires_target": True,
        "effects": "Sets bribe_offered flag; target must respond"
    },
    "Write_Challan": {
        "description": "Write an official traffic challan/ticket",
        "requires_target": True,
        "effects": "Official record created; pressure on target"
    },
    "Confiscate_Keys": {
        "description": "Take someone's vehicle keys as leverage",
        "requires_target": True,
        "effects": "Target loses keys; cannot leave"
    },
    "Record_Video": {
        "description": "Start recording the scene on phone",
        "requires_target": False,
        "effects": "Everyone becomes aware they are being recorded"
    },
    "Block_Vehicle": {
        "description": "Physically block a vehicle from leaving",
        "requires_target": True,
        "effects": "Target's vehicle cannot move"
    },
    "Show_Item": {
        "description": "Show an item to prove a point (empty wallet, damage, ID)",
        "requires_target": False,
        "effects": "Others see the item and react"
    },
    "Call_Contact": {
        "description": "Call someone on phone (inspector, lawyer, family)",
        "requires_target": False,
        "effects": "Outside authority is now involved"
    },
    "Offer_Chai": {
        "description": "Offer or bring chai to de-escalate",
        "requires_target": False,
        "effects": "Social gesture; tension may reduce"
    },
    "Sit_On_Ground": {
        "description": "Sit on the ground in protest/despair",
        "requires_target": False,
        "effects": "Emotional pressure on others; crowd sympathy increases"
    },
}


def get_available_actions_text() -> str:
    """Return a formatted string of available actions for prompts."""
    lines = []
    for action_type, info in VALID_ACTIONS.items():
        target_note = "(requires target)" if info["requires_target"] else "(no target needed)"
        lines.append(f"- {action_type}: {info['description']} {target_note}")
    return "\n".join(lines)


def validate_action(action_type: str, actor: str, target: Optional[str],
                    state: StoryState) -> Tuple[bool, str]:
    """Validate whether an action is allowed."""
    if action_type not in VALID_ACTIONS:
        return False, f"Unknown action type: {action_type}"

    action_info = VALID_ACTIONS[action_type]

    if action_info["requires_target"] and not target:
        return False, f"{action_type} requires a target"

    if target and target not in state.character_profiles:
        return False, f"Unknown target: {target}"

    if actor == target:
        return False, "Cannot target yourself"

    return True, "Valid"


def execute_action(action_type: str, actor: str, target: Optional[str],
                   description: str, state: StoryState) -> Dict:
    """
    Execute an action and return state updates.

    Returns a dict with keys: world_state, character_memories, narration
    """
    updated_world = dict(state.world_state)
    updated_memories = dict(state.character_memories)
    narration = ""

    if action_type == "Give_Money":
        updated_world["money_exchanged"] = True
        updated_world["money_from"] = actor
        updated_world["money_to"] = target
        narration = f"{actor} hands over money to {target}."

    elif action_type == "Offer_Bribe":
        updated_world["bribe_offered"] = True
        updated_world["bribe_from"] = actor
        updated_world["bribe_to"] = target
        narration = f"{actor} subtly offers chai-pani to {target}."

    elif action_type == "Write_Challan":
        updated_world["challan_written"] = True
        updated_world["challan_target"] = target
        narration = f"{actor} pulls out the challan book and begins writing a ticket for {target}."

    elif action_type == "Confiscate_Keys":
        updated_world["keys_confiscated"] = True
        updated_world["keys_taken_from"] = target
        narration = f"{actor} snatches {target}'s vehicle keys."

    elif action_type == "Record_Video":
        updated_world["being_recorded"] = True
        updated_world["recorder"] = actor
        narration = f"{actor} pulls out a phone and starts recording the whole scene."

    elif action_type == "Block_Vehicle":
        updated_world["vehicle_blocked"] = True
        updated_world["vehicle_blocked_owner"] = target
        narration = f"{actor} physically blocks {target}'s vehicle, preventing them from leaving."

    elif action_type == "Show_Item":
        updated_world[f"{actor}_showed_item"] = True
        narration = f"{actor} shows something to prove a point — {description}"

    elif action_type == "Call_Contact":
        updated_world[f"{actor}_called_contact"] = True
        narration = f"{actor} pulls out a phone and makes a call — {description}"

    elif action_type == "Offer_Chai":
        updated_world["chai_offered"] = True
        narration = f"{actor} sends for chai, trying to calm everyone down."

    elif action_type == "Sit_On_Ground":
        updated_world[f"{actor}_sitting_on_ground"] = True
        narration = f"{actor} slumps down on the road in despair, drawing sympathy from the crowd."

    # Update memory for all characters about the action
    action_fact = f"[ACTION] {actor}: {action_type}" + (f" → {target}" if target else "") + f" ({description})"
    for char_name in state.character_profiles:
        char_mem = list(updated_memories.get(char_name, []))
        char_mem.append(action_fact)
        if len(char_mem) > 20:
            char_mem = char_mem[-20:]
        updated_memories[char_name] = char_mem

    return {
        "world_state": updated_world,
        "character_memories": updated_memories,
        "narration": narration
    }


def get_action_count(state: StoryState) -> int:
    """Count how many action events have occurred so far."""
    return sum(1 for e in state.events if e.get("type") == "action")
