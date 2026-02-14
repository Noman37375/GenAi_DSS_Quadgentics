## ✅ Do’s
- **Follow the starter repo setup**: Make sure your system runs smoothly with the given instructions. Judges penalize heavily if code doesn’t execute.  
- **Implement mandatory components**:
  - Character memory (each agent tracks inventory, knowledge, perceptions).  
  - Action system (at least 5 distinct non-verbal actions within 25 turns).  
  - Reasoning layer (agents decide whether to talk or act).  
- **Respect technical constraints**:  
  - Max 25 turns.  
  - Context length and token limits.  
  - Use free/open-source models only.  
- **Produce required JSON outputs**:  
  - `story_output.json` (final narration trace).  
  - `prompts_log.json` (audit/debug log).  
- **Write clear documentation**: README + technical report explaining design choices, why you built it this way, and how to run it.  
- **Ensure originality**: Minimal reliance on AI-generated filler; show your own design thinking.  
- **Prepare for Q/A**: Be ready to explain architecture, agent interactions, and justify decisions.  

---

## ❌ Don’ts
- **Don’t rely only on dialogue**: Missing actions = weak story progression and lost marks.  
- **Don’t break JSON compliance**: Malformed or inconsistent files will cost points.  
- **Don’t exceed constraints**: More than 25 turns, ignoring token limits, or hallucinated state transitions = penalties.  
- **Don’t leave README vague**: If judges can’t run your code, you’ll be heavily penalized.  
- **Don’t copy-paste AI content blindly**: Overuse of auto-generated text without understanding design = low score.  
- **Don’t give incoherent narration**: Story must be logical, engaging, and consistent with agent personalities.