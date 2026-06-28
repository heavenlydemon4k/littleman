# Settings Provider Selector + API Key Flow

## Goal

Replace the raw "API base URL" field in Settings with a provider dropdown so a user only has to:

1. Pick a provider (OpenAI, Kimi / Moonshot, Anthropic, OpenRouter, Ollama, or Custom).
2. Paste an API key.
3. Click Save.

Base URL and default models are auto-configured per provider. The saved API key is shown as a disabled, masked input so the user knows it is stored.

## Background

The current Settings page exposes `api_base`, primary model, and secondary model as editable fields. Users with a Kimi key must know the Moonshot base URL (`https://api.moonshot.ai/v1`) and the correct model prefix (`openai/moonshot-v1-128k`). This is error-prone and makes the key feel like it "doesn't save" because the input clears after Save with no obvious persisted state.

Onboarding already has a provider preset table, but it is hard-coded inside `OnboardingPage.tsx`. Settings should reuse the same presets.

## Design

### 1. Shared provider presets

Create `frontend/src/llm-providers.ts` exporting a single source of truth:

```ts
export interface ProviderPreset {
  key: string;
  label: string;
  prefix: string;
  apiBase: string;   // "" means "use the provider's native endpoint"
  models: string[];  // base model ids; final id is prefix + model
}

export const PROVIDERS: ProviderPreset[] = [
  {
    key: "openai",
    label: "OpenAI",
    prefix: "openai/",
    apiBase: "",
    models: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  },
  {
    key: "kimi",
    label: "Kimi / Moonshot",
    prefix: "openai/",
    apiBase: "https://api.moonshot.ai/v1",
    models: ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
  },
  {
    key: "anthropic",
    label: "Anthropic",
    prefix: "anthropic/",
    apiBase: "",
    models: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  },
  {
    key: "openrouter",
    label: "OpenRouter",
    prefix: "openrouter/",
    apiBase: "https://openrouter.ai/api/v1",
    models: ["anthropic/claude-sonnet-4-6", "openai/gpt-4o"],
  },
  {
    key: "ollama",
    label: "Ollama",
    prefix: "ollama/",
    apiBase: "http://localhost:11434",
    models: ["llama3.1:8b", "qwen2.5:14b", "llama3.3:70b"],
  },
];

export const CUSTOM_KEY = "custom";
```

Update `OnboardingPage.tsx` to import `PROVIDERS` from this module and remove its local `PROVIDERS` constant.

### 2. Settings UI changes

In `frontend/src/pages/SettingsPage.tsx`:

#### Provider selector

- Add a `<select>` labeled "Provider" with options from `PROVIDERS` plus a "Custom" option.
- Determine the active provider on load by matching the current `api_base` and `primary_model` prefix against the preset table:
  - Exact `api_base` match and model prefix match → that provider.
  - No match → "Custom".
- On provider change:
  - Set `form.api_base = provider.apiBase`.
  - Set `form.primary_model = provider.prefix + provider.models[0]`.
  - Set `form.secondary_model = provider.prefix + (provider.models[1] ?? provider.models[0])`.
  - Trigger model list refresh.

#### API key input states

| State | UI |
|-------|----|
| No key stored | Editable password input, placeholder `Paste key…` |
| Key stored, not editing | Disabled password input showing `cfg.api_key_masked`; **Edit** button enables editing |
| Editing | Editable password input, placeholder `Paste new key…`; Save will overwrite |

- The existing trash icon removes the stored key (calls `DELETE /api/settings/runtime/api-key`).
- After a successful Save that included a new key, switch to the "stored, not editing" state.

#### Advanced section

Collapse the following fields behind an "Advanced" disclosure by default:

- API base URL
- Primary model
- Secondary model

This keeps the default view to just Provider + API Key + Mode + Save/Test.

### 3. Backend changes

None. The existing endpoints accept and persist:

- `mode`
- `api_base`
- `api_key`
- `primary_model`
- `secondary_model`

### 4. Save feedback

After a successful `PATCH /api/settings/runtime`:

- Show the existing green "saved" text for 2 seconds.
- Ensure the provider selector reflects the saved state.
- If a key was saved, immediately show the disabled masked input so the user sees persistence.

### 5. Testing

- Existing backend end-to-end tests in `tests/test_settings_runtime.py` continue to cover persistence.
- Manual verification:
  1. Open Settings.
  2. Select "Kimi / Moonshot".
  3. Paste a key and Save.
  4. `GET /api/settings/runtime` returns `api_base: "https://api.moonshot.ai/v1"`, `api_key_set: true`.
  5. Refresh the page; the provider is still Kimi and the key input is disabled/masked.
  6. Click Edit, paste a new key, Save; the new key is persisted.

## Out of Scope

- Storing a `provider` field in the backend runtime config. The provider is derived from `api_base` + model prefix on the frontend only.
- Auto-detecting the provider from the key format.
- Changing the onboarding flow beyond sharing the preset table.
