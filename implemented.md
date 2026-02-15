# Implemented Checklist — GenAI_DSS Multi-Agent Narrative System

This file tracks every implemented feature, why it was implemented, and the exact code changes applied.

---

## Claude session context (where work left off)

A previous Claude Code session hit its limit while integrating the **ReviewerAgent**. The plan was:

1. **ReviewerAgent** had been created (`src/agents/reviewer_agent.py`) to check each character turn for **Karachi realism**, **logical consistency**, **repetition**, and **action logic** — so output "makes sense as a Karachi person."
2. **Not yet done**: Wire the Reviewer into the narrative graph and main.

**Completed in this pass:** ReviewerAgent is now integrated: it runs after each character response; if it rejects (major issues), the character gets one retry with the reviewer’s suggestion in context. Reviewer logs are included in `prompts_log.json`.

---

## Checklist

- [x] **Schemas**: CharacterProfile has goals and inventory; StoryState has memory and world_state; Action model defined.
- [x] **Character configs**: character_configs.json includes goals and inventory per character.
- [x] **Memory**: Per-character memory populated and used in get_context_for_character and prompts.
- [x] **Dialogue context**: When a character speaks, context includes their own previous dialogues and the other party's previous dialogues so responses stay logical.
- [x] **Director improvement**: Director sees character descriptions + goals when selecting speaker; anti-repetition instruction prevents same 2 characters looping.
- [x] **Scene detail enrichment**: Seed story and character configs now have concrete details (BMW brand, colors, damage specifics) so LLM never guesses facts.
- [x] **Anti-repetition hard enforcement**: Code-level block prevents same speaker more than max_consecutive times — LLM can't override.
- [x] **min_turns hard enforcement**: Code-level block prevents conclusion before min_turns (15) — no more short stories.
- [x] **Proper story ending**: Conclusion prompt requires detailed resolution with each character's fate, crowd, environment, and emotional beat.
- [x] **No-double-turn**: max_consecutive changed to 1 — no character speaks twice in a row. Anti-PingPong prevents same 2 chars for 4+ turns.
- [x] **Per-character language rules**: Saleem=95% Urdu, Raza=90% blunt Urdu, Jameel=95% dramatic Urdu, Ahmed=English-Urdu mix.
- [x] **Story phases + dramatic twists**: Director follows 4-phase structure (Setup→Escalation→Complication→Resolution). min_turns=15.
- [x] **Anti-dialogue-repetition**: Characters see their own previous lines + used actions, MUST say something new and pick different actions.
- [x] **Story twist injection**: At turn 9, a random dramatic twist is injected (flight missed / DSP coming / viral video / engine dead) that all characters react to.
- [x] **Story length variation**: Conclusion only checked on even turns before turn 18, plus 5-turn breathing room after twist.
- [x] **Natural action frequency**: Actions only when situation demands — not forced every turn. Min actions reduced to 5.
- [x] **Code-level action repeat blocking**: Same action type blocked per character (except Give_Money/Offer_Bribe). No more Show_Item 3x.
- [x] **Stronger anti-repetition context**: Characters see explicit rules — "If you already talked about children, do NOT mention children again."
- [x] **Director narration anti-repetition**: Director told to vary environmental details, not repeat "heat shimmering off asphalt."
- [x] **README updated**: Full feature documentation, architecture diagram, configuration table, key files. Removed "Missing Features" section.
- [x] **Technical Report created**: Technical_Report.md with architecture, design decisions, trade-offs, evaluation results.
- [x] **ReviewerAgent integrated**: Fifth agent reviews each character turn for Karachi realism, language, repetition, and action logic; rejects major issues with one retry using reviewer suggestion.
- [x] **FastAPI + frontend integration**: Backend API (src/api.py) with POST /api/run, GET /api/story (200 + empty when no story), GET /api/run/stream (SSE). Frontend uses EventSource for turn-by-turn streaming; Next disabled on last turn while streaming, auto-advance when new turn arrives. Root package.json runs both via concurrently (dev, dev:frontend, dev:api).

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
| `_build_character_context()` (new method) | Builds a complete context string for any character, including: initial event, director narration, goals, inventory, memory facts (last 10), and recent dialogue (last 15 turns showing all speakers). |
| `_character_respond_node()` updated | Now calls `_build_character_context()` instead of building context inline. |
| `run()` updated | Now accepts and passes `character_memories` to the initial state so memory persists from the start. |

**File: `src/main.py`**

| Change | What was done |
|--------|---------------|
| `story_graph.run()` call updated | Now passes `character_memories=story_manager.state.character_memories` so the graph starts with initialized memory buffers. |

---

## 5. Director Improvement (Character Descriptions + Anti-Repetition)

**Why:** The Director previously only saw a flat list of character names with zero context about who they are. By giving the Director each character's description and goals, it can make smarter decisions — bringing in a mediator when tension rises, an authority figure when things get chaotic, etc.

### Applied Changes

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| `{available_characters}` → `{character_descriptions}` | Prompt now expects character descriptions with goals, not just names |
| Anti-repetition rule added | "If the last 3-4 turns are between the same 2 characters, MUST pick a different character" |
| Role-based guidance added | Use each character's personality/goals to decide when they'd naturally intervene |

**File: `src/agents/director_agent.py`**

| Change | What was done |
|--------|---------------|
| `select_next_speaker()` updated | Now builds formatted string with each character's name, description, and goals |

---

## 6. Scene Detail Enrichment (Fix Factual Inconsistency)

**Why:** The seed story said "a car" with no brand, color, or damage specifics. The LLM invented different car brands each turn. The fix: bake concrete facts into the source data so every agent prompt has the same ground truth from turn 1.

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

## Progress Analytics

### Run Comparison Chart

| Metric | Run 1 | Run 2 | Run 3 | Run 4 | Run 8 | Run 9 | **Run 10** |
|--------|-------|-------|-------|-------|-------|-------|-------------|
| **Changes applied** | None | 1-4 | 1-6 | 1-11 | 1-20 | 1-23 | **1-26 (Reviewer)** |
| **Total turns** | 11 | 20 | 11 | 9 | 16 | 16 | **22** |
| **Total actions** | 0 | 0 | 0 | 9 | 16 (forced) | 9 (natural) | **5 (min met)** |
| **Actions blocked/rejected** | — | — | — | — | 0 | 3 (repeat) | **3 (target: crowd/null)** |
| **Turns with NO action** | 11 | 20 | 11 | 0 | 0 | 7 | **17** |
| **Story twist** | None | None | None | None | viral_video | senior_officer_coming | **Director: dhaba blast** |
| **Reviewer active** | — | — | — | — | — | — | **Yes (reject + retry)** |
| **Ending realism** | OK | Weak | Best | Abrupt | Saleem 20k reject | 15k + Raza 5k | **55k + Raza 5k (realistic)** |
| **Dialogue repetition** | N/A | Yes | No | Some | High | Medium | **Medium (Reviewer retries)** |
| **Overall rating** | 6/10 | 4/10 | 8.5/10 | 8.5/10 | 7.5/10 | 8.5/10 | **7.5–8/10** |

### Progress Trend

```
Quality
  10 |
   9 |              * Run 3 (8.5)    * Run 4 (8.5)                    * Run 9 (8.5)
   8 |                                               * Run 8 (7.5)
   7 |
   6 |  * Run 1 (6.0)
   5 |
   4 |        * Run 2 (4.0)
   3 |
   2 |
   1 |
   0 +------+------+------+------+------+------+
     Orig   1-4    1-6    1-11   1-20   1-23
```

### Key Observations — Run 9 (After Changes 21-23)

**What improved:**
- **Actions natural**: 9 actions in 16 turns (vs 16/16 in Run 8). 7 turns are talk-only — characters speak when speaking makes sense.
- **Repeat actions blocked**: 3 actions blocked by code (Saleem Show_Item, Jameel Call_Contact, Raza Write_Challan, Ahmed Call_Contact)
- **Different twist fired**: senior_officer_coming (was viral_video in Run 8) — confirms randomization working
- **Ending realistic**: Ahmed pays 15,000, Raza pockets 5,000. Much more believable than Run 8 (Saleem rejecting 20k).
- **Ahmed has talk-only turns**: Turns 2 and 14 are pure dialogue — no forced action. Realistic.

**What still needs work:**
- Saleem still repeats themes (rickshaw/children/gareeb) across multiple turns
- Uncle Jameel still repeats "Poora Karachi jaanta hai Jameel bhai kaun hai" and "Inspector Farooq"
- Director narration phrases still repeat ("heat shimmering off the asphalt")
- These are semantic repetition issues — harder to fix at code level

### Key Observations — Run 10 (After Change 26: ReviewerAgent + Director-generated twist)

**Note:** Run 10 transcript in compare.md may be partial (terminal length). Analysis based on available output.

**What’s working (revision is helping):**
- **ReviewerAgent is active:** Multiple [Reviewer] entries — Minor issues (e.g. Raza’s “lakh dena padega” slightly high), and **REJECTED + Retry** for Saleem (theatrical/poetic dialogue, repetition of children appeal) and Ahmed (50k unrealistic, performative “Allah khair kare”). Retries produced simpler, more in-character lines. So the revision (Reviewer) **is improving quality**, not worsening it.
- **Director-generated twist:** Dhaba gas cylinder explosion — fresh, context-aware, not from a fixed list. Story adapts (dhaba jal gaya, 55k settlement includes that).
- **Ending realistic:** 55,000 rupees settlement, Raza pockets 5,000, Ahmed missed flight. Coherent and Karachi-plausible.
- **No action repeat spam:** Only 5 actions in 22 turns — minimum met, no forced action every turn.

**Concerns (not “worse”, just trade-offs):**
- **Only 5 actions in 22 turns:** Story is very talk-heavy (17 talk-only turns). Rubric requires “at least 5 distinct actions” — met, but if judges want more visible physical behaviour, consider nudging prompt slightly (e.g. “consider a physical action when it would change the situation”), without forcing.
- **Actions rejected for target:** `Show_Damage → crowd` and `Wave_Down_Traffic → null`, `Wave_Down_Passerby → null` rejected (Unknown target). Open-ended actions need **valid targets** (character names or explicit “no target” in schema). Prompt should say: target must be a character name or leave blank for no-target actions.
- **Saleem/Jameel repetition:** Despite Reviewer retries, themes (bachche, rickshaw, Inspector Zubair) still recur. Reviewer is cutting the worst lines; full semantic variety would need even stronger persona/anti-repetition in character prompt.

**Verdict:** Revision (Reviewer + Director twist + current system) is **not making the system worse**. It is **raising the floor**: bad dialogue gets rejected and retried, twist is dynamic, ending stays realistic. Trade-off: fewer actions per run and some valid-seeming actions rejected due to target validation. Next steps: (1) Clarify in prompt that action target must be a character name or empty; (2) Optionally soften “only act when necessary” so 6–8 actions in 20+ turns is more likely without forcing.

---

## 7-11. Action System, Reasoning Layer, World State, Director Upgrade, Karachi Realism

*(Changes 7-11 documented in detail below — unchanged from previous version)*

### 7. Action System (`src/actions.py`)
Originally: 10 scenario-specific actions with validation and execution pipeline. **Later overhauled** (see changes 21-23, then full rewrite to open-ended system): now uses pattern-matching on free-form action types instead of a fixed menu. Each action still updates world_state and propagates to all character memories.

### 8. Reasoning Layer (Structured Character Output)
Characters respond with JSON: `reasoning`, `decision` (talk/act/both), `dialogue`, `action`. Forces explicit think-before-act.

### 9. Narrative Graph: Action Execution & World State Propagation
Graph processes character actions: validate → execute → update world_state → emit events → propagate memories.

### 10. Director Upgrade for Actions & World State
Director sees world_state and action_count in both speaker selection and conclusion prompts.

### 11. Karachi Realism Overhaul
Seed story and character configs enriched with Karachi-specific details: crowd dynamics, phone recording, physical actions, blunt police language, 40°C heat.

---

## 12-14. Anti-Repetition, min_turns, Proper Ending

### 12. Anti-Repetition Hard Code Enforcement
Code-level block prevents same speaker consecutively, regardless of LLM output.

### 13. min_turns Hard Code Enforcement
Code hard-blocks conclusion before `min_turns` (15). Max_turns (25) forces conclusion as safety net.

### 14. Proper Story Ending
Conclusion prompt requires: resolution details, each character's fate, crowd reaction, environment closing, final emotional beat. 4-6 sentences minimum.

---

## 15-17. No-Double-Turn, Language Rules, Story Phases

### 15. max_consecutive = 1
Zero tolerance for double turns. Anti-PingPong prevents same 2 chars for 4+ turns.

### 16. Per-Character Language Rules
Saleem=95% Roman Urdu, Raza=90% blunt Urdu, Jameel=95% dramatic Urdu, Ahmed=English-Urdu mix. Each with WRONG/RIGHT examples.

### 17. Story Phases + Dramatic Twist Instructions
Director follows 4-phase structure. min_turns raised to 15. Conclusion hardened with multiple requirements.

---

## 18-20. Anti-Dialogue-Repetition, Twist Injection, Story Length Variation

### 18. Anti-Dialogue-Repetition + Anti-Action-Repetition
Characters see their own previous lines + used actions with "DO NOT REPEAT" instructions.

### 19. Story Twist Injection System
4 code-level twists (flight_missed, senior_officer_coming, viral_video, rickshaw_worse) injected at turn 9. Updates world_state and all character memories.

### 20. Story Length Variation
Post-twist breathing room (5 turns). Conclusion only on even turns before turn 18. Stories vary between 16-22 turns.

---

## 21-23. Natural Actions, Code-Level Action Blocking, Stronger Context

### 21. Natural Action Frequency (Change 21)

**Why:** Run 8 had 16 actions in 16 turns — every single turn had a forced action. This is unnatural. Real people don't perform a physical action every time they speak. Characters should talk when talking makes sense, and act only when the situation demands it.

**Applied Changes:**

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| Min actions threshold | Changed from `7` to `5` — story only needs 5 meaningful actions |

**File: `src/prompts/character_prompts.py`**

| Change | What was done |
|--------|---------------|
| Action pressure removed | Changed "Physical actions matter more than words" → "Only perform action when situation truly demands it" |
| Talk-only encouraged | Added "It is perfectly fine to choose decision: 'talk' with no action if you have nothing physical to do" |

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| Action pressure removed | Removed "pick characters likely to perform physical actions" from Director rules |

### 22. Code-Level Action Repeat Blocking (Change 22)

**Why:** Run 8 had Show_Item 3x, Block_Vehicle 2x, Record_Video 3x by same characters. Even with prompt-level "pick different ones", the LLM repeated. Now code blocks it.

**Applied Changes:**

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| Repeat action detection | Before executing any action, code checks if this character already performed this action type |
| `REPEATABLE_ACTIONS` set | Only `Give_Money` and `Offer_Bribe` can repeat (logically someone can pay/bribe twice) |
| All others blocked | If character already did Show_Item, system rejects Show_Item again. Prints `>> Action BLOCKED (repeat)` |

### 23. Stronger Anti-Repetition Context + Director Narration Variety (Change 23)

**Why:** The generic "DO NOT REPEAT" instruction wasn't specific enough. Characters kept repeating themes (children, rickshaw, gareeb). Director kept saying "heat shimmering off the asphalt."

**Applied Changes:**

**File: `src/graph/narrative_graph.py`**

| Change | What was done |
|--------|---------------|
| Specific anti-repetition rules | "If you already talked about your children, do NOT mention children again" |
| New-point requirement | "Think: What has CHANGED since I last spoke? What NEW information do I have?" |
| Action is optional emphasis | "If talking is enough, JUST TALK. Not every turn needs an action." |

**File: `src/prompts/director_prompts.py`**

| Change | What was done |
|--------|---------------|
| Narration variety rule | "If you already described heat shimmering, use a DIFFERENT detail" |
| Alternative details given | "smell of diesel, bus conductor shouting, hawker selling water bottles, child weaving through traffic" |

---

## Documentation (Changes 24-25)

### 24. README Updated

**Why:** README was the original starter kit — said "LACKS advanced features" and "Missing: Actions, Memory, Reasoning." A judge reading this would think nothing was implemented. Completely rewritten to show all implemented features, architecture, configuration, and key files.

### 25. Technical Report Created

**Why:** Rubric requires a PDF/LaTeX technical report (20 marks for Documentation). Created `Technical_Report.md` covering: system architecture, all 3 mandatory components with design rationale, 5 novel extensions, design trade-offs, evaluation results, and file structure.

---

### 26. ReviewerAgent Integrated

**Why:** User requested "another agent who looks at achieved output and turn and makes it logical and make sense as a Karachi person." The ReviewerAgent was already implemented in `src/agents/reviewer_agent.py` but was not yet wired into the graph. Integration ensures every character turn is checked for: (1) **Language realism** (e.g. Saleem not speaking like a lawyer, Raza not overly polite), (2) **Logical consistency** (e.g. would a man earning 800/day refuse 20,000?), (3) **Repetition** (same argument or emotional appeal again?), (4) **Action logic** (does the physical action fit the moment?). Major issues cause rejection and one retry with the reviewer’s suggestion in context; minor issues are approved with notes. Reviewer logs are written to `prompts_log.json` for audit.

**Applied changes:**

| File | Change |
|------|--------|
| `src/graph/narrative_graph.py` | Import `ReviewerAgent`. `NarrativeGraph.__init__` accepts optional `reviewer: Optional[ReviewerAgent] = None`. In `_character_respond_node`, after `character.respond()`, call `reviewer.review_turn()`. If not approved and feedback present, retry once with context `context + "\n\n=== REVIEWER FEEDBACK (you must address this) ===\n" + feedback`. |
| `src/main.py` | Import `ReviewerAgent`. Create `reviewer = ReviewerAgent(config)`. Pass `reviewer` to `NarrativeGraph(config, characters, director, reviewer)`. Append reviewer logs to `all_logs` before writing `prompts_log.json`. |

---

## 27. FastAPI + Frontend Integration & Streaming

**Why:** The frontend needed to run the full narrative via the backend (no pre-baked story). To avoid long waits (2–5 min), the backend streams each **reviewed** turn over SSE so the user sees turns as they are ready instead of waiting for the whole run. GET /api/story returns 200 with an empty payload when no story exists (no 404 in console).

### Applied Changes

| File | Change |
|------|--------|
| **pyproject.toml** | Added `fastapi>=0.115.0`, `uvicorn>=0.32.0`. |
| **package.json** (repo root) | New. Scripts: `dev` = concurrently frontend + API, `dev:frontend` = cd to frontend + npm run dev, `dev:api` = uv run uvicorn src.api:app --reload --port 8000. DevDependency: `concurrently`. |
| **src/api.py** (new) | FastAPI app, CORS for localhost:5173 / 127.0.0.1:5173. In-memory `last_story`. `events_to_frontend_turns()` maps backend events (dialogue/narration/action) to frontend shape (title, scenario, turns, conclusion); speaker → character key (Saleem→saleem, Ahmed Malik→ahmed, etc.); optional `actionText` per turn. `run_narrative()` = same setup as main (seed_story, character_configs, graph); `_build_graph_and_state()` for streaming. **POST /api/run**: runs full narrative, transforms, stores in `last_story`, writes story_output.json & prompts_log.json, returns payload. **GET /api/story**: returns `last_story` or `{ title: null, scenario: null, turns: [], conclusion: null }` (200, no 404). **GET /api/run/stream**: SSE stream; sends `meta` (title, scenario), then per `character_respond` chunk `turns` (newTurns), then `conclusion` from check_conclusion, then `done`; uses `graph.astream(initial_state, stream_mode="updates")`; sets `last_story` at end. |
| **Hackthon_Frontend_IBA/frontend/src/App.jsx** | `storyData` in state (initial null). API base from `VITE_API_URL` (default http://localhost:8000). On mount: GET /api/story; if body has turns, set storyData. **Start story**: EventSource GET /api/run/stream; on `meta` set storyData (title, scenario, turns: []); on `turns` append newTurns and **auto-advance** if user was on previous last turn; on `conclusion` set conclusion; on `done` close EventSource, set currentTurn -1, isLoading false. Entry screen when no story or empty turns and not loading. "Streaming story" message when loading and turns.length === 0. **Next button**: disabled when `isConclusion` OR (`isLoading` and on last turn) so it stays disabled until the next turn is generated; when new turn arrives, Next enables and view auto-advances if on last turn. Display uses storyData?.title, scenario, turns, conclusion; optional actionText under dialogue. Nav/progress/character list only when storyData set. |

### Current run / build

| Command | Where | What it does | Typical output (excerpt) |
|---------|--------|--------------|---------------------------|
| **npm run dev** | Repo root | Starts frontend (Vite) and API (uvicorn) with concurrently | `[0] Vite v7.x ... ready at http://localhost:5173` and `[1] INFO: Uvicorn running on http://127.0.0.1:8000` |
| **npm run dev:frontend** | Repo root | Only frontend: `cd Hackthon_Frontend_IBA/frontend && npm run dev` | Vite dev server on 5173 (uses esbuild under the hood for deps, Vite for serve/HMR) |
| **npm run dev:api** | Repo root | Only API: `uv run uvicorn src.api:app --reload --port 8000` | `INFO: Uvicorn running on http://127.0.0.1:8000`; may show pyproject TOML warning for `python-version` in `[tool.uv]` |
| **uv run uvicorn src.api:app --reload --port 8000** | Repo root | Same as dev:api; **uv** resolves env and runs uvicorn | Same as above |
| **npm run dev** (in frontend) | Hackthon_Frontend_IBA/frontend | Vite dev server only | `VITE v7.x ready at http://localhost:5173` |
| **npm run build** (in frontend) | Hackthon_Frontend_IBA/frontend | Vite production build | `vite v7.x building for production...` then `dist/` output |

**Note:** Frontend dev uses **Vite** (which uses **eslint** for lint; build is Rollup/esbuild-based). Backend uses **uv** for dependency and env management and **uvicorn** as the ASGI server.

---

## 28. Documentation Overhaul — README + Technical Report Updated to Match Current System

**Why:** The README and Technical Report were written when the system still used hardcoded actions (10-item menu), hardcoded twists (4 random choices), simple language rules, and temperature 0.7. Since then, the system was completely overhauled: open-ended actions with pattern-matching, deep psychological personas with tactical evolution, LLM-generated twists, Reviewer Agent, FastAPI + React frontend with SSE streaming, and temperature 0.75. Documentation must accurately describe the CURRENT system for judges.

**Applied Changes:**

| File | What Changed |
|------|-------------|
| **README.md** | Complete rewrite. Now documents: open-ended action system (pattern table instead of fixed menu), deep psychological personas, LLM-generated twists, Reviewer Agent, FastAPI + SSE streaming, frontend setup/usage. Architecture diagram updated. Config table shows temperature 0.75. Key files table includes api.py and frontend. Setup instructions include frontend (npm install, npm run dev). |
| **Technical_Report.md** | Complete rewrite. Section 3.2 (Actions): now describes open-ended pattern-matching system with code examples, explains WHY we moved from fixed menu to open-ended (repetition, limited expressiveness, artificial feel). Section 3.3 (Reasoning): now describes deep personas with psychology/tactical evolution, explains WHY deep personas vs simple rules. Section 4.1 (Twists): now describes LLM-generated twists via DIRECTOR_TWIST_PROMPT, explains WHY LLM-generated vs hardcoded (repetition across runs, context mismatch). Section 4.6 (new): SSE streaming. Section 5 (Trade-offs): updated tables for open-ended vs fixed menu, reviewer vs stronger prompts. Section 6 (Evaluation): includes Run 10 data with reviewer catches. Appendix: file structure includes api.py, frontend directory. |

**Key documentation changes by topic:**

| Topic | OLD (inaccurate) | NEW (matches code) |
|-------|-------------------|---------------------|
| Actions | "10 action types: Give_Money, Offer_Bribe..." with VALID_ACTIONS table | Open-ended with pattern-matching; any action valid; 13 pattern categories |
| Twists | "4 pre-written twists randomly selected" | LLM-generated via DIRECTOR_TWIST_PROMPT, unique per run |
| Personas | "Per-character language rules with WRONG/RIGHT examples" | Deep psychological personas with PSYCHOLOGY, LANGUAGE, TACTICAL EVOLUTION, NEVER DO |
| Temperature | 0.7 | 0.75 |
| Architecture | No frontend, no API | FastAPI + React + SSE streaming documented |
| Design rationale | "Why scenario-specific actions? Generic actions don't produce meaningful state changes" | "Why open-ended? Fixed menu caused repetition, limited emergent behavior, felt artificial" |
| Twist rationale | "Why code-level, not prompt-level? Prompt instructions unreliable" | "Why LLM-generated? Hardcoded twists repeated across runs and didn't fit specific context" |

---

### Issues Remaining
- [x] ~~No Technical Report~~ → Created (Technical_Report.md)
- [x] ~~README says "Missing Features"~~ → Rewritten with full feature docs
- [x] ~~Actions forced every turn (16/16)~~ → Natural (9/16 in Run 9)
- [x] ~~Same action repeated (Show_Item 3x)~~ → Open-ended system eliminates fixed-menu repetition
- [x] ~~Documentation describes old system~~ → README + Technical Report fully updated to match current code
- [ ] Dialogue theme repetition (Saleem: children/rickshaw/gareeb) — Reviewer catches worst cases, some recurrence remains
- [ ] Technical_Report.md needs conversion to PDF for submission

### Do's & Don'ts Compliance

| Requirement | Status | Notes |
|------------|--------|-------|
| Character memory | ✅ Done | Per-character, 20-fact sliding window |
| Action system (≥5 actions) | ✅ Done | 9 natural actions in Run 9, 8 unique types |
| Reasoning layer (Talk vs Act) | ✅ Done | Structured JSON with reasoning field |
| Max 25 turns | ✅ Done | 16 turns in Run 9 |
| Free/open-source models | ✅ Done | Gemma 3 27B IT |
| story_output.json | ✅ Done | With events, conclusion, metadata |
| prompts_log.json | ✅ Done | Timestamped audit log |
| Not dialogue-only | ✅ Done | 9 physical actions (natural frequency) |
| Coherent narration | ✅ Done | Logical, engaging, consistent |
| JSON compliance | ✅ Done | Verified structure matches spec |
| Clear README | ✅ Done | Full feature docs, architecture, config |
| Technical Report | ✅ Done | Technical_Report.md (needs PDF conversion) |
| Originality / design thinking | ✅ Done | Twist injection, code-level enforcement, per-character language, ReviewerAgent |
| Actions not forced | ✅ Done | 7 talk-only turns in Run 9 |
| Action variety | ✅ Done | 8 unique types, repeats blocked by code |

---

*Last updated: Change 27 — FastAPI + frontend integration, GET/POST/stream endpoints, SSE turn-by-turn streaming, Next disabled on last turn while streaming with auto-advance when new turn arrives; run commands (npm run dev, uv, Vite/esbuild) documented.*
