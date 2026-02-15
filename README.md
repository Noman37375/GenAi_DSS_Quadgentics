# GenAI_DSS: Multi-Agent Narrative System

## 1. Introduction

A **Multi-Agent Narrative System** built for the **Hackfest x Datathon 2026** Generative AI module. The system uses **LangGraph** to orchestrate autonomous character agents that navigate a conflict-driven story defined by a "Story Seed."

Unlike traditional chatbots, these agents possess:
- **Individual Memory** — each character tracks what they've seen, heard, and done.
- **Physical Actions** — agents perform non-verbal actions (blocking vehicles, confiscating keys, recording video) that change the world state.
- **Structured Reasoning** — agents "think" through their goals before deciding whether to talk, act, or both.
- **Dramatic Story Twists** — code-level event injection mid-story to break linearity and force characters to adapt.
- **Reviewer Agent** — a fifth agent checks each character turn for Karachi realism, logical consistency, and repetition; rejected turns get one retry with the reviewer’s suggestion.

## 2. Setup

### Prerequisites
- Python 3.11+
- `uv` package manager
- Google API Key (Gemini Free Tier)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/GenAi_DSS.git
   cd GenAi_DSS
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```ini
   GOOGLE_API_KEY=your_api_key_here
   ```

## 3. Usage

> [!IMPORTANT]
> **Mandatory Seed Story**: Uses the provided "Rickshaw Accident" seed story (`examples/rickshaw_accident/seed_story.json`).

To run the system:

```bash
uv run src/main.py
```

The system will:
1. Load the seed story and character configurations.
2. Initialize 4 character agents + 1 Director agent + 1 Reviewer agent.
3. Run the narrative loop (15-25 turns) with actions, memory updates, a dramatic twist, and per-turn reviewer checks.
4. Generate `story_output.json` and `prompts_log.json`.

## 4. Implemented Features

### 4.1 Character Memory System
Each character maintains an individual memory buffer (sliding window of 20 entries) that tracks:
- What they said and did in previous turns
- What other characters said and did (cross-character propagation)
- World events like story twists

Characters reference their memory when generating responses, ensuring continuity. Memory is stored in `StoryState.character_memories` as per-character lists.

### 4.2 Action System
10 distinct action types that produce tangible world-state changes:

| Action | Description | Requires Target |
|---|---|---|
| `Give_Money` | Hand over money | Yes |
| `Offer_Bribe` | Offer chai-pani / bribe | Yes |
| `Write_Challan` | Write traffic ticket | Yes |
| `Confiscate_Keys` | Take vehicle keys | Yes |
| `Record_Video` | Start recording on phone | No |
| `Block_Vehicle` | Physically block a vehicle | Yes |
| `Show_Item` | Show item to prove a point | No |
| `Call_Contact` | Call someone on phone | No |
| `Offer_Chai` | Bring chai to de-escalate | No |
| `Sit_On_Ground` | Sit in protest/despair | No |

Each action goes through **validation** (checks if action is allowed given current state) and **execution** (updates `world_state`, generates narration, propagates to character memories).

### 4.3 Reasoning Layer
Characters respond with structured JSON containing:
```json
{
    "reasoning": "Internal thought about what to do next",
    "decision": "talk | act | both",
    "dialogue": "Spoken words",
    "action": { "type": "ActionType", "target": "name or null", "description": "..." }
}
```
The `reasoning` field captures the agent's internal decision-making process — evaluating goals, assessing the situation, and choosing a strategy before speaking or acting.

### 4.4 Story Twist Injection
At turn 9, the system injects one of 4 dramatic twists (code-level, not LLM-dependent):
- **Flight Missed** — Ahmed's Dubai flight departs without him
- **Senior Officer Coming** — DSP inspection in 10 minutes, Raza panics
- **Viral Video** — Live stream hits 50,000+ views
- **Rickshaw Engine Dead** — Mechanic confirms 50,000 rupees damage

Twists update `world_state` and inject into ALL characters' memories, forcing them to adapt.

### 4.5 Director Intelligence
- **Story Phase System**: Setup (1-4) → Escalation (5-9) → Complication (10-15) → Resolution (16-22)
- **Anti-Repetition**: Code-level enforcement prevents same character speaking twice consecutively
- **Anti-Ping-Pong**: Detects when 2 characters dominate for 4+ turns and forces a third
- **Conclusion Resistance**: Post-twist breathing room, minimum action requirements, variable story length

### 4.6 Per-Character Language Rules
- **Saleem**: 95% Roman Urdu (uneducated street speaker)
- **Ahmed Malik**: English-Urdu code-switching (elite Karachiite)
- **Constable Raza**: 90% blunt street Urdu (authority figure)
- **Uncle Jameel**: 95% dramatic Urdu (neighborhood elder)

### 4.7 Reviewer Agent
A fifth agent runs after each character turn. It checks:
- **Language realism** — e.g. Saleem must not speak like a lawyer; Raza must sound blunt, not polite.
- **Logical consistency** — e.g. would a man earning 800/day refuse 20,000? Unrealistic amounts or reactions are rejected.
- **Repetition** — same emotional appeal or argument again?
- **Action logic** — does the physical action fit the moment?

If the reviewer rejects (major severity), the character gets **one retry** with the reviewer’s suggestion in context. Reviewer calls are logged in `prompts_log.json`.

## 5. System Architecture

```
┌──────────────────────────────────────────────────┐
│                  NarrativeGraph                   │
│              (LangGraph StateGraph)               │
│                                                   │
│  ┌─────────────┐    ┌──────────────────┐    ┌──────┐
│  │  Director    │───>│ Character Agent   │───>│Review│
│  │  Selects     │    │ Responds (with    │    │  er  │
│  │  Speaker +   │    │ reasoning, action │    │(real-│
│  │  Narration   │    │ + dialogue)       │    │ism)  │
│  └──────┬───────┘    └────────┬─────────┘    └──┬───┘
│         │                     │    retry if reject
│         │    ┌────────────────┘                    │
│         │    │                                     │
│         ▼    ▼                                     │
│  ┌──────────────────┐                              │
│  │ Check Conclusion  │──── continue ───> Director  │
│  │ (min turns, min   │                             │
│  │  actions, twist   │──── conclude ───> END       │
│  │  breathing room)  │                             │
│  └──────────────────┘                              │
│                                                    │
│  Twist Injection @ Turn 9                          │
│  Memory Updates after each turn                    │
│  Action Validation + Execution                     │
└──────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|---|---|
| `src/main.py` | Entry point — loads config, initializes agents, runs graph |
| `src/schemas.py` | Pydantic models: `StoryState`, `CharacterProfile`, `DialogueTurn` |
| `src/config.py` | Configuration: turns, temperature, model settings |
| `src/actions.py` | Action validation, execution, world-state updates |
| `src/graph/narrative_graph.py` | LangGraph workflow, twist injection, conclusion logic |
| `src/agents/character_agent.py` | Character agent with structured JSON reasoning |
| `src/agents/director_agent.py` | Director agent with speaker selection + anti-repetition |
| `src/agents/reviewer_agent.py` | Reviewer agent — Karachi realism and consistency per turn |
| `src/prompts/character_prompts.py` | Character prompts with per-character language rules |
| `src/prompts/director_prompts.py` | Director prompts with story phases |

## 6. Output Files

**`story_output.json`** — Final narrative trace:
- `title`, `seed_story` (metadata)
- `events[]` — chronological list with `type` (dialogue/narration/action), `speaker`, `content`, `turn`
- `conclusion` — why the story ended

**`prompts_log.json`** — Debug/audit log:
- `timestamp`, `agent`, `prompt`, `response` for every LLM call (Director, Character, Reviewer)

## 7. Configuration

| Parameter | Default | Description |
|---|---|---|
| `model_name` | `gemma-3-27b-it` | LLM model (Google Generative AI) |
| `temperature` | `0.7` | Creativity vs consistency |
| `max_turns` | `25` | Maximum dialogue turns |
| `min_turns` | `15` | Minimum before conclusion allowed |
| `max_tokens_per_prompt` | `2000` | Max generation tokens |
| `max_context_length` | `4000` | Max input context |
| `max_consecutive_same_character` | `1` | Anti-repetition threshold |
| `num_characters` | `4` | Number of character agents |
