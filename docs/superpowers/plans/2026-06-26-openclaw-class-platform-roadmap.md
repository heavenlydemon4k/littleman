# littleman → OpenClaw-Class Platform Roadmap

> **Status:** planning document — no code changes yet.  
> **Purpose:** record the architectural findings from studying OpenClaw and the littleman repo, and present a sequenced set of implementation plans for review before execution.

---

## 1. What we are trying to achieve

`littleman` is already a credible autonomous-agent engine. Compared to OpenClaw, its differentiators are:

- **Dynamic, self-authored heartbeats** (OpenClaw uses a static `HEARTBEAT.md`).
- **Mental Construct** — structured, agent-owned markdown cognition.
- **Meta/Macro/Task layering** with a deterministic risk governor for side-effectful domains.
- **Serial execution + cross-process lock** for a single consistent world view.

The remaining gap is **breadth and cleanliness as a platform**: OpenClaw is a personal-assistant *ecosystem* (channels, plugins, skill marketplace, sandboxing), while littleman is a single-domain engine that happens to have a clean application boundary. To close that gap without losing depth, we need to:

1. Make the platform surface genuinely domain-agnostic.
2. Adopt a clean skill/docs/loader model that does not fight itself.
3. Prepare the boundary for external interoperability (MCP/ACP).

---

## 2. Architectural findings

### 2.1 The skill/docs/loader collision is the most urgent seam

`littleman/skills/openclaw_loader.py` currently scans `workspace/skills/*.md` and registers **every markdown file as a skill**. If the file name matches a built-in skill, it overwrites the working implementation with a documentation-only stub. We just patched `registry.py` to skip already-registered names, but that is a workaround, not a design.

The real model should be:

- `workspace/skills/*.md` = **documentation** read via `read_skill_doc(name)`.
- `workspace/openclaw/skills/*.md` = **executable skill manifests** with optional `littleman.skills.openclaw.<name>` implementations.
- Built-in Python skills are always authoritative.

Additionally, `read_skill_doc(name)` should resolve by **registered skill name**, not by doc filename. A doc file can cover a family of skills (e.g. `kb.md` covers `write_to_kb`, `read_from_kb`, `search_kb`) via a YAML `skills:` frontmatter list.

### 2.2 Default platform surfaces still assume Polymarket

The platform default (`littleman.platform`) is supposed to be a generic autonomous assistant, but several agent-facing surfaces still read like a trading bot:

- `workspace/skills/probability.md` frames `estimate_probability` as a bet-decision tool.
- `CHAT_SUGGESTIONS_SYSTEM` calls the agent a "prediction-market trading agent".
- `CALENDAR_MAINTAIN_SYSTEM` tells the agent to "keep open positions and watched market closes current".
- `SELF_MAINTAIN_SYSTEM` tells it to "cite the market".

These do not break the platform default immediately, but they mislead the model about its identity. They belong in the Polymarket application, not the platform defaults.

### 2.3 The session pipeline is still trading-shaped

`agent/session.py`, `meta/synthesizer.py`, `meta/directive.py`, `macro/strategy.py`, and `meta/planner.py` hard-code a trading-shaped situation report, directive schema, strategy examples, and heartbeat cascade rules. When `active_application = "littleman.platform"`, the pipeline still asks the model about wallet balance, open positions, and market closes.

This is the largest remaining architectural debt. Fixing it requires introducing **application-specific prompt extensions** so the platform core can render a generic situation/directive/plan for the default app and a trading-specific one for Polymarket.

### 2.4 Interoperability is not yet on the map

OpenClaw's ecosystem power comes from standards: `SKILL.md` manifests, plugin manifests, permission manifests, and bridges like ACP/MCP. littleman has a well-defined skill registry, but it is not exposed to other agents. Adding an MCP server or ACP bridge would let Claude Code, Codex, or OpenClaw drive littleman's skills.

---

## 3. Proposed sequence

### Phase 1 — Immediate: clean the skill/docs/loader seam

**Plan:** [`2026-06-26-skill-docs-and-registry.md`](2026-06-26-skill-docs-and-registry.md)

Why first:
- It fixes a real bug we just band-aided.
- It makes First Light more reliable (`read_skill_doc("write_to_kb")` will work).
- It is self-contained and low risk.

Outcome:
- `workspace/skills/*.md` are docs only.
- `read_skill_doc` resolves by registered name using frontmatter `skills:`.
- OpenClaw executable skills load from `workspace/openclaw/skills/`.
- Built-in skills cannot be shadowed.

### Phase 2 — Immediate: remove trading language from default surfaces

**Plan:** [`2026-06-26-default-platform-surfaces-cleanup.md`](2026-06-26-default-platform-surfaces-cleanup.md)

Why second:
- Independent of Phase 1.
- Low risk; mostly text changes plus regression tests.
- Immediately improves the platform default's identity.

Outcome:
- `probability.md`, `EXPOSURE.template.md`, chat suggestions, and maintenance prompts are application-neutral.
- Regression tests prevent the drift from recurring.

### Phase 3 — Medium: make the session pipeline application-aware

Not yet planned in detail. The shape would be:

1. Introduce an `ApplicationContext` abstraction with methods like:
   - `situation_payload(state, heartbeat_context)`
   - `directive_schema()`
   - `strategy_examples()`
   - `heartbeat_plan_rules()`
   - `session_summary(exec_result)`
2. Provide a generic `PlatformApplicationContext` and a trading `PolymarketApplicationContext`.
3. Refactor `prompts.py` to accept app-specific schema/examples/rules as placeholders.
4. Update `synthesizer.py`, `directive.py`, `strategy.py`, `planner.py`, and `agent/session.py` to call the active context.

This is the prerequisite for making the platform default actually behave like a general assistant during autonomous wakes.

### Phase 4 — Longer term: interoperability

- **MCP server** exposing the skill registry as tools.
- **ACP bridge** so other agents can delegate to a littleman instance.
- **OpenClaw permission manifests** if/when littleman loads third-party skills.

---

## 4. Open questions to resolve before Phase 3

1. Should the platform default even run the full meta/macro/task pipeline for ordinary chat, or should there be a lighter "chat mode" that skips situation/directive/strategy when the user just asked a question?
2. Should `ApplicationContext` be a Protocol method on `Application`, or a separate object returned by `Application.get_context()`?
3. How should non-financial applications express risk/exposure? Should `EXPOSURE.md` be optional per application?
4. Does the `estimate_probability` skill stay in the platform default, or move to a "decision support" skill pack?

---

## 5. Recommended next turn

Pick **Phase 1** or **Phase 2** and execute via `superpowers:subagent-driven-development`. They are independent, so either is a clean next step. Phase 1 is higher leverage because it fixes a real architectural bug; Phase 2 is faster and improves first impressions.
