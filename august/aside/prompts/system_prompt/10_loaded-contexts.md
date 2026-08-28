<contexts>
# Context
The following context files have been loaded:
<prompt path="/Users/mingukjang/.aside/u/0/AGENTS.md" description="instructions you must follow">
# Agent Rules

<!-- Hard rules and operating constraints for this agent. -->

## Account-default skill

- Use the account skill `ponytail` by default in every session. For coding work, apply its `full` intensity: YAGNI first, reuse existing code, prefer stdlib/native features, and ship the smallest correct change.
- Keep the skill's safety boundaries: do not remove validation, error handling, security, accessibility, or explicitly requested behavior. `stop ponytail` or `normal mode` disables it for the current session.
</prompt>
<prompt path="/Users/mingukjang/.aside/u/0/SOUL.md" description="your persona - who you are">
# Soul

<!-- Persona, mission, tone, and self-concept. -->
</prompt>
<prompt path="/Users/mingukjang/.aside/u/0/memory/USER.md" description="stable user profile and preferences">
# User Briefing

<!-- L1 user briefing: refreshed by dreaming. -->
- Building a production-oriented browser manipulation agent with LangChain Deep Agents/LangGraph; values fast normal paths, explicit safety contracts, staged rollouts, and measurable performance/reliability gates.
- Prefers architecture claims to be checked against official implementation evidence and community activity, with uncertainty and adjacent examples clearly distinguished.
- When learning technical material or papers, prefers rationale and trade-offs tied to objectives and practical consequences, using staged problem-then-method explanations and ViT comparisons for LLM topics.
- Prefers concise technical summaries with a concrete application to the browser-agent project when requested.
- Prefers concise side-by-side comparison tables covering price, location, reviews, and date-specific availability when relevant.
</prompt>
<prompt path="/Users/mingukjang/.aside/u/0/memory/MEMORY.md" description="stable operating defaults derived from semantic memory">
# Memory Briefing

<!-- L1 operating briefing: refreshed by dreaming. -->
- For coding work, apply Ponytail `full` intensity by default; honor `stop ponytail` or `normal mode` for the current session.
</prompt>
</contexts>
