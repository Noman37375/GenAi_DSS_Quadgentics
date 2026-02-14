# [cite_start]Hackfest x Datathon 2026: Generative AI Problem Statement [cite: 1]

## 1. Introduction
[cite_start]The Generative AI module of the Hackfest x Datathon challenges participants to move beyond linear text generation[cite: 3]. [cite_start]You are required to design a **Multi-Agent Narrative System** where autonomous agents navigate a world defined by a "Story Seed"[cite: 4]. Unlike traditional chatbots, these agents must possess:
* [cite_start]A sense of **agent memory**[cite: 5].
* [cite_start]The ability to execute **non-verbal actions** to resolve conflicts and achieve goals[cite: 5].

---

## 2. Resources & Tooling

### 2.1 Base Repository
[cite_start]A starter codebase, including environment configurations and the initial story seed, is provided at: [https://github.com/itbaans/GenAi_DSS](https://github.com/itbaans/GenAi_DSS)[cite: 8, 9].

### 2.2 Configuration and Technical Constraints
[cite_start]The repository includes critical parameters that must be respected[cite: 11]:
* [cite_start]**Context Length (`max_context_length`)**: The maximum token limit for the entire input buffer, including character memory and prompt construction[cite: 12].
* [cite_start]**Max Tokens Per Prompt (`max_tokens_per_prompt`)**: The maximum limit for a single model generation/output[cite: 13].
* [cite_start]**Character Profiles**: Specific persona traits, goals, and starting inventories that define agent behavior[cite: 14].
* [cite_start]**Dialogue Turns (`max_turns`)**: The simulation is strictly limited to a maximum of **25 turns**[cite: 15].
* [cite_start]**Temperature**: Participants may fine-tune this to balance creative narration and logical consistency[cite: 16].

### 2.3 Model Restrictions
* [cite_start]Participants are encouraged to use **Open-Source models** or **Free APIs** (e.g., Google Gemini Free Tier)[cite: 19].
* [cite_start]The system must be designed to run effectively in a standard development environment without requiring paid credits[cite: 20].

---

## 3. System Architecture

### 3.1 The Director (Pre-defined)
[cite_start]The Director is the primary controller of the narrative, already implemented in the codebase[cite: 24, 25]. Its roles include:
* [cite_start]**Turn-Taking**: Managing which character speaks or acts next[cite: 27].
* [cite_start]**Narrative Pacing**: Ensuring the story adheres to the Story Seed and reaches a conclusion within 25 turns[cite: 28].
* [cite_start]**Context Management**: Providing agents with environmental data[cite: 29].

### 3.2 Character Personas (Pre-defined)
[cite_start]Each character has specific personality traits designed to drive friction[cite: 31]. [cite_start]Agents must maintain a **consistent voice** based on these traits[cite: 32].

### 3.3 Mandatory Components for Implementation
[cite_start]Participants must implement the following agentic functions[cite: 33, 34]:
* [cite_start]**Character Memory**: Individual memory buffers to track knowledge, inventory, and perceptions of others[cite: 35, 36].
* [cite_start]**Action System**: A mechanism for non-verbal behaviors that result in tangible updates to the Story State[cite: 37, 38].
* [cite_start]**Reasoning Layer**: A process where agents "think" through goals to decide whether to **Talk or Act**[cite: 39, 40].

---

## 4. Interaction and Action Requirements
* [cite_start]**Turn Limit**: Strictly limited to a total of 25 dialogue turns[cite: 42].
* [cite_start]**Action Frequency**: Within these turns, the system must trigger at least **5 distinct Actions**[cite: 43].
* [cite_start]**Action Logic**: Agents should "decide" to act when dialogue is insufficient to reach a goal[cite: 45].
* [cite_start]**Purpose**: Actions serve to break dialogue loops and force the narrative forward (e.g., *Search Object*, *Trade_Item*, *Unlock Door*)[cite: 47].

---

## 5. Deliverables & Output Files

### 5.1 Narration Output (`story_output.json`)
[cite_start]Records the final narrative trace, including[cite: 51, 52]:
* [cite_start]**Metadata**: Title and seed story description[cite: 53].
* [cite_start]**Events**: Chronological list of turns with type (`dialogue` or `narration`), speaker, content, and turn number[cite: 54, 55, 56, 57, 58].
* [cite_start]**Conclusion**: Why the story ended[cite: 59].

### 5.2 Prompts Log (`prompts_log.json`)
[cite_start]A debug/audit log tracking: timestamp, agent name, the full prompt sent, and the raw LLM response[cite: 60, 61, 62, 63, 64, 65].

### 5.3 Technical Submission
* [cite_start]**Technical Report**: A PDF (LaTeX) describing architecture and action logic[cite: 67].
* [cite_start]**Codebase**: Modular, commented code with a clear `README.md`[cite: 68].

---

## 6. Evaluation Criteria
[cite_start]Metrics include **Story Completion**, **Character Consistency**, **Memory Tracking**, and **Director Effectiveness**[cite: 71, 72].

> [!WARNING]
> [cite_start]**Penalty Warning**: If the evaluation team is unable to run your code or view the generated narration using the provided instructions, the submission will be heavily penalized[cite: 73, 74].