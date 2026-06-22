import { useEffect, useState } from "react";
import { Plus, Trash2, Star, Cpu } from "lucide-react";
import clsx from "clsx";
import type { LLMConfig } from "../types";

const PROVIDERS = ["anthropic", "openai", "ollama", "litellm"];

const PROVIDER_MODELS: Record<string, string[]> = {
  anthropic: [
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4-8",
    "anthropic/claude-haiku-4-5-20251001",
  ],
  openai: ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/gpt-4-turbo"],
  ollama: ["ollama/llama3.1:8b", "ollama/llama3.1:70b", "ollama/qwen2.5:14b", "ollama/qwen2.5:32b"],
  litellm: [],
};

const EMPTY_FORM = {
  name: "",
  provider: "anthropic",
  model: "",
  api_key: "",
  base_url: "",
  is_primary: false,
  is_secondary: false,
  extra_params: "{}",
};

export function SettingsPage() {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState("");

  const load = () =>
    fetch("/api/settings/llm").then((r) => r.json()).then(setConfigs).catch(console.error);

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setForm({ ...EMPTY_FORM });
    setEditId(null);
    setError("");
    setShowForm(true);
  };

  const openEdit = (c: LLMConfig) => {
    setForm({
      name: c.name,
      provider: c.provider,
      model: c.model,
      api_key: "",
      base_url: c.base_url ?? "",
      is_primary: c.is_primary,
      is_secondary: c.is_secondary,
      extra_params: JSON.stringify(c.extra_params, null, 2),
    });
    setEditId(c.id);
    setError("");
    setShowForm(true);
  };

  const submit = async () => {
    setError("");
    let extra: Record<string, unknown> = {};
    try {
      extra = JSON.parse(form.extra_params || "{}");
    } catch {
      setError("Extra params must be valid JSON");
      return;
    }

    const body = {
      name: form.name,
      provider: form.provider,
      model: form.model,
      api_key: form.api_key || null,
      base_url: form.base_url || null,
      is_primary: form.is_primary,
      is_secondary: form.is_secondary,
      extra_params: extra,
    };

    const url = editId ? `/api/settings/llm/${editId}` : "/api/settings/llm";
    const method = editId ? "PATCH" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const data = await res.json();
      setError(data.detail ?? "Request failed");
      return;
    }

    await load();
    setShowForm(false);
  };

  const del = async (id: string) => {
    await fetch(`/api/settings/llm/${id}`, { method: "DELETE" });
    await load();
  };

  const setPrimary = async (id: string) => {
    await fetch(`/api/settings/llm/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_primary: true }),
    });
    await load();
  };

  const suggestedModels = PROVIDER_MODELS[form.provider] ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 font-mono text-lg font-semibold text-white">Settings</h1>
        <p className="mb-6 text-sm text-muted">Agent runtime + chat model configuration</p>

        <RuntimeSection />

        <h2 className="mb-1 mt-8 font-mono text-sm font-semibold text-white">Chat models</h2>
        <p className="mb-4 text-xs text-muted">
          Models selectable for the interactive chat. The agent's own model is set in Agent
          runtime above.
        </p>

        {/* Config list */}
        <div className="mb-4 space-y-2">
          {configs.map((c) => (
            <div
              key={c.id}
              className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3"
            >
              <Cpu size={16} className="mt-0.5 flex-shrink-0 text-blue-400" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-medium text-white">{c.name}</span>
                  {c.is_primary && (
                    <span className="rounded bg-blue-500/20 px-1.5 py-0.5 font-mono text-xs text-blue-400">
                      primary
                    </span>
                  )}
                  {c.is_secondary && (
                    <span className="rounded bg-surface-4 px-1.5 py-0.5 font-mono text-xs text-muted">
                      secondary
                    </span>
                  )}
                </div>
                <p className="mt-0.5 font-mono text-xs text-muted">{c.model}</p>
                {c.base_url && (
                  <p className="mt-0.5 text-xs text-muted">{c.base_url}</p>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                {!c.is_primary && (
                  <button
                    onClick={() => setPrimary(c.id)}
                    title="Set as primary"
                    className="rounded p-1.5 text-muted hover:text-amber-400 transition-colors"
                  >
                    <Star size={14} />
                  </button>
                )}
                <button
                  onClick={() => openEdit(c)}
                  className="rounded p-1.5 text-xs text-muted hover:text-white transition-colors"
                >
                  edit
                </button>
                <button
                  onClick={() => del(c.id)}
                  className="rounded p-1.5 text-muted hover:text-red-400 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}

          {configs.length === 0 && (
            <div className="rounded-xl border border-dashed border-border py-8 text-center text-sm text-muted">
              No models configured yet
            </div>
          )}
        </div>

        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted hover:border-blue-500 hover:text-white transition-colors"
        >
          <Plus size={14} />
          Add model
        </button>

        {/* Form */}
        {showForm && (
          <div className="mt-6 rounded-xl border border-border bg-surface-2 p-5">
            <h2 className="mb-4 font-mono text-sm font-semibold text-white">
              {editId ? "Edit model" : "Add model"}
            </h2>

            <div className="space-y-4">
              <Field label="Name">
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Claude Sonnet"
                  className={inputCls}
                />
              </Field>

              <Field label="Provider">
                <select
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value, model: "" })}
                  className={inputCls}
                >
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </Field>

              <Field label="Model string">
                <input
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  placeholder="e.g. anthropic/claude-sonnet-4-6"
                  className={inputCls}
                />
                {suggestedModels.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {suggestedModels.map((m) => (
                      <button
                        key={m}
                        onClick={() => setForm({ ...form, model: m })}
                        className="rounded bg-surface-3 px-2 py-0.5 font-mono text-xs text-muted hover:text-white transition-colors"
                      >
                        {m.split("/")[1]}
                      </button>
                    ))}
                  </div>
                )}
              </Field>

              <Field label="API key">
                <input
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  placeholder={editId ? "Leave blank to keep existing" : "sk-..."}
                  className={inputCls}
                />
              </Field>

              {(form.provider === "ollama" || form.provider === "litellm") && (
                <Field label="Base URL">
                  <input
                    value={form.base_url}
                    onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                    placeholder="http://localhost:11434"
                    className={inputCls}
                  />
                </Field>
              )}

              <Field label="Extra params (JSON)">
                <textarea
                  value={form.extra_params}
                  onChange={(e) => setForm({ ...form, extra_params: e.target.value })}
                  rows={3}
                  className={clsx(inputCls, "resize-none font-mono text-xs")}
                />
              </Field>

              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_primary}
                    onChange={(e) => setForm({ ...form, is_primary: e.target.checked })}
                    className="accent-blue-500"
                  />
                  Set as primary
                </label>
                <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_secondary}
                    onChange={(e) => setForm({ ...form, is_secondary: e.target.checked })}
                    className="accent-blue-500"
                  />
                  Set as secondary
                </label>
              </div>

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  onClick={submit}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 transition-colors"
                >
                  {editId ? "Save changes" : "Add model"}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-white transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-white placeholder-muted outline-none focus:border-blue-500 transition-colors";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs text-muted">{label}</label>
      {children}
    </div>
  );
}

interface RuntimeCfg {
  mode: string;
  primary_model: string;
  secondary_model: string;
  api_base: string;
  api_key_set: boolean;
  api_key_masked: string;
  autonomous: boolean;
}

function RuntimeSection() {
  const [cfg, setCfg] = useState<RuntimeCfg | null>(null);
  const [form, setForm] = useState<Partial<RuntimeCfg> & { api_key?: string }>({});
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () =>
    fetch("/api/settings/runtime")
      .then((r) => r.json())
      .then((c) => {
        setCfg(c);
        setForm({
          mode: c.mode,
          primary_model: c.primary_model,
          secondary_model: c.secondary_model,
          api_base: c.api_base,
        });
      });

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    const body: Record<string, unknown> = {
      mode: form.mode,
      primary_model: form.primary_model,
      secondary_model: form.secondary_model,
      api_base: form.api_base,
    };
    if (form.api_key) body.api_key = form.api_key;
    const r = await fetch("/api/settings/runtime", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setCfg(await r.json());
    setForm((f) => ({ ...f, api_key: "" }));
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!cfg) return null;

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Cpu size={16} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">Agent runtime</h2>
        <span
          className={clsx(
            "ml-auto rounded px-2 py-0.5 font-mono text-xs",
            cfg.autonomous ? "bg-green-500/20 text-green-400" : "bg-surface-4 text-muted"
          )}
        >
          autonomous {cfg.autonomous ? "ON" : "OFF"}
        </span>
      </div>
      <p className="mb-4 text-xs text-muted">
        The model and credentials the agent actually uses. Changes apply live (no restart).
        Autonomous is toggled from the Agent dashboard.
      </p>

      <div className="space-y-3">
        <Field label="Mode">
          <select
            value={form.mode}
            onChange={(e) => setForm({ ...form, mode: e.target.value })}
            className={inputCls}
          >
            <option value="real">real (calls the LLM)</option>
            <option value="fake">fake (deterministic, no API calls)</option>
          </select>
        </Field>
        <Field label="Primary model (directive / strategy / probability)">
          <input
            value={form.primary_model ?? ""}
            onChange={(e) => setForm({ ...form, primary_model: e.target.value })}
            className={inputCls}
          />
        </Field>
        <Field label="Secondary model (situation / lightweight)">
          <input
            value={form.secondary_model ?? ""}
            onChange={(e) => setForm({ ...form, secondary_model: e.target.value })}
            className={inputCls}
          />
        </Field>
        <Field label="API base URL (OpenAI-compatible endpoint)">
          <input
            value={form.api_base ?? ""}
            onChange={(e) => setForm({ ...form, api_base: e.target.value })}
            className={inputCls}
          />
        </Field>
        <Field label={`API key ${cfg.api_key_set ? `(current: ${cfg.api_key_masked})` : "(not set)"}`}>
          <input
            type="password"
            value={form.api_key ?? ""}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            placeholder="Leave blank to keep existing"
            className={inputCls}
          />
        </Field>
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save runtime"}
          </button>
          {saved && <span className="text-xs text-green-400">saved</span>}
        </div>
      </div>
    </div>
  );
}
