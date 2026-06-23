# Design — Onboarding & UI (working vision)

Status: **vision capture**, evolving. This records design intent agreed in guided design
sessions, ahead of implementation. Not all of this is built yet.

Littleman is a **general agent platform** (see [META.md](../META.md)); nothing here is
Polymarket-specific. The user's stated *purpose* during onboarding is what gives the agent its
domain.

---

## 1. First-run flow (new user, nothing configured)

```
Welcome (shared, domain-agnostic)
  1. "What should we call you?"        → display name
  2. "What should we do?"              → purpose / prime directive (free text)
  3. LLM provider → model               → provider/model selection
        │
        ├── GUIDED  → short questionnaire (details & constraints) → compiles SOUL.md + limits
        └── CUSTOM  → no questionnaire; configure by talking to the agent in chat
        │
        ▼
  Land in a CHAT (the default empty chat), left sidebar present
```

The shared welcome collects only what's universal. The agent's *mission* comes from the
purpose field; domain-specific config (wallet, budget, risk) appears later only when the purpose
implies it.

### Guided questionnaire (details & constraints)

Domain-agnostic by default; compiled by an LLM into `SOUL.md` + initial limits:
- Objective & success criteria
- Operating constraints / red lines (in the user's own words)
- Autonomy & check-in cadence (how independent; when to pause and ask)
- Any domain config the purpose implies (e.g. budget/wallet/risk *only* if it involves money)

### Custom path

No questionnaire. The user **configures the agent by prompting it in the chat** — but it is not
a passive blank box:

- **First Light still runs** (a *custom-onboarding-aware* variant): even with no user info yet,
  the agent wakes, reads what little it has, understands it is in custom onboarding, and **greets
  the user and guides the conversation** toward configuring itself. The guidance should respect
  the user's intelligence — helpful and steering, not hand-holdy.
- The agent has **every skill available**, including a **self-configuration skill** so it can
  write/update its own `SOUL.md` + limits from the conversation. The custom path is the agent
  genuinely self-configuring through dialogue.
- Power users can still edit `SOUL.md`/config directly in the Workspace tab.

### Skills must be OpenClaw-compatible (requirement)

Skills follow the **OpenClaw / AgentSkills format** (a `SKILL.md` with `name` + `description`
frontmatter) so skills from **OpenClaw's marketplace can be imported and shared**. The existing
`workspace/skills/*.md` docs and `read_skill_doc` are the seed of this; the gap is full
frontmatter + a loader that registers filesystem skills, not just Python-defined ones.

---

## 2. First Light as a *waking moment* in chat (the core idea)

First Light is **the agent's first-ever activation** — and it is **compulsory**. It is **not** a
silent background process; it happens **visibly in the chat**, exactly once, triggered the moment
the user completes/selects their onboarding:

1. Onboarding completes → a **compulsory one-time run of the model** fires (the first activation).
   It is mandatory, not optional or skippable — the agent must gather its bearings once before
   normal operation begins.
2. The agent **wakes**, **reads its relevant files** (`SOUL.md`, the onboarding answers, the
   mental construct), and **gathers its bearings**.
3. It **responds to the user in the chat** — introducing itself and its understanding of the
   mission, informed by the answers the user gave during onboarding.
4. It then **goes dormant** ("turns off") until the next prompt or scheduled wake.

After this one compulsory First Light, the agent is purely per-wake (each user message or
heartbeat wakes it). So "turn the agent on for the first time" = this mandatory First Light run;
thereafter waking is ordinary and automatic per message.

This is the **heartbeat / wake model surfaced as conversation**: dormant by default → user (or
a heartbeat) wakes it → it reads, acts, responds → it sleeps. The same mechanic that drives
autonomous operation is what the user sees in chat. A wake costs tokens; sleep costs nothing.

### Power model: per-wake only (decided)

There is **no global power switch**. The agent is purely event-driven:
- Each **user message** wakes it for that turn, then it sleeps.
- Each **heartbeat** wakes it for that session (gated by the existing autonomy toggle), then it
  sleeps.
- **First Light** is the one wake with no preceding user message, so the empty first chat shows
  an explicit **"Wake the agent"** action to trigger it. After that, normal per-message waking.

So "turn on / turn off" is the per-wake lifecycle, not a persistent state. Nothing new to gate
globally beyond the autonomy toggle that already exists for heartbeats.

### Implications for the UI

- The chat needs an explicit **agent power / wake control** ("turn on" for the first bearings;
  thereafter, sending a message wakes it for that turn).
- Dormant vs awake is a **visible state**, not hidden.
- The Main session (the agent's autonomous activity stream) and this user chat share the same
  wake mechanic — autonomous wakes write to Main; user prompts wake it in the user chat.

---

## 3. Layout constants & chat surface

- **Onboarding is the first pop-out screen and is compulsory.** It blocks access to the main app
  (chat / profile / settings home) until completed. It is *separate* from the chat itself — it
  gates the very first chat session.
- The **left sidebar is always present** (Agent, Main · agent, chats, Workspace, Settings).
- New users **start on the default empty chat** after onboarding.

### Empty-session chat (modern LLM-platform pattern)

- An **empty session opens with the input box centered** in the chat area, with the **littleman
  brand mark above it** (simple). Like ChatGPT/Claude's empty state.
- On the **first prompt**, the input **animates down to the normal bottom position** and the
  conversation begins above it.
- The **chat input field is designed to feel modern and familiar** — rounded composer, the
  existing thinking/skills toggles, send/stop — matching the aesthetic of mainstream chat apps.

### First Light is a button, not a text field

- For the compulsory First Light, the centered "input" is replaced by an **activate button**
  (the user presses it to wake the agent for the first time — there's no message to type yet).
- On activation, **live status text streams** showing what the agent is doing (e.g. "waking…",
  "reading SOUL.md…", "gathering bearings…", "forming first understanding…"), then the agent's
  greeting appears and the session becomes a normal chat (input drops to the bottom).

---

## 4. Decided vs open

**Decided:**
- First-run flow: shared welcome (name → purpose → provider/model) → Guided | Custom.
- Land on the default empty chat; sidebar always present.
- First Light = visible waking moment in chat; runs for **both** paths (custom variant is
  onboarding-aware and guides the user).
- Power model: per-wake only (no global switch); empty chat shows "Wake the agent".
- Custom = self-configuration through guided dialogue; agent has a self-config skill + all skills.
- Skills are OpenClaw/AgentSkills-compatible (marketplace import).

**Open / to-decide:**
- Exact UI for "Wake the agent" (button in composer vs banner in the first chat).
- First Light as one assistant turn vs a short visible sequence (reading… → here's my read).
- Guided questionnaire rendering (stepper vs single form).
- Self-config skill shape (`update_self` writing `SOUL.md` + limits) and its safety gating.
- Filesystem skill loader for OpenClaw `SKILL.md` import (beyond Python-defined skills).
- What the agent dashboard becomes once chat is home (side tab vs command-center).

## 5. Suggested MVP build order

1. First-run detection + shared welcome (name → purpose → provider/model).
2. Onboarding writes a seed `SOUL.md` (guided: from questionnaire; custom: minimal stub) and
   lands on the empty chat.
3. "Wake the agent" → First Light runs visibly in chat (reads files, greets per the purpose).
4. Custom: self-config skill so the agent persists config from the conversation.
5. OpenClaw `SKILL.md` filesystem loader + marketplace-format compatibility.
