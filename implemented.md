# Implemented Checklist — GenAI_DSS Multi-Agent Narrative System

This file tracks every implemented feature, why it was implemented, and the exact code changes applied.

---

## Checklist

- [x] **Schemas**: CharacterProfile has goals and inventory; StoryState has memory and world_state; Action model defined.
- [x] **Character configs**: character_configs.json includes goals and inventory per character.
- [x] **Memory**: Per-character memory populated and used in get_context_for_character and prompts.
- [x] **Dialogue context**: When a character speaks, context includes their own previous dialogues and the other party's previous dialogues so responses stay logical.
- [x] **Director improvement**: Director sees character descriptions + goals when selecting speaker; anti-repetition instruction prevents same 2 characters looping.
- [x] **Scene detail enrichment**: Seed story and character configs now have concrete details (BMW brand, colors, damage specifics) so LLM never guesses facts.
- [x] **Anti-repetition hard enforcement**: Code-level block prevents same speaker more than max_consecutive times — LLM can't override.
- [x] **min_turns hard enforcement**: Code-level block prevents conclusion before min_turns (10) — no more 9-turn stories.
- [x] **Proper story ending**: Conclusion prompt requires detailed resolution with each character's fate, crowd, environment, and emotional beat.

---

## 1. Schemas Update

**Why:** The original `CharacterProfile` only had `name` and `description`. Characters had no goals to pursue, no inventory to interact with, and no memory of past events. Without these, the narrative lacks depth — characters can't reason about objectives, trade items, or recall what happened. The `Action` model is needed so the system can later support non-verbal actions (give item, offer bribe, etc.) as required by the problem statement. `world_state` on `StoryState` allows tracking global flags (e.g. "bribe_offered", "challan_written") that actions can modify.

### Applied Changes

**File: `src/schemas.py`**

| Change | What was done |
|--------|---------------|
| `CharacterProfile.goals` | Added `goals: List[str] = Field(default_factory=list)` — each character's objectives |
| `CharacterProfile.inventory` | Added `inventory: List[str] = Field(default_factory=list)` — items the character carries |
| `Action` model (new) | New Pydantic model with `type`, `actor`, `target` (optional), `description` (optional) — represents a non-verbal action |
| `StoryState.character_memories` | Added `character_memories: Dict[str, List[str]]` — per-character memory buffer |
| `StoryState.world_state` | Added `world_state: Dict[str, Any]` — global story flags updated by actions |

---

## 2. Character Configs Update

**Why:** The schemas now support goals and inventory, but the actual character data in `character_configs.json` had neither. Without goals, characters have no motivation to drive the story. Without inventory, item-based actions (give money, show ID, write challan) have nothing to operate on. Each character was given goals and items that fit their role in the rickshaw accident scenario.

### Applied Changes

**File: `examples/rickshaw_accident/character_configs.json`**

| Character | Goals added | Inventory added |
|-----------|-------------|-----------------|
| **Saleem** | Avoid paying for damage, not get arrested, get back to work | old Nokia phone, small cash (200 rupees), rickshaw keys |
| **Ahmed Malik** | Get compensation, leave for airport ASAP, assert authority | smartphone, business card, wallet with credit cards, car keys |
| **Constable Raza** | Clear traffic, extract facilitation fee, avoid paperwork | traffic challan book, whistle, police ID badge |
| **Uncle Jameel** | Stay involved in drama, mediate to feel important, protect Saleem | shop keys, phone, chai cup |

---

## 3. Per-Character Memory

**Why:** Previously characters only saw the last 15 raw dialogue turns with no structured memory. This means a character couldn't recall earlier events once the dialogue window scrolled past them. Per-character memory solves this by storing key facts (what I said, what others said) as a persistent buffer capped at 20 entries. This gives characters continuity — they remember promises, threats, and offers even if those happened many turns ago.

### Applied Changes

**File: `src/story_state.py`**

| Change | What was done |
|--------|---------------|
| `MAX_MEMORY_FACTS = 20` | Constant to cap memory size per character |
| `__init__` updated | Now reads `goals` and `inventory` from character config dicts; initializes `character_memories` as `{name: []}` for each character; initializes `world_state` as `{}` |
| `update_memory()` (new static method) | Appends a fact to a character's memory list, trims to last 20 entries |
| `get_context_for_character()` rewritten | Now returns structured context with: goals, inventory, last 10 memory facts, and last 15 dialogue turns |

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| `_character_respond_node()` updated | After generating dialogue, updates `character_memories` — adds "I said: ..." to the speaker and "{Speaker} said: ..." to every other character. Caps each at 20 entries. Returns updated `character_memories` in state dict. |

**File: `src/prompts/character_prompts.py`**

| Change | What was done |
|--------|---------------|
| Prompt template simplified | Removed the old hardcoded "Things You Remember" section. The prompt now directly uses the rich context string (which already contains goals, inventory, memory, and dialogue) passed from the graph. |

---

## 4. Dialogue Context (Own + Others' Lines)

**Why:** For a character's response to make sense, they need to see what they previously said AND what others said to them. Without this, characters repeat themselves, contradict earlier statements, or ignore direct questions. The implementation ensures every character sees the full recent conversation (last 15 turns) — both their own lines and everyone else's — so they can respond logically and coherently.

### Applied Changes

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| `_build_character_context()` (new method) | Builds a complete context string for any character, including: initial event, director narration, goals, inventory, memory facts (last 10), and recent dialogue (last 15 turns showing all speakers). This replaces the old inline context string that only had the event description and raw dialogue. |
| `_character_respond_node()` updated | Now calls `_build_character_context()` instead of building context inline. This ensures consistent, rich context for every character turn. |
| `run()` updated | Now accepts and passes `character_memories` to the initial state so memory persists from the start. |

**File: `src/main.py`**

| Change | What was done |
|--------|---------------|
| `story_graph.run()` call updated | Now passes `character_memories=story_manager.state.character_memories` so the graph starts with initialized (empty) memory buffers for each character. |

---

---

## 5. Director Improvement (Character Descriptions + Anti-Repetition)

**Why:** The Director previously only saw a flat list of character names (`Saleem, Ahmed Malik, Constable Raza, Uncle Jameel`) with zero context about who they are. This caused two problems: (1) the Director couldn't know Uncle Jameel is a mediator/witness, so he entered the story very late (turn 10); (2) without awareness of character roles, the Director let the same 2 characters haggle back-and-forth endlessly, creating repetitive dialogue. By giving the Director each character's description and goals, it can make smarter decisions — bringing in a mediator when tension rises, an authority figure when things get chaotic, etc. The anti-repetition rule explicitly prevents same-pair loops.

### Applied Changes

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| `{available_characters}` → `{character_descriptions}` | Prompt now expects character descriptions with goals, not just names |
| Anti-repetition rule added | New instruction: "If the last 3-4 turns are between the same 2 characters on the same topic, MUST pick a different character" |
| Role-based guidance added | New instruction: use each character's personality/goals to decide when they'd naturally intervene |
| Conclusion prompt updated | Added repetition detection: "if characters are repeating the same arguments or amounts, it is time to wrap up" |

**File: `src/agents/director_agent.py`**

| Change | What was done |
|--------|---------------|
| `select_next_speaker()` updated | Now builds a formatted string with each character's name, description, and goals from `story_state.character_profiles`, passed as `character_descriptions` to the prompt |
| Old `available_characters` param removed | Replaced by the richer `character_descriptions` string |

---

## 6. Scene Detail Enrichment (Fix Factual Inconsistency)

**Why:** The seed story said "a car" with no brand, color, or damage specifics. Ahmed's description said "expensive car" — again no concrete detail. This meant the LLM invented the car brand each turn (BMW in one run, Mercedes in another), causing factual inconsistency within the same story. The fix is simple: bake concrete facts into the source data so every agent prompt has the same ground truth from turn 1. No extra LLM calls needed, 100% reliable.

### Applied Changes

**File: `examples/rickshaw_accident/seed_story.json`**

| Change | What was done |
|--------|---------------|
| `description` enriched | Now specifies: "green rickshaw", "white BMW", "dent on left rear door", "front bumper bent" |
| `setting` object added | Structured details: location, time, weather, and both vehicles with specific descriptions |

**File: `examples/rickshaw_accident/character_configs.json`**

| Character | Description change |
|-----------|-------------------|
| **Saleem** | Now mentions "old green rickshaw" and "front bumper bent in collision with a white BMW" |
| **Ahmed Malik** | Now mentions "white BMW" and "dent on left rear door from the rickshaw collision" |
| **Constable Raza** | Now mentions "rickshaw-BMW collision on Shahrah-e-Faisal" |
| **Uncle Jameel** | Now mentions "witnessed the rickshaw hitting the white BMW" and "his shop is right on the corner" |

---

---

## Progress Analytics

### Run Comparison Chart

| Metric | Run 1: Original (D:\) | Run 2: After Changes 1–4 | Run 3: After Changes 1–6 | Run 4: After All 11 Changes |
|--------|------------------------|--------------------------|--------------------------|------------------------------|
| **Changes applied** | None | Schemas, Goals, Inventory, Memory, Dialogue Context | + Director Improvement, Scene Enrichment | + Action System, Reasoning Layer, World State, Director Upgrade, Karachi Realism |
| **Total turns** | 11 | 20 | 11 | 9 |
| **Total actions** | 0 | 0 | 0 | **9** (6+ distinct types) |
| **Car brand consistency** | BMW (lucky guess) | Mercedes (wrong — inconsistent) | BMW (from config — 100% consistent) | BMW (100% consistent) |
| **Uncle Jameel entry turn** | Turn 6 | Turn 10 | **Turn 4** | Turn 5 |
| **Speaker diversity (4 chars by turn)** | Turn 6 | Turn 10 | **Turn 4** | Turn 5 |
| **Repetitive loops detected** | No | Yes (turns 12–20: same haggling) | No | No |
| **Characters reference goals** | No | Partially (persistent but unfocused) | Yes (goal-driven + balanced) | Yes (goal-driven + physical actions) |
| **Action types used** | — | — | — | Show_Item, Record_Video, Call_Contact, Confiscate_Keys, Offer_Bribe, Block_Vehicle |
| **Dialogue language** | English | English | English with some Urdu | **Heavy Urdu/Roman Urdu** (realistic) |
| **Physical actions** | None | None | None | **9 actions** — blocking, grabbing keys, recording, sitting on ground |
| **Crowd presence** | Not mentioned | Not mentioned | Barely mentioned | **Active** — crowd reactions in Director narrations |
| **Resolution nuance** | 5000 flat, quick deal | 3000, Saleem pays, loses | 5000 from Ahmed, Raza skims 3000, Saleem gets 2000 | Nuanced with physical escalation and de-escalation |
| **Conclusion quality** | Good — natural ending | Weak — dragged | **Best** — nuanced | Good — action-driven but slightly abrupt (9 turns) |
| **Story pacing** | Good | Poor (bloated middle) | **Best** (tight) | Good (fast-paced, action-heavy) |
| **Factual errors** | None | Car brand wrong | **None** | **None** |
| **Anti-repetition compliance** | N/A | Failed | Passed | ⚠️ Uncle Jameel speaks turns 8-9 consecutively |
| **Overall rating** | 6/10 | 4/10 (regression) | **8.5/10** | **8.5/10** |

### Progress Trend

```
Quality
  10 |
   9 |                                          *  Run 3 (8.5)    *  Run 4 (8.5)
   8 |
   7 |
   6 |  * Run 1 (6.0)
   5 |
   4 |                 * Run 2 (4.0)
   3 |
   2 |
   1 |
   0 +----------+-----------+-----------+-----------+
     Original   After 1-4   After 1-6   After 1-11
```

### Key Observations Per Stage

**Original → After Changes 1–4 (Regression: 6.0 → 4.0)**
- Goals made characters more persistent — good foundation but caused infinite loops
- Memory system working but Director wasn't upgraded to handle it
- Car brand inconsistency exposed (no factual grounding)
- Lesson: Adding character intelligence without upgrading the Director creates imbalance

**After Changes 1–4 → After All 6 Changes (Recovery + Improvement: 4.0 → 8.5)**
- Director now sees character descriptions → Uncle Jameel enters at turn 4 (was 10)
- Anti-repetition rule → no more same-pair haggling loops
- Scene enrichment → BMW consistent across all 11 turns
- Conclusion prompt detects repetition → story ends at natural point
- Resolution is most nuanced: Ahmed pays, Raza skims, Saleem gets something — reflects real Karachi dynamics
- Lesson: Director quality is the backbone; character intelligence only shines when Director orchestrates well

**After Changes 1–6 → After All 11 Changes (Action System + Realism: 8.5 → 8.5)**
- Action system working: 9 actions across 6+ distinct types (Show_Item, Record_Video, Call_Contact, Confiscate_Keys, Offer_Bribe, Block_Vehicle)
- Reasoning layer functional: characters decide Talk vs Act via structured JSON
- Karachi realism dramatically improved: crowd reactions, heat/dust environment, heavy Urdu dialogue
- World state propagation working: actions update flags visible to all future turns
- ≥5 actions enforcement working (9 actions total, well above threshold)
- Score stayed at 8.5 (not higher) because: only 9 turns (story feels rushed), Uncle Jameel double-turn at 8-9
- Lesson: Action system adds massive depth but needs tuning — story should breathe more between actions

### Issues Remaining
- [x] ~~No non-verbal actions yet~~ → Implemented (Change 7)
- [x] ~~No Talk vs Act reasoning layer~~ → Implemented (Change 8)
- [x] ~~No ≥5 actions enforcement~~ → Implemented (Change 7/9)
- [x] ~~story_output.json missing top-level `conclusion` field~~ → Fixed (Change 10)
- [x] ~~Realism not yet tested with a run~~ → Run 4 confirms realism working
- [ ] Uncle Jameel double-turn (turns 8-9) — anti-repetition enforcement needs fix
- [ ] Story length too short (9 turns) — may need minimum turn encouragement
- [ ] No Technical Report (PDF/LaTeX)
- [ ] README needs updating with run instructions and architecture
- [ ] JSON output compliance verification needed

### Do's & Don'ts Compliance (from `do's n don's.md`)

| Requirement | Status | Notes |
|------------|--------|-------|
| Character memory | ✅ Done | Per-character, 20-fact cap |
| Action system (≥5 actions) | ✅ Done | 9 actions, 6+ types in Run 4 |
| Reasoning layer (Talk vs Act) | ✅ Done | Structured JSON decision |
| Max 25 turns | ✅ Done | 9 turns in Run 4 |
| Free/open-source models | ✅ Done | Gemma 3 27B IT |
| story_output.json | ✅ Done | With conclusion + metadata |
| prompts_log.json | ✅ Done | Timestamped audit log |
| Not dialogue-only | ✅ Done | 9 physical actions |
| Coherent narration | ✅ Done | Logical, engaging, consistent |
| JSON compliance | ⚠️ Needs verification | Output structure needs checking |
| Clear README | ❌ Not done | Judges penalize heavily |
| Technical Report | ❌ Not done | Required documentation |
| Originality / design thinking | ✅ Done | Custom Karachi actions, research-based realism |

---

## 7. Action System (New Module: `src/actions.py`)

**Why:** The story was dialogue-only. Characters talked about money, threats, and decisions but never physically DID anything. On a real Karachi street, people block vehicles, grab keys, record videos, sit on the ground in protest, and hand over cash. Without actions, the story feels like a radio play, not a street scene. The rubric also requires ≥5 distinct actions per run and `type: "action"` events in `story_output.json` (15 marks for JSON compliance).

### Applied Changes

**New file: `src/actions.py`**

| Component | What it does |
|-----------|-------------|
| `VALID_ACTIONS` dict | 10 scenario-specific actions: `Give_Money`, `Offer_Bribe`, `Write_Challan`, `Confiscate_Keys`, `Record_Video`, `Block_Vehicle`, `Show_Item`, `Call_Contact`, `Offer_Chai`, `Sit_On_Ground` — each with description, target requirement, and effects |
| `get_available_actions_text()` | Formats action list for character prompts |
| `validate_action()` | Checks action type exists, target is valid, actor ≠ target |
| `execute_action()` | Updates `world_state` flags, updates memory for all characters, returns narration text |
| `get_action_count()` | Counts `type: "action"` events in state — used for ≥5 enforcement |

---

## 8. Reasoning Layer: Talk vs Act (Structured Character Output)

**Why:** Characters need to DECIDE whether to speak, act, or both. Previously they could only output dialogue. Now they output structured JSON with `reasoning`, `decision` (talk/act/both), `dialogue`, and optional `action`. This is the core of the Problem Statement 3.3 requirement: "Agents decide whether to Talk or Act."

### Applied Changes

**File: `src/prompts/character_prompts.py`**

| Change | What was done |
|--------|---------------|
| Structured JSON output format | Character must respond with `reasoning`, `decision`, `dialogue`, `action` fields |
| Available actions listed | All 10 action types shown in prompt with descriptions |
| `world_state_text` param added | Character sees current world state (what actions have happened) |
| Karachi realism instructions | "Act like a REAL person on a Karachi street", "React to the crowd", "Use natural Urdu-English mix" |

**File: `src/agents/character_agent.py`**

| Change | What was done |
|--------|---------------|
| `respond()` return type changed | Now returns `Tuple[str, Optional[Dict]]` — (dialogue, action_dict) |
| JSON parsing added | Parses structured response, extracts dialogue and action separately |
| `world_state_text` param added | Passed to prompt builder |
| Fallback handling | If JSON parsing fails, treats entire response as dialogue with no action |

---

## 9. Narrative Graph: Action Execution & World State Propagation

**Why:** The graph needed to process actions returned by characters — validate them, execute them, update world_state, emit action events, and ensure all future turns see the updated state. Also enforces ≥5 actions before allowing conclusion.

### Applied Changes

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| `_format_world_state()` new method | Converts `world_state` dict to readable text for prompts |
| `_build_character_context()` updated | Now includes action count and encourages physical actions when count < 5 |
| `_character_respond_node()` rewritten | Calls `character.respond()` with world_state_text; if action returned, validates and executes it; emits both dialogue and action events; updates world_state and memories |
| `_check_conclusion_node()` updated | Hard blocks conclusion if `action_count < 5`; only calls Director after threshold met |

---

## 10. Director Upgrade for Actions & World State

**Why:** Director needs to see what actions have happened (world_state) and how many actions have occurred (action_count) to make informed decisions about speaker selection and story conclusion.

### Applied Changes

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| `{world_state_text}` added | Director sees current world state in speaker selection prompt |
| `{action_count}` added | Both prompts show current action count and minimum threshold |
| Action encouragement | If < 5 actions, Director is told to pick characters likely to perform physical actions |
| Crowd awareness instruction | Director narrations should include crowd reactions, environmental details |
| Conclusion prompt hardened | "DO NOT CONCLUDE if fewer than 5 actions taken" |

**File: `src/agents/director_agent.py`**

| Change | What was done |
|--------|---------------|
| `_format_world_state()` method added | Formats world_state dict for prompts |
| `select_next_speaker()` updated | Passes world_state_text and action_count to prompt |
| `check_conclusion()` updated | Passes world_state_text and action_count to prompt |

---

## 11. Karachi Realism Overhaul

**Why:** Analysis of all 3 previous runs against real Karachi street dynamics (based on research of actual incidents) revealed major realism gaps: invisible crowd, no phone recording, characters too polished/English, police too polite, no physical actions, silent environment. Real Karachi road accidents involve mobs surrounding vehicles, phone recording as leverage, raw street Urdu, blunt police threats, physical confrontation, and environmental chaos.

### Applied Changes

**File: `examples/rickshaw_accident/seed_story.json`**

| Change | What was done |
|--------|---------------|
| `description` expanded | Now includes: 40°C heat, crowd of 15-20 people, some recording on phones, crowd siding with poor man, chai dhaba on corner, "In Karachi, the crowd decides more than the police" |
| `setting.crowd` added | "15-20 people gathered, some recording on phones, mostly siding with the rickshaw driver" |
| `setting.environment` added | "Non-stop honking, bus/truck drivers shouting, chai dhaba nearby, paan shop across the road" |

**File: `examples/rickshaw_accident/character_configs.json`**

| Character | Realism changes |
|-----------|----------------|
| **Saleem** | Can cry/sit on ground/beat chest/appeal to crowd. "Knows crowd usually sides with the poor man." Physically blocks car. Shows empty wallet. |
| **Ahmed Malik** | "Increasingly nervous because the crowd is growing and hostile." BMW physically blocked. "In Karachi, a rich man surrounded by an angry crowd is in a vulnerable position." Real fear is being stuck, not damage cost. |
| **Constable Raza** | "Does NOT use polite words like 'facilitation fee', just directly asks for money." Physically takes keys. "Nervous about people recording on phones." Threatens to impound rickshaw. |
| **Uncle Jameel** | "Physically inserts himself — stands between people, waves arms, blocks paths." Actually sends helper for chai. "Claims to know everyone." 30 years on this street. |

**File: `src/main.py`**

| Change | What was done |
|--------|---------------|
| Action count printed | Shows total actions at end of run |
| Top-level `conclusion` field | Added to `story_output.json` as required by Problem Statement 5.1 |
| `metadata.total_actions` | Added to output metadata |

---

## 12. Anti-Repetition Hard Code Enforcement

**Why:** The Director prompt said "don't pick the same speaker more than 2 times in a row" — but the LLM ignored it. In Run 4, Uncle Jameel spoke at turns 8 AND 9 consecutively. Prompt-only rules are unreliable. A hard code check guarantees no character speaks more than `max_consecutive_same_character` times in a row, regardless of what the LLM returns.

### Applied Changes

**File: `src/agents/director_agent.py`**

| Change | What was done |
|--------|---------------|
| Hard enforcement block added | After Director picks a speaker, code checks if that speaker already spoke `max_consecutive` times in a row. If yes, forces a different speaker from available characters. Prints `[Anti-Repetition]` warning. |

---

## 13. min_turns Hard Code Enforcement

**Why:** Config has `min_turns: 10`, but Run 4 ended at turn 9. The min_turns check was only in the conclusion PROMPT — the LLM ignored it. Now the code hard-blocks conclusion before `min_turns`, ensuring the story always gets enough turns to develop properly. Also added max_turns force-conclusion as safety net.

### Applied Changes

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| `min_turns` hard block | `_check_conclusion_node()` returns `is_concluded: False` if `current_turn < config.min_turns` — no LLM call needed |
| `max_turns` force conclusion | If `current_turn >= config.max_turns`, force `is_concluded: True` as safety net |

---

## 14. Proper Story Ending (Resolution Narration)

**Why:** The story felt like a "scenario" — it just stopped without a proper ending. The conclusion_narration was a single generic line like "the situation was resolved". A real story needs: final deal/outcome, each character's fate after resolution, crowd dispersing, environment returning to normal, and a final emotional beat. The enhanced conclusion prompt now REQUIRES all 5 elements, producing a 4-6 sentence ending that gives closure to every character arc.

### Applied Changes

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| Conclusion prompt expanded | Now requires 5 elements: Resolution details, each character's fate (Saleem/Ahmed/Raza/Jameel), crowd reaction, environment closing, final emotional beat |
| Character descriptions added | Conclusion prompt now sees `{character_descriptions}` so it knows each character's goals when writing their ending |
| Last 8 turns shown (was 5) | More context for better conclusion quality |
| "4-6 sentences minimum" | Explicit instruction for detailed ending |

**File: `src/agents/director_agent.py`**

| Change | What was done |
|--------|---------------|
| `check_conclusion()` updated | Now builds and passes `character_descriptions` to conclusion prompt |
| Last turns increased to 8 | Shows more recent dialogue for better conclusion context |

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| `_conclude_node()` enhanced | Now prints the full conclusion narration with visual formatting (=== borders) |

**File: `src/main.py`**

| Change | What was done |
|--------|---------------|
| Conclusion printing improved | Shows "Story Ending" section with the full conclusion narration instead of just "Reason: ..." |

---

*This file will be updated with new runs as they are shared for comparison. Each run will be scored and added to the chart above.*
