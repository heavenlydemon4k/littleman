# Settings Provider Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw API-base URL field in Settings with a provider dropdown so users only pick a provider, paste an API key, and save; base URL and default models are auto-configured and the saved key is shown as a disabled masked input.

**Architecture:** Extract the provider preset table from onboarding into a shared module, then consume it from both onboarding and settings. The settings page derives the active provider from the saved `api_base` + model prefix, auto-fills dependent fields on change, and manages the API key input as a togglable editable/disabled state.

**Tech Stack:** React + TypeScript + Vite frontend; existing FastAPI backend endpoints unchanged.

## Global Constraints

- No backend schema/API changes; reuse `PATCH /api/settings/runtime` and `DELETE /api/settings/runtime/api-key`.
- Keep provider presets identical between onboarding and settings.
- Preserve existing model-list fetch behavior (`/api/settings/models`).
- Use existing Tailwind classes and input styling.

---

### Task 1: Extract shared provider presets

**Files:**
- Create: `frontend/src/llm-providers.ts`
- Modify: `frontend/src/pages/OnboardingPage.tsx`

**Interfaces:**
- Produces: `ProviderPreset` interface and `PROVIDERS` array, exported from `frontend/src/llm-providers.ts`.
- Consumes: `OnboardingPage.tsx` currently defines an equivalent local `PROVIDERS` constant.

- [ ] **Step 1: Create the shared module**

Create `frontend/src/llm-providers.ts`:

```ts
export interface ProviderPreset {
  key: string;
  label: string;
  prefix: string;
  apiBase: string;
  models: string[];
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

export function fullModel(provider: ProviderPreset, index: number): string {
  const base = provider.models[index] ?? provider.models[0];
  return `${provider.prefix}${base}`;
}
```

- [ ] **Step 2: Refactor OnboardingPage to import presets**

In `frontend/src/pages/OnboardingPage.tsx`:

1. Remove the local `PROVIDERS` constant and its TypeScript type.
2. Add:

```ts
import { CUSTOM_KEY, PROVIDERS, fullModel } from "../llm-providers";
```

3. Replace `provider.prefix + model` with `provider.prefix + model` where `model` is already the base id; keep as is. Replace `provider.prefix + (provider.models[1] ?? model)` with `fullModel(provider, 1)`.
4. Replace the type `Record<string, { label: string; apiBase: string; needsKey: boolean; prefix: string; models: string[] }>` usage with `ProviderPreset` from the module.

Expected result: onboarding still builds and behaves identically.

- [ ] **Step 3: Verify build**

Run:

```bash
cd frontend
npm run build
```

Expected: build succeeds with no new TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/llm-providers.ts frontend/src/pages/OnboardingPage.tsx
git commit -m "refactor: share provider presets between onboarding and settings"
```

---

### Task 2: Add provider selector and API key states to Settings

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

**Interfaces:**
- Consumes: `PROVIDERS`, `CUSTOM_KEY`, `ProviderPreset`, `fullModel` from `frontend/src/llm-providers.ts`.
- Consumes: existing `RuntimeCfg` and `/api/settings/runtime` GET/PATCH/DELETE endpoints.
- Produces: a `provider` form field plus derived `api_base`, `primary_model`, and `secondary_model` updates.

- [ ] **Step 1: Add provider imports and helper**

At the top of `frontend/src/pages/SettingsPage.tsx`, add:

```ts
import { CUSTOM_KEY, PROVIDERS, ProviderPreset, fullModel } from "../llm-providers";
```

Add a helper inside the file:

```ts
function detectProvider(apiBase: string, primaryModel: string): string {
  return (
    PROVIDERS.find(
      (p) =>
        p.apiBase.toLowerCase() === (apiBase || "").toLowerCase() &&
        primaryModel.startsWith(p.prefix)
    )?.key ?? CUSTOM_KEY
  );
}
```

- [ ] **Step 2: Add provider state and synchronization**

Inside `RuntimeSection`, after the existing state declarations, add:

```ts
const [provider, setProvider] = useState<string>(CUSTOM_KEY);
const [editingKey, setEditingKey] = useState(false);
const [advanced, setAdvanced] = useState(false);
```

Update the `load()` callback so that after `setCfg(c)` and `setForm(...)` it also sets the provider:

```ts
setProvider(detectProvider(c.api_base, c.primary_model));
```

- [ ] **Step 3: Add provider change handler**

Inside `RuntimeSection`, add:

```ts
const applyProvider = (key: string) => {
  setProvider(key);
  if (key === CUSTOM_KEY) return;
  const p = PROVIDERS.find((x) => x.key === key);
  if (!p) return;
  setForm((f) => ({
    ...f,
    api_base: p.apiBase,
    primary_model: fullModel(p, 0),
    secondary_model: fullModel(p, 1),
  }));
  loadModels(p.apiBase, form.api_key, fullModel(p, 0));
};
```

- [ ] **Step 4: Render the provider field**

Add a new `Field` before the existing Mode field:

```tsx
<Field label="Provider">
  <select
    value={provider}
    onChange={(e) => applyProvider(e.target.value)}
    className={inputCls}
  >
    {PROVIDERS.map((p) => (
      <option key={p.key} value={p.key}>
        {p.label}
      </option>
    ))}
    <option value={CUSTOM_KEY}>Custom</option>
  </select>
</Field>
```

- [ ] **Step 5: Replace the API key field with editable/disabled states**

Replace the existing API key `Field` block with:

```tsx
<Field
  label={`API key ${cfg.api_key_set && !editingKey ? "(saved)" : ""}`}
>
  <div className="flex items-center gap-2">
    <input
      type="password"
      value={
        cfg.api_key_set && !editingKey
          ? cfg.api_key_masked
          : (form.api_key ?? "")
      }
      disabled={cfg.api_key_set && !editingKey}
      onChange={(e) => setForm({ ...form, api_key: e.target.value })}
      placeholder={
        cfg.api_key_set && !editingKey
          ? "Key saved"
          : "Paste key (sk-… / Moonshot key)"
      }
      className={inputCls}
    />
    {cfg.api_key_set && (
      <>
        {!editingKey ? (
          <button
            onClick={() => {
              setEditingKey(true);
              setForm((f) => ({ ...f, api_key: "" }));
            }}
            className="flex-shrink-0 rounded-lg border border-border px-3 py-2 text-xs text-muted hover:text-white transition-colors"
          >
            Edit
          </button>
        ) : null}
        <button
          onClick={removeKey}
          title="Remove the stored key"
          className="flex-shrink-0 rounded-lg border border-border p-2 text-muted hover:border-red-500/50 hover:text-red-400 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </>
    )}
  </div>
</Field>
```

- [ ] **Step 6: Wrap advanced fields in a collapsible section**

Wrap the existing `API base URL`, `Models`, primary model, and secondary model fields in a disclosure. Add this after the API key field:

```tsx
<div>
  <button
    onClick={() => setAdvanced((a) => !a)}
    className="text-xs text-muted hover:text-white transition-colors"
  >
    {advanced ? "Hide advanced" : "Show advanced"}
  </button>
  {advanced && (
    <div className="mt-3 space-y-3">
      {/* existing base URL, models refresh row, primary/secondary model fields */}
    </div>
  )}
</div>
```

Move the existing base URL input, the model list refresh row, and the primary/secondary `ModelSelect` fields inside the conditional `advanced &&` block. Leave the `Mode` field and provider field always visible.

- [ ] **Step 7: Update save and remove handlers**

In the existing `save()` function, after `setForm((f) => ({ ...f, api_key: "" }))`, add:

```ts
setEditingKey(false);
```

In the existing `removeKey()` function, after `setForm((f) => ({ ...f, api_key: "" }))`, add:

```ts
setEditingKey(false);
```

- [ ] **Step 8: Build and smoke-test**

Run:

```bash
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat(settings): provider dropdown, auto-filled base/models, masked saved key"
```

---

### Task 3: Manual end-to-end verification

**Files:**
- None (manual test against the running backend).

- [ ] **Step 1: Confirm the backend tests still pass**

Run:

```bash
cd /c/Users/judas/Documents/littleman
.venv/Scripts/python -m pytest tests/test_settings_runtime.py -v
```

Expected: 3 tests pass.

- [ ] **Step 2: Restart the frontend dev server if needed**

If the UI is being served by `npm run dev`, restart it so the new code is loaded.

- [ ] **Step 3: Verify Kimi flow in the browser**

1. Open Settings.
2. Select provider "Kimi / Moonshot".
3. Paste a Moonshot API key.
4. Click Save.
5. Expected: the key input becomes disabled and shows a masked key like `sk-12X…9abc`; the page shows "saved".
6. Expected: `GET /api/settings/runtime` returns `api_base: "https://api.moonshot.ai/v1"` and `api_key_set: true`.
7. Refresh the page; expected: provider is still "Kimi / Moonshot", key still masked.
8. Click Edit, paste a different key, Save; expected: new key persisted.

- [ ] **Step 4: Verify OpenAI flow**

1. Select provider "OpenAI".
2. Paste an OpenAI key.
3. Save.
4. Expected: `api_base: ""` and `primary_model: "openai/gpt-4o"` (or whichever model is first).

- [ ] **Step 5: Verify Custom flow**

1. Select provider "Custom".
2. Manually edit the advanced base URL and models.
3. Save.
4. Expected: values persist after refresh.

- [ ] **Step 6: Verify onboarding still works**

1. Run a fresh onboarding (`python start.py --fresh` if testing locally).
2. Select Kimi, paste key, complete onboarding.
3. Expected: onboarding redirects and `/api/settings/runtime` shows the correct Kimi base and model.

- [ ] **Step 7: Push changes**

```bash
git push origin main
```

Expected: push completes without conflicts.

---

## Self-Review

**Spec coverage:**
- Shared provider presets — Task 1.
- Provider dropdown in Settings — Task 2 Step 4.
- Auto-fill base URL and models on provider change — Task 2 Step 3.
- Masked/disabled API key input with Edit button — Task 2 Step 5.
- Advanced section hiding base/model fields — Task 2 Step 6.
- Save feedback — Task 2 Step 7 + existing "saved" toast.
- No backend changes — enforced by global constraints.
- Manual verification — Task 3.

**Placeholder scan:** None. All steps include concrete code or commands.

**Type consistency:** `ProviderPreset`, `PROVIDERS`, `CUSTOM_KEY`, and `fullModel` are imported identically in both onboarding and settings. The `provider` state is always a string key matching `ProviderPreset.key` or `CUSTOM_KEY`.
