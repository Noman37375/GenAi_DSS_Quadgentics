# Implementation Guide: GenAI_DSS Multi-Agent Narrative System

This document is a step-by-step implementation plan to meet the **Gen_AI_Problem_Statement.md** and **Evaluation_Rubric.md** requirements. Use it as a checklist and reference while extending the codebase.

---

## 1. Overview

### Required by Problem Statement (Section 3.3)

| Component | Description | Current Status |
|-----------|-------------|----------------|
| **Character Memory** | Individual memory buffers: knowledge, inventory, perceptions of others | Missing (only recent dialogue used) |
| **Action System** | Non-verbal actions that update Story State (e.g. Search, Trade, Unlock) | Missing (dialogue only) |
| **Reasoning Layer** | Agents decide whether to **Talk** or **Act** | Missing |

### Constraints to Respect

- **Max 25 turns** (already in `config.max_turns`)
- **At least 5 distinct Actions** per run (must enforce after implementing actions)
- **Context length** and **max_tokens_per_prompt** (see `src/config.py`)

### Rubric Priorities (Marks)

1. **Working System (25)** — README + one-command run
2. **Documentation & Report (20)** — README + Technical Report (PDF/LaTeX)
3. **Feature Implementation (15)** — Memory + Actions + Reasoning
4. **JSON Compliance (15)** — Correct `story_output.json` and `prompts_log.json`
5. **Q/A (15)** — Prepare to explain architecture
6. **Story Quality (10)** — Coherence via actions and tuning

---

## 2. Implementation Order

Recommended sequence (dependencies first):

1. **Schemas & config** — Extend profiles (goals, inventory); define action types
2. **Character memory** — Per-character memory store and prompt integration
3. **Action schema & execution** — Define actions, update state, emit events
4. **Reasoning layer** — Talk vs Act decision; branch in graph
5. **Output & docs** — Top-level `conclusion`, README, Technical Report
6. **Enforce ≥5 actions** — Logic so story does not end before 5 actions

---

## 3. Feature 1: Character Memory

### Goal

Per-character memory: **knowledge**, **inventory**, and **perceptions of others** (Problem Statement 3.3).

### 3.1 Current conversation dialogue context (own + other party)

**Purpose:** When a character’s turn comes, provide structured context so responses stay logical and consistent:
- **This character’s own previous dialogues** in the current conversation only.
- **The other party’s previous dialogues** in the current conversation only (the person they are talking to, e.g. last speaker or primary interlocutor).

Right now the code sends one mixed “Recent Dialogue” (everyone’s last N turns). Splitting into “your lines” and “their lines” improves coherence.

**Steps:**

1. **Use existing `dialogue_history`** — No new storage needed; filter `state.dialogue_history` (current conversation) by speaker.
2. **Build two context sections when building the character prompt:**
   - **Your previous lines in this conversation:** Filter `dialogue_history` where `turn.speaker == current_character_name`. Format as a list (e.g. turn number + your dialogue). Cap to last N of their own lines if needed (e.g. last 10).
   - **What they said (person you’re talking to):** Decide “the other party” — e.g. the **last speaker** in the conversation (so the current character is “replying to” them), or the character who spoke most recently before this turn. Filter `dialogue_history` where `turn.speaker == other_party_name`. Format similarly. Cap to last N of their lines.
3. **Optional: “other party” logic** — If multiple characters speak in sequence, “the person you’re talking to” can be: (a) the last speaker, or (b) the Director’s “last selected speaker” (already in state). Use that name to filter their dialogues.
4. **Pass both sections into the character prompt** in `_character_respond_node` (or in `get_context_for_character()` if the graph calls it). Use clear labels, e.g.:
   - `Your previous lines in this conversation: ...`
   - `What [OtherPartyName] said in this conversation: ...`
5. **Keep full “Recent Dialogue” optional** — You can still include a short “Full recent dialogue” (last 5–10 turns) for flow, but the two sections above should be the primary context for consistency.

**Files to touch:**

- `src/graph/narrative_graph.py` — In `_character_respond_node`, build `your_previous_lines` and `other_party_lines` from `state.dialogue_history` (filter by speaker), then pass into context string. Optionally call a helper in `story_state.py`.
- `src/story_state.py` — Optionally add helpers e.g. `get_own_dialogues_for_character(character_name, dialogue_history, max_turns)` and `get_other_party_dialogues(other_party_name, dialogue_history, max_turns)` and use them when building context.
- `src/prompts/character_prompts.py` — Ensure prompt has placeholders or sections for “Your previous lines in this conversation” and “What [X] said in this conversation”.

### Steps (general character memory)

1. **Extend `CharacterProfile`** (`src/schemas.py`)
   - Add optional `goals: List[str] = []`
   - Add optional `inventory: List[str] = []` (or `Dict[str, int]` for counts)

2. **Add per-character memory to state**
   - Option A: In `StoryState`, add `character_memories: Dict[str, List[str]]` (each character’s memory entries).
   - Option B: New module e.g. `src/memory.py` with a `CharacterMemory` class that stores and retrieves facts per character.

3. **Update `character_configs.json`** (`examples/rickshaw_accident/character_configs.json`)
   - For each character add:
     - `"goals": ["e.g. Get out of this without paying a bribe"]`
     - `"inventory": ["e.g. phone", "small cash"]`

4. **Update `StoryStateManager.get_context_for_character()`** (`src/story_state.py`)
   - Include:
     - Character’s **goals** and **inventory** (from profile or state).
     - **Your memory:** last N facts from `character_memories[character_name]`.
   - Optionally: “What you believe about others” (perceptions) if you store them.

5. **When to write to memory**
   - After each dialogue turn and after each action: extract key facts (e.g. “Ahmed offered to pay”, “Raza asked for chai-pani”) and append to the speaking/acting character’s memory (and optionally to others’ “perceptions”).
   - Cap memory size (e.g. last 20 facts or by token count) to respect `max_context_length`.

### Files to Touch

- `src/schemas.py` — CharacterProfile, StoryState
- `src/story_state.py` — get_context_for_character, add_turn / memory update
- `src/config.py` — optional `max_memory_facts` or `max_memory_tokens`
- `examples/rickshaw_accident/character_configs.json` — goals, inventory
- `src/prompts/character_prompts.py` — include “Your goals”, “Your inventory”, “Your memory”

---

## 4. Feature 2: Action System

### Goal

Non-verbal actions that **change Story State**; at least **5 distinct actions** per run (Problem Statement 3.3 & 4).

**Purpose:** Break dialogue loops and push the narrative forward when talk alone is not enough.

### Steps

1. **Define action schema** (`src/schemas.py` or `src/actions.py`)
   - Example types: `Search_Object`, `Trade_Item`, `Give_Item`, `Use_Item`, `Unlock_Door`, `Take_Item` (and story-specific ones like `Offer_Bribe`, `Refuse_Bribe`, `Betray_Ally`, `Write_Challan`).
   - Model: e.g. `Action(type: str, target: Optional[str], description: Optional[str])`.
   - **Actions must be defined per story and character context** — choose types that fit the scenario and personas (e.g. rickshaw scenario: give money, take phone, offer bribe, write challan; other stories might use BetrayAlly, UnlockDoor, SearchObject, etc.).
   - Document which actions are valid in the story and how they affect the world.

2. **Extend `StoryState` for world/action effects**
   - e.g. `world_state: Dict[str, Any]` (e.g. `{"bribe_offered": False, "challan_written": False}`, `"box_opened": True, "key_found": True`).
   - Character inventories should be updated when actions like Give/Take/Trade run (can live in `character_memories` or a dedicated `character_inventories: Dict[str, List[str]]`).

3. **Action execution logic**
   - New module or functions: `execute_action(actor: str, action: Action, state: StoryState) -> StoryState`.
   - Validate action (type allowed, target present, etc.), then update:
     - Inventories (if Give/Take/Trade),
     - `world_state` flags if needed.

4. **Emit action events**
   - When an action is executed, append to `state.events` an entry with:
     - `type: "action"`
     - `speaker` (actor)
     - `content` or `action_type` + `target`
     - `turn`

5. **World updates carry into future turns — other agents react accordingly**
   - After an action updates `world_state` (e.g. “box opened → key found”), that state must be **included in the context given to all characters on future turns**. So when building prompts for Director and Character agents, pass the current `world_state` (and/or a short “What has happened so far” summary of action outcomes). This way other agents see what changed and can react (e.g. “Raza took the bribe” → others can refer to it in dialogue or take new actions).

6. **Enforce ≥5 actions**
   - Before calling Director’s `check_conclusion`, ensure `count(events where type == "action") >= 5`, or pass this into the Director prompt so it avoids ending too early.

### Files to Touch

- `src/schemas.py` — Action model; StoryState.world_state / inventories
- New: `src/actions.py` (optional) — action registry, validation, execution
- `src/graph/narrative_graph.py` — after “character_respond” or new “character_act” node: parse action, execute, append event
- `src/agents/character_agent.py` — character can output action (see Reasoning Layer)
- Director prompts — optionally mention “ensure at least 5 actions in the story”
- Context building (e.g. `story_state.py`, `narrative_graph.py`, character/director prompts) — include current `world_state` and action outcomes so **all agents** on future turns can react.

---

## 5. Feature 3: Reasoning Layer (Talk vs Act)

### Goal

Agents “think” through goals and **decide whether to Talk or Act** (Problem Statement 3.3).

### Steps

1. **Structured character output**
   - Option A (single call): Character prompt asks for JSON, e.g.:
     - `reasoning`: short explanation
     - `decision`: `"talk"` | `"act"`
     - `dialogue`: string or null
     - `action`: `{ "type": "...", "target": "..." }` or null
   - Option B (two steps): First LLM call: “Do you want to speak or act? If act, which action?” Second call: generate dialogue or confirm action and execute.

2. **Update character prompt** (`src/prompts/character_prompts.py`)
   - Include: goals, inventory, memory (from Feature 1).
   - Add: “Decide whether dialogue alone is enough to reach your goals, or if you need to perform an action (e.g. give item, offer money).”
   - Specify allowed action types and format (e.g. JSON with `decision`, `dialogue`, `action`).

3. **Graph branching** (`src/graph/narrative_graph.py`)
   - After getting character response:
     - If `decision == "act"` and `action` is valid → run action execution, update state, append action event; optionally add short narration for the action.
     - If `decision == "talk"` or no action → append dialogue turn as now.
   - Ensure both paths update `events` and state correctly.

### Files to Touch

- `src/prompts/character_prompts.py` — reasoning + decision + dialogue/action format
- `src/agents/character_agent.py` — parse structured response; return both dialogue and optional action
- `src/graph/narrative_graph.py` — branch on Talk vs Act; call action execution when Act

---

## 6. JSON Compliance

### story_output.json (Problem Statement 5.1)

Required:

- **Metadata**: title, seed story description (or reference).
- **Events**: chronological list with `type` (`dialogue` | `narration` | `action`), `speaker` (for dialogue/action), `content`, `turn` (or turn_number).
- **Conclusion**: why the story ended.

**Change in `src/main.py`:**

- Add a **top-level** `"conclusion"` field so evaluators see it clearly, e.g.:
  - `"conclusion": final_state.get("conclusion_reason")`
- Keep `metadata.conclusion_reason` if useful for debugging.

### prompts_log.json (Problem Statement 5.2)

Already has: timestamp, agent, prompt, response. Ensure no fields are removed and format stays consistent (e.g. include `role` if you use it).

---

## 7. Documentation & Report

### README (Rubric: clear setup/usage)

- **Run instructions**: One clear command (e.g. `uv run src/main.py`) and any env (e.g. `GOOGLE_API_KEY` in `.env`).
- **Expected outputs**: Mention `story_output.json` and `prompts_log.json` in project root.
- **What was built**: Short section on Memory, Actions, and Reasoning (Talk vs Act).
- **Structure**: Brief overview of `src/` (agents, graph, state, prompts).

### Technical Report (Problem Statement 5.3, Rubric 20 marks)

- **Format**: PDF (LaTeX preferred).
- **Content**:
  - System architecture (Director, Character agents, Narrative graph, State).
  - Character memory: what is stored, where, how it’s used in prompts.
  - Action system: action types, execution, how state and events are updated.
  - Reasoning layer: how Talk vs Act is implemented (e.g. structured output, graph branch).
  - Design decisions: e.g. why single-call vs two-step reasoning, why certain action set.
- Write in your own words to show understanding (avoid heavy AI-generated tone).

---

## 8. Checklist Summary

Use this to track progress:

- [ ] **Schemas**: `CharacterProfile` has `goals` and `inventory`; `StoryState` has memory and/or world_state; Action model defined.
- [ ] **Character configs**: `character_configs.json` includes goals and inventory per character.
- [ ] **Memory**: Per-character memory populated and used in `get_context_for_character` and prompts.
- [ ] **Dialogue context (current conversation)**: When a character speaks, context includes (1) their own previous dialogues in this conversation and (2) the other party’s previous dialogues in this conversation (so responses stay logical).
- [ ] **Actions**: Action types defined **per story and character context** (e.g. OfferBribe, BetrayAlly, WriteChallan for rickshaw); execution updates state; action events appended with `type: "action"`.
- [ ] **World state in future turns**: Current `world_state` and action outcomes (e.g. “box opened → key found”) are passed in context to all agents on future turns so other agents can react accordingly.
- [ ] **Reasoning**: Character prompt asks for decision (Talk/Act) and optional reasoning; agent returns structured output.
- [ ] **Graph**: Branch on Talk vs Act; action path executes action and updates state and events.
- [ ] **≥5 actions**: Logic ensures at least 5 actions before story can conclude.
- [ ] **25 turns max**: Simulation respects max 25 turns (config + conclusion logic does not exceed it).
- [ ] **story_output.json**: Top-level `conclusion` field added in `main.py`.
- [ ] **README**: Run command, env, expected outputs, and “what we built” (memory, actions, reasoning).
- [ ] **Technical Report**: PDF (LaTeX) with architecture, memory, actions, reasoning, and design rationale.
- [ ] **Run test**: Clone, install, set env, run once; confirm `story_output.json` and `prompts_log.json` are correct and story has ≥5 actions.

---

## 9. File Reference

| File | Purpose |
|------|---------|
| `src/schemas.py` | DialogueTurn, CharacterProfile (goals, inventory), StoryState (memory, events, world_state), Action |
| `src/config.py` | max_turns, max_context_length, max_tokens_per_prompt, temperature, optional memory limits |
| `src/story_state.py` | StoryStateManager; get_context_for_character (memory, goals, inventory); optional helpers for own/other-party dialogue context; memory update on turn/action |
| `src/agents/character_agent.py` | respond() returns or parses structured output (dialogue + optional action + reasoning) |
| `src/agents/director_agent.py` | select_next_speaker, check_conclusion (consider “at least 5 actions” in prompt or logic) |
| `src/graph/narrative_graph.py` | Nodes: director_select → character_respond (or character_act branch) → action execution → check_conclusion → conclude; build context with own + other-party dialogues (current conversation) |
| `src/prompts/character_prompts.py` | Include memory, goals, inventory; sections for “Your previous lines” and “What [other] said”; output format for Talk vs Act |
| `src/main.py` | Build output_data with top-level `conclusion`; write story_output.json, prompts_log.json |
| `examples/rickshaw_accident/character_configs.json` | Add goals and inventory per character |

---

*Last updated for Gen_AI_Problem_Statement.md and Evaluation_Rubric.md. Complete these items to meet the Hackfest × Datathon requirements and maximize rubric scores.*
