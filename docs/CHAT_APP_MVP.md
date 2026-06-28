# Chat App MVP — System Configuration and External App Connectors

This document defines the next product shape for littleman.

The immediate goal is not to build every external integration. The goal is to
make the core chat app reliable and extensible so the LLM can help configure
itself, explain its current system, and later connect to applications such as
email, Polymarket, calendars, issue trackers, or any API-backed service through
a common connector contract.

## Product Target

Littleman should first be a useful local chat application with:

- a working LLM runtime that can be configured from chat and settings;
- an inspectable system prompt / identity / memory surface;
- safe tools that let the assistant read and update its own local workspace;
- clear operator control over autonomy, scheduled work, and external actions;
- a connector layer where new external apps can be added without changing the
  platform loop.

Polymarket remains a reference app. It should not define the product shape.

## Current Starting Point

Already built:

- chat sessions, streaming, tool use, and a Main session;
- onboarding that writes `workspace/SOUL.md`;
- First Light, mental construct files, and construct maintenance;
- runtime model settings in `workspace/state/runtime.json`;
- skill registry with availability gating and `chat_safe`;
- default platform app and optional Polymarket app;
- heartbeat scheduler and autonomous toggle;
- workspace editor and agent dashboard.

Current gaps:

- the chat app cannot yet configure all important system files conversationally;
- app integration is split between `Application` objects and ad hoc settings;
- secrets and connector credentials do not have a uniform model;
- external side effects do not have a first-class approval policy;
- the dashboard still has trading-shaped data in platform views;
- there is no connector creation flow where the LLM can inspect an API spec and
  propose a compatible skill pack.

## MVP Scope

### 1. Chat-First System Configuration

The assistant should be able to configure its own local system through chat,
with operator confirmation for sensitive changes.

Required capabilities:

- read current system identity:
  - `SOUL.md`
  - `AGENT.md`
  - construct docs
  - runtime model config
  - active application
  - registered skills
- propose edits to `SOUL.md` and selected construct docs;
- apply approved edits;
- update runtime settings:
  - mode: real/fake
  - primary model
  - secondary model
  - API base
  - autonomous on/off
- explain what is configured and what is missing.

Implementation shape:

- keep `SettingsPage` for direct manual edits;
- add chat-safe configuration skills for read/propose/apply operations;
- do not let the LLM silently overwrite identity or autonomy settings;
- require explicit operator approval for:
  - changing autonomous mode;
  - replacing `SOUL.md`;
  - storing or deleting credentials;
  - enabling an external connector.

### 2. Connector Registry

Add a platform-level connector model separate from the current application
model.

An application is the domain personality and runtime behavior.

A connector is an external capability provider.

Examples:

- Gmail connector;
- generic IMAP/SMTP connector;
- Google Calendar connector;
- Polymarket connector;
- GitHub connector;
- Notion connector;
- generic HTTP OpenAPI connector.

Minimal connector fields:

```json
{
  "id": "gmail",
  "name": "Gmail",
  "kind": "email",
  "status": "disabled",
  "auth_type": "oauth",
  "scopes": ["read_email", "send_email"],
  "capabilities": ["search_messages", "draft_email", "send_email"],
  "approval_policy": {
    "read": "allow",
    "write": "confirm",
    "external_send": "confirm"
  }
}
```

Connector state should live in SQLite. Secrets should not be stored in ordinary
workspace markdown. For MVP, credentials can stay in environment/runtime
overrides if needed, but the schema should be designed so a keyring or encrypted
store can replace it later.

### 3. Connector Skills

Each enabled connector registers skills into the existing skill registry.

Skill policy should be more precise than `chat_safe`.

Add skill effect classes:

- `read_local`
- `write_local`
- `read_external`
- `write_external`
- `send_external`
- `spend_money`
- `destructive`

Then derive chat exposure and approval behavior from these effect classes.

Examples:

- `gmail_search_messages`: `read_external`
- `gmail_create_draft`: `write_external`
- `gmail_send_email`: `send_external`
- `polymarket_scan`: `read_external`
- `polymarket_place_order`: `spend_money`
- `workspace_write_file`: `write_local`

### 4. Approval Flow

The chat loop needs a standard "pending action" state.

The model should be able to say: "I want to call this skill with these
arguments." If the skill requires approval, the backend stores a pending action
and the frontend shows Approve / Reject.

MVP behavior:

- read-only skills execute immediately;
- local writes require confirmation unless the file is explicitly safe;
- external sends, money movement, credential changes, deletes, and connector
  enabling always require confirmation;
- approved actions are logged with who approved them and when.

### 5. Auto-Configure External APIs

"Auto configure itself to be compatible" should mean the assistant can help set
up a connector from available structured information, not that it invents unsafe
runtime code.

MVP support:

- user provides:
  - service name;
  - API base URL;
  - OpenAPI spec URL/file, or manual endpoint description;
  - auth type;
  - desired capabilities;
- LLM analyzes the spec and proposes:
  - connector manifest;
  - required credentials/scopes;
  - skill definitions;
  - safety policies;
  - test calls;
- operator approves;
- backend saves the connector manifest;
- generated connector code is not executed automatically in MVP.

Near-term practical version:

- support a generic HTTP connector with configured endpoints;
- endpoint calls are data-driven from a manifest;
- no arbitrary Python execution from the LLM;
- require approval for non-GET requests.

### 6. Dashboard Changes

The dashboard should become platform-first.

Keep:

- runtime status;
- active model;
- autonomous toggle;
- heartbeats;
- Main activity feed;
- construct docs;
- skills list.

Change:

- move wallet/position/exposure cards into the Polymarket connector/app panel;
- add a Connectors page:
  - installed connectors;
  - enabled/disabled state;
  - missing credentials;
  - available skills;
  - approval policy;
  - last successful check;
  - last error.

## Data Model Additions

Proposed tables:

```python
class Connector(Base):
    id: str
    name: str
    kind: str
    status: str
    auth_type: str
    config: JSON
    capabilities: JSON
    approval_policy: JSON
    created_at: datetime
    updated_at: datetime

class ConnectorCredential(Base):
    id: str
    connector_id: str
    key_name: str
    secret_ref: str
    status: str
    created_at: datetime
    updated_at: datetime

class PendingAction(Base):
    id: str
    skill_name: str
    args: JSON
    effect: str
    reason: str
    status: str
    requested_by_session_id: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    result: JSON | None
    created_at: datetime
```

`ConnectorCredential.secret_ref` should point to whatever secret backend exists.
For MVP, it can reference environment/runtime keys, but the table should avoid
storing raw secrets where possible.

## Implementation Order

1. Fix current platform health issues.
   - route-level tests for `/api/agent/status`;
   - remove remaining undefined variables and platform-mode dashboard errors.

2. Add configuration skills.
   - read runtime config;
   - propose `SOUL.md` edit;
   - apply approved `SOUL.md` edit;
   - set runtime model settings with approval.

3. Add skill effect metadata.
   - extend `Skill`;
   - mark existing skills;
   - keep backwards compatibility with `chat_safe`;
   - expose effect metadata in `/api/agent/skills`.

4. Add pending action approval.
   - DB table;
   - API routes;
   - chat loop integration;
   - frontend approval card.

5. Add connector registry.
   - DB tables;
   - API routes;
   - Connectors page;
   - default disabled connector entries for Polymarket and generic HTTP.

6. Add generic HTTP connector MVP.
   - manifest-driven endpoint calls;
   - GET allowed if enabled;
   - POST/PUT/PATCH/DELETE require approval;
   - response shaping and error display.

7. Move Polymarket into connector/app UI.
   - keep current application behavior;
   - expose its connector status through the new connectors page;
   - keep money movement gated.

8. Add email connector after the generic connector works.
   - start with draft-only email;
   - sending requires explicit approval;
   - read/search can be enabled separately from send.

## What Not To Build Yet

- arbitrary LLM-generated Python connector code execution;
- full OAuth for every provider;
- multi-user accounts;
- multi-agent coordination;
- autonomous external sends;
- autonomous money movement;
- a generic abstraction for every possible app before a second real connector exists.

## Definition of Done for MVP

The MVP is done when:

- a user can open Littleman, configure the model, and chat normally;
- the assistant can explain and propose changes to its own identity/config;
- approved config changes apply through safe backend APIs;
- external connector state is visible and understandable;
- at least one non-Polymarket connector works through the connector registry;
- read-only connector calls work from chat;
- write/send/spend actions pause for approval;
- the dashboard has no platform-mode trading assumptions in its main status view.
