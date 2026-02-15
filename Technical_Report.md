# Technical Report: GenAI_DSS Multi-Agent Narrative System

**Hackfest x Datathon 2026 — Generative AI Module**

---

## 1. Abstract

This report describes the design and implementation of a Multi-Agent Narrative System that orchestrates four autonomous character agents through a conflict-driven story using LangGraph. The system extends the provided starter codebase with three mandatory components — Character Memory, Action System, and Reasoning Layer — plus several novel extensions including dramatic story twist injection, per-character language modeling, and code-level anti-repetition enforcement. The system generates narratives of 15-25 turns with 10+ distinct actions, producing coherent stories where agents negotiate, escalate, and resolve conflicts based on their individual goals and memories.

---

## 2. System Architecture

### 2.1 High-Level Design

The system follows a Director-Agent architecture orchestrated by a LangGraph `StateGraph`. The Director controls narrative pacing and speaker selection, while four Character Agents autonomously generate dialogue and actions based on their personality, memory, and goals. A fifth agent, the **ReviewerAgent**, checks each character turn for Karachi realism, logical consistency, and repetition; if it rejects (major issues), the character gets one retry with the reviewer’s suggestion in context.

```
                    ┌─────────────────┐
                    │   Entry Point   │
                    │   (main.py)     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  NarrativeGraph  │
                    │  (StateGraph)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼───┐  ┌──────▼──────┐  ┌───▼──────────┐
    │  Director    │  │  Character  │  │   Check      │
    │  Select      │──│  Respond    │──│  Conclusion  │
    │  Speaker     │  │  (Reason +  │  │  (min turns, │
    │  + Narrate   │  │   Act)      │  │   actions,   │
    └─────────────┘  └─────────────┘  │   twist)     │
                                       └──────┬───────┘
                                              │
                                    continue ─┤── conclude → END
                                              │
                                    ┌─────────▼─────────┐
                                    │  Twist Injection   │
                                    │  (Turn 9, code-    │
                                    │   level event)     │
                                    └───────────────────┘
```

### 2.2 State Management

All state flows through a single Pydantic `StoryState` model:

| Field | Type | Purpose |
|---|---|---|
| `seed_story` | `Dict` | Original scenario description |
| `current_turn` | `int` | Turn counter |
| `dialogue_history` | `List[DialogueTurn]` | Full dialogue transcript |
| `events` | `List[Dict]` | Chronological events (dialogue, narration, action) |
| `character_profiles` | `Dict[str, CharacterProfile]` | Name, description, goals, inventory per character |
| `character_memories` | `Dict[str, List[str]]` | Per-character memory buffers |
| `world_state` | `Dict[str, Any]` | Mutable world facts (keys confiscated, money exchanged, etc.) |
| `is_concluded` | `bool` | Whether story has ended |
| `conclusion_reason` | `str` | Final narration explaining the ending |

LangGraph's `StateGraph` passes this state through each node, with nodes returning partial state updates that get merged.

### 2.3 LLM Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Model | `gemma-3-27b-it` | Free-tier Google Generative AI; strong instruction following |
| Temperature | `0.7` | Balances creativity with consistency |
| Max Output Tokens | `2000` | Sufficient for dialogue + action JSON |
| Max Context | `4000` | Fits character context + memory + dialogue history |

---

## 3. Mandatory Component Implementations

### 3.1 Character Memory System

**Design Decision**: Sliding window per-character memory with cross-character propagation.

Each character maintains a list of up to 20 memory entries. After each turn:

1. **Speaker's memory** receives: `"Turn X: I said: {dialogue}"`
2. **All other characters' memories** receive: `"Turn X: {Speaker} said: {dialogue}"`
3. **Action memory**: When any action executes, ALL characters receive: `"[ACTION] Actor: ActionType → Target (description)"`
4. **Twist memory**: When a story twist fires, ALL characters receive the twist context.

**Why sliding window of 20?** Keeps the context within `max_context_length` (4000 tokens) while preserving enough history for continuity. Older memories are dropped, simulating how real people forget earlier details but remember recent events clearly.

**Why cross-character propagation?** In the physical scenario (street accident), all characters can see and hear everything. Cross-propagation ensures character B knows what character A did, enabling realistic reactions.

```python
# Memory update after each turn (narrative_graph.py)
speaker_mem.append(f"Turn {turn}: I said: {dialogue[:150]}")
for other in characters:
    other_mem.append(f"Turn {turn}: {speaker} said: {dialogue[:150]}")
```

### 3.2 Action System

**Design Decision**: Scenario-specific action vocabulary with validation-execution pipeline.

We defined 10 action types specific to the Rickshaw Accident scenario:

| Action | Target Required | World State Effect |
|---|---|---|
| `Give_Money` | Yes | Sets `money_exchanged`, `money_from`, `money_to` |
| `Offer_Bribe` | Yes | Sets `bribe_offered`, `bribe_from`, `bribe_to` |
| `Write_Challan` | Yes | Sets `challan_written`, `challan_target` |
| `Confiscate_Keys` | Yes | Sets `keys_confiscated`, `keys_taken_from` |
| `Record_Video` | No | Sets `being_recorded`, `recorder` |
| `Block_Vehicle` | Yes | Sets `vehicle_blocked`, `vehicle_blocked_owner` |
| `Show_Item` | No | Sets `{actor}_showed_item` |
| `Call_Contact` | No | Sets `{actor}_called_contact` |
| `Offer_Chai` | No | Sets `chai_offered` |
| `Sit_On_Ground` | No | Sets `{actor}_sitting_on_ground` |

**Validation Pipeline** (`actions.py:validate_action`):
1. Check action type is in `VALID_ACTIONS`
2. Check target is provided if required
3. Check target exists in `character_profiles`
4. Check actor is not targeting themselves

**Execution Pipeline** (`actions.py:execute_action`):
1. Update `world_state` with action-specific flags
2. Generate narration text describing the action
3. Propagate action fact to ALL characters' memories
4. Return updated state

**Why scenario-specific actions?** Generic actions (like "do something") don't produce meaningful state changes. By defining concrete actions tied to the scenario, each action creates a specific world-state fact that other characters can detect and respond to (e.g., if keys are confiscated, Ahmed can't leave).

### 3.3 Reasoning Layer

**Design Decision**: Structured JSON output with explicit reasoning field.

Each character agent outputs a structured JSON response:

```json
{
    "reasoning": "Brief internal thought about goals and situation",
    "decision": "talk | act | both",
    "dialogue": "Spoken words in character voice",
    "action": {
        "type": "ActionType",
        "target": "character name or null",
        "description": "What the character physically does"
    }
}
```

The `reasoning` field captures the agent's internal decision-making:
- **Goal assessment**: "I need to get the crowd on my side"
- **Situation analysis**: "Ahmed offered money; I should reject to keep sympathy"
- **Strategy choice**: "I'll show my empty wallet to prove I'm poor"

The `decision` field forces an explicit choice between talking, acting, or both — preventing the common failure mode where agents only talk and never perform physical actions.

**Why JSON-structured reasoning?** Forcing the LLM to output structured JSON with a reasoning step improves decision quality. The model must articulate its thinking before generating dialogue, similar to chain-of-thought prompting. The structured format also ensures we can reliably parse actions from responses.

---

## 4. Novel Extensions

### 4.1 Story Twist Injection

**Problem**: LLM-generated stories tend toward linear escalation → quick resolution. The Director prompt's "Phase 3: Complication" instructions were routinely ignored by the model.

**Solution**: Code-level event injection at turn 9. Four pre-written twists are available:

1. **Flight Missed**: Ahmed's Dubai flight departs without him — removes his urgency to leave, changes his negotiation stance entirely.
2. **Senior Officer Coming**: DSP inspection in 10 minutes — Raza panics, can't take bribes openly.
3. **Viral Video**: Live stream hits 50,000 views — public scrutiny on everyone.
4. **Rickshaw Engine Dead**: Mechanic confirms engine failure, 50,000 rupees damage — escalates the stakes dramatically.

Each twist includes:
- **Narration**: Injected into the story as a dramatic moment
- **World State Update**: Flags that characters can detect (e.g., `ahmed_flight_missed: True`)
- **Memory Update**: Added to ALL characters' memories so they react to it

**Why code-level, not prompt-level?** Prompt instructions like "inject a complication at turn 10" are unreliable — the LLM may ignore them, inject them too early, or generate weak complications. Code-level injection guarantees the twist happens at exactly the right moment with the right content.

**Post-twist breathing room**: After the twist fires (turn 9), conclusion checks are blocked until turn 14, giving characters 5 turns to react to the new situation.

### 4.2 Per-Character Language Modeling

**Problem**: All characters initially spoke fluent English, which is unrealistic for a Karachi street scene. A poor rickshaw driver would not say "I have a family to feed! Five children!"

**Solution**: Per-character language rules with explicit WRONG/RIGHT examples:

- **Saleem** (rickshaw driver): 95% Roman Urdu, only knows basic English words (please, sorry, sir, police). *Wrong*: "I have a family to feed!" → *Right*: "Bhai mere paanch bachche hain!"
- **Ahmed Malik** (businessman): English-Urdu code-switching, as elite Karachiites naturally speak. "Dekhiye, I have a very important flight."
- **Constable Raza** (traffic police): 90% blunt street Urdu, authority speech. *Wrong*: "I need to inspect your vehicle" → *Right*: "Abe chabi de! Documents dikhao!"
- **Uncle Jameel** (shopkeeper elder): 95% dramatic Urdu with theatrical flair.

These rules are injected prominently in each character's prompt with concrete examples, making the LLM follow the linguistic constraints more reliably.

### 4.3 Anti-Repetition System

Three layers of anti-repetition enforcement:

**Layer 1 — Speaker Anti-Repetition** (code-level):
`max_consecutive_same_character = 1` ensures no character speaks twice in a row. If the Director selects the same speaker as the last turn, the system forces a different character.

**Layer 2 — Anti-Ping-Pong** (code-level):
If the same 2 characters have been speaking for the last 4 turns, the system forces a third character into the conversation.

**Layer 3 — Dialogue Anti-Repetition** (prompt-level):
Each character sees their own previous lines with explicit instructions: "YOU MUST SAY SOMETHING COMPLETELY NEW." They also see their previously used action types with instructions to pick different ones.

### 4.4 Director Story Phase System

The Director prompt includes a 4-phase structure:
- **Phase 1 — Setup (Turns 1-4)**: Characters arrive, assess, take positions
- **Phase 2 — Escalation (Turns 5-9)**: Tensions rise, actions increase
- **Phase 3 — Complication (Turns 10-15)**: Twist has fired, characters adapt
- **Phase 4 — Resolution (Turns 16-22)**: Final negotiations, money changes hands

The Director receives the current turn number and uses it to gauge which phase the story is in, adjusting speaker selection and narration accordingly.

### 4.5 Conclusion Resistance

Multiple mechanisms prevent premature story endings:
- **Minimum turns**: Story cannot end before turn 15
- **Minimum actions**: At least 5 actions must have occurred
- **Post-twist buffer**: 5 turns after twist injection before conclusion is possible
- **Frequency limiting**: Before turn 18, conclusion checks only run on even turns
- **Maximum turns**: Hard cap at 25 turns forces conclusion

### 4.6 Reviewer Agent

**Problem**: Character output can drift from Karachi realism (e.g. Saleem speaking like a lawyer), violate logical consistency (e.g. refusing 20,000 rupees when earning 800/day), or repeat the same argument across turns.

**Solution**: A **ReviewerAgent** runs after each character response. It receives the character’s dialogue and action, the current world state, and the character’s previous lines. Using a dedicated LLM call with a Karachi-street-reviewer persona, it checks: (1) **Language realism** (e.g. rickshaw driver must speak mostly Urdu; constable must sound blunt, not polite), (2) **Logical consistency** (e.g. amounts and reactions must be plausible), (3) **Repetition** (same emotional appeal or argument again?), (4) **Action logic** (does the physical action fit the moment?). It returns `approved` (true/false), `severity` (minor/major), `issues[]`, and `suggestion`. If `approved` is false and severity is major, the narrative graph retries the character once with the reviewer’s suggestion appended to the context; otherwise the turn is accepted. Reviewer calls are logged in `prompts_log.json` for audit.

**Why a separate agent?** Keeping the reviewer separate from the character agent preserves a single responsibility per agent and allows the reviewer to use a harsher, “born-and-raised Karachiite” persona without polluting the character’s own prompt.

---

## 5. Design Decisions and Trade-offs

### 5.1 Code-Level vs. Prompt-Level Enforcement

A recurring challenge was that prompt-level instructions (e.g., "don't end the story yet", "speak different characters") were unreliable. The LLM would frequently ignore these constraints. Our solution was to move critical constraints to code-level enforcement:

| Constraint | Prompt-Level (Unreliable) | Code-Level (Reliable) |
|---|---|---|
| No consecutive same speaker | "NEVER pick same character" | `max_consecutive = 1` enforcement |
| Minimum story length | "Story should be 15+ turns" | `min_turns = 15` hard block |
| Minimum actions | "Ensure 5+ actions" | `action_count < 7` hard block |
| Story twist | "Inject complication at turn 10" | `STORY_TWISTS` injection at turn 9 |
| Anti-ping-pong | "Don't let 2 chars dominate" | 4-turn detection + forced switch |

**Trade-off**: Code-level enforcement is rigid — it can't adapt to narrative context. But the reliability gain far outweighs this limitation. The LLM still controls the creative content; code only enforces structural constraints.

### 5.2 Memory Window Size

We chose a sliding window of 20 entries per character. Smaller windows (10) caused characters to "forget" earlier events, while larger windows (30+) exceeded context limits. 20 entries covers approximately the last 10 turns of activity (each turn generates ~2 memory entries: dialogue + action).

### 5.3 Action Vocabulary Size

10 action types were chosen to balance expressiveness with reliability. Fewer actions (5) limited character behavior. More actions (15+) caused the LLM to hallucinate invalid action types. 10 types cover the key physical behaviors in a street accident scenario while remaining parseable.

---

## 6. Evaluation Results

### 6.1 Story Metrics (Latest Run)

| Metric | Value |
|---|---|
| Total Turns | 16 |
| Total Actions | 16 (1 per turn) |
| Unique Action Types Used | 7 of 10 |
| Twist Injected | viral_video (turn 9) |
| All 4 Characters Spoke | Yes |
| Conclusion Type | Negotiated settlement |
| Language Compliance | Saleem/Raza/Jameel speak Urdu; Ahmed code-switches |

### 6.2 Action Distribution

| Action Type | Count | Characters |
|---|---|---|
| Show_Item | 3 | Saleem |
| Record_Video | 3 | Ahmed, Uncle Jameel, Saleem |
| Block_Vehicle | 2 | Uncle Jameel |
| Confiscate_Keys | 1 | Constable Raza |
| Write_Challan | 2 | Constable Raza |
| Offer_Chai | 1 | Uncle Jameel |
| Sit_On_Ground | 1 | Saleem |
| Offer_Bribe | 1 | Ahmed Malik |
| Give_Money | 1 | Ahmed Malik |
| Call_Contact | 1 | Uncle Jameel |

### 6.3 Iterative Improvement

The system went through 8 development iterations, tracked via output comparison:

| Run | Turns | Actions | Key Change |
|---|---|---|---|
| 1-4 | 5-10 | 0-5 | Base implementation, adding memory/actions |
| 5-6 | 10 | 8-10 | Anti-repetition, min_turns, proper ending |
| 7 | 15 | 15 | Story phases, language rules, anti-pingpong |
| 8 | 16 | 16 | Story twist injection, conclusion resistance |

---

## 7. Conclusion

The system successfully demonstrates a multi-agent narrative where four autonomous characters with individual memories, goals, and action capabilities negotiate a street conflict in Karachi. A fifth agent (Reviewer) checks each turn for realism and consistency, with one retry on rejection. Key design insights include: (1) code-level enforcement is essential for structural constraints that LLMs tend to ignore, (2) per-character language rules with concrete examples significantly improve linguistic realism, (3) pre-written dramatic twists injected at fixed points create more interesting narratives than relying on the LLM to generate complications spontaneously, and (4) a dedicated reviewer agent improves output quality without overloading the character prompt.

---

## Appendix A: File Structure

```
GenAi_DSS/
├── src/
│   ├── main.py                    # Entry point
│   ├── config.py                  # StoryConfig dataclass
│   ├── schemas.py                 # Pydantic models (StoryState, DialogueTurn, etc.)
│   ├── actions.py                 # Action validation + execution
│   ├── story_state.py             # StoryStateManager
│   ├── agents/
│   │   ├── base_agent.py          # BaseAgent with LLM integration + logging
│   │   ├── character_agent.py     # CharacterAgent (reasoning + dialogue + action)
│   │   ├── director_agent.py      # DirectorAgent (speaker selection + conclusion)
│   │   └── reviewer_agent.py     # ReviewerAgent (Karachi realism + consistency check per turn)
│   ├── prompts/
│   │   ├── character_prompts.py   # Per-character language rules + prompt template
│   │   └── director_prompts.py    # Director prompts with story phases
│   └── graph/
│       └── narrative_graph.py     # LangGraph StateGraph + twist injection
├── examples/
│   └── rickshaw_accident/
│       ├── seed_story.json        # Story seed with setting details
│       └── character_configs.json # 4 character profiles with goals + inventory
├── story_output.json              # Generated narrative trace
├── prompts_log.json               # LLM interaction audit log
└── README.md                      # Setup + usage + feature documentation
```
