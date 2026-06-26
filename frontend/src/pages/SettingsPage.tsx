import { useCallback, useEffect, useState } from "react";
import { Trash2, Cpu, Palette, RefreshCw, Loader2, CheckCircle2, XCircle } from "lucide-react";
import clsx from "clsx";
import { ACCENT_PRESETS, applyAccent, currentAccent } from "../theme";

export function SettingsPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 font-mono text-lg font-semibold text-white">Settings</h1>
        <p className="mb-6 text-sm text-muted">
          The model the agent and chat run on, plus appearance.
        </p>

        <RuntimeSection />
        <div className="mt-6" />
        <AppearanceSection />
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

function AppearanceSection() {
  const [accent, setAccent] = useState<string>(currentAccent());

  const pick = (key: string) => {
    applyAccent(key);
    setAccent(key);
  };

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Palette size={16} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">Appearance</h2>
      </div>
      <p className="mb-4 text-xs text-muted">
        Accent color. The default is monochrome (black); pick another to recolor the interface.
      </p>
      <div className="flex flex-wrap gap-2">
        {ACCENT_PRESETS.map((p) => (
          <button
            key={p.key}
            onClick={() => pick(p.key)}
            className={clsx(
              "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-colors",
              accent === p.key
                ? "border-blue-500 text-white"
                : "border-border text-muted hover:text-white"
            )}
          >
            <span
              className="h-3 w-3 rounded-full"
              style={{ background: p.stops[3], border: "1px solid rgba(255,255,255,0.15)" }}
            />
            {p.label}
          </button>
        ))}
      </div>
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

const CUSTOM = "__custom__";

// A model picker: a dropdown of live/fetched models with a "Custom…" escape to type any id.
function ModelSelect({
  value, models, onChange,
}: { value: string; models: string[]; onChange: (v: string) => void }) {
  const known = models.includes(value);
  const [custom, setCustom] = useState(!known && !!value);

  // Keep the current value selectable even if the live list doesn't include it.
  const options = Array.from(new Set([...(value ? [value] : []), ...models]));

  if (custom) {
    return (
      <div className="flex items-center gap-2">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. openai/moonshot-v1-128k"
          className={inputCls}
        />
        <button
          onClick={() => setCustom(false)}
          className="flex-shrink-0 rounded-lg border border-border px-2 py-2 text-[11px] text-muted hover:text-white transition-colors"
        >
          list
        </button>
      </div>
    );
  }
  return (
    <select
      value={known ? value : ""}
      onChange={(e) => (e.target.value === CUSTOM ? setCustom(true) : onChange(e.target.value))}
      className={inputCls}
    >
      {options.length === 0 && <option value="">(load models or choose Custom)</option>}
      {options.map((m) => (
        <option key={m} value={m}>{m}</option>
      ))}
      <option value={CUSTOM}>Custom…</option>
    </select>
  );
}

// The one place LLM config lives. The agent and the interactive chat both run on this; there is
// no separate "chat model" any more. Model fields are live dropdowns fetched from the provider.
function RuntimeSection() {
  const [cfg, setCfg] = useState<RuntimeCfg | null>(null);
  const [form, setForm] = useState<Partial<RuntimeCfg> & { api_key?: string }>({});
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const [models, setModels] = useState<string[]>([]);
  const [modelsState, setModelsState] = useState<"idle" | "loading" | "live" | "fallback">("idle");
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [test, setTest] = useState<{ ok: boolean; detail: string } | null>(null);
  const [testing, setTesting] = useState(false);

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

  // Fetch the provider's models for the dropdowns. Uses the unsaved key/base if present so you
  // can populate before saving. Read-only — spends no tokens.
  const loadModels = useCallback((base?: string, key?: string, hint?: string) => {
    setModelsState("loading");
    setModelsError(null);
    fetch("/api/settings/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_base: base ?? null, api_key: key ?? null, model_hint: hint ?? null }),
    })
      .then((r) => r.json())
      .then((d: { models: string[]; source: string; error: string | null }) => {
        setModels(d.models || []);
        setModelsState(d.source === "live" ? "live" : "fallback");
        setModelsError(d.error);
      })
      .catch((e) => { setModelsState("fallback"); setModelsError(String(e)); });
  }, []);

  // Auto-load models once the config is known.
  useEffect(() => {
    if (cfg) loadModels(cfg.api_base, undefined, cfg.primary_model);
  }, [cfg, loadModels]);

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

  const removeKey = async () => {
    const r = await fetch("/api/settings/runtime/api-key", { method: "DELETE" });
    setCfg(await r.json());
    setForm((f) => ({ ...f, api_key: "" }));
  };

  const testConnection = async () => {
    setTesting(true);
    setTest(null);
    try {
      const r = await fetch("/api/settings/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_base: form.api_base ?? null,
          api_key: form.api_key || null,
          model_hint: form.primary_model ?? null,
        }),
      });
      setTest(await r.json());
    } catch (e) {
      setTest({ ok: false, detail: String(e) });
    } finally {
      setTesting(false);
    }
  };

  if (!cfg) return null;

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Cpu size={16} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">Language model</h2>
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
        The model and credentials the agent and chat both run on. Changes apply live (no restart).
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
        <Field label="API base URL (OpenAI-compatible endpoint)">
          <input
            value={form.api_base ?? ""}
            onChange={(e) => setForm({ ...form, api_base: e.target.value })}
            onBlur={(e) => loadModels(e.target.value, form.api_key, form.primary_model)}
            placeholder="e.g. https://api.moonshot.ai/v1"
            className={inputCls}
          />
        </Field>
        <Field label={`API key ${cfg.api_key_set ? `(current: ${cfg.api_key_masked})` : "(not set)"}`}>
          <div className="flex items-center gap-2">
            <input
              type="password"
              value={form.api_key ?? ""}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder={cfg.api_key_set ? "Leave blank to keep existing" : "Paste key (sk-…)"}
              className={inputCls}
            />
            {cfg.api_key_set && (
              <button
                onClick={removeKey}
                title="Remove the stored key (reverts to the .env default)"
                className="flex-shrink-0 rounded-lg border border-border p-2 text-muted hover:border-red-500/50 hover:text-red-400 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </Field>

        {/* Models — live dropdowns */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">
            Models{" "}
            {modelsState === "live" && <span className="text-green-400">· live ({models.length})</span>}
            {modelsState === "fallback" && <span className="text-amber-400">· fallback list</span>}
          </span>
          <button
            onClick={() => loadModels(form.api_base, form.api_key, form.primary_model)}
            disabled={modelsState === "loading"}
            className="flex items-center gap-1 text-[11px] text-muted hover:text-white transition-colors disabled:opacity-50"
          >
            {modelsState === "loading" ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            refresh
          </button>
        </div>
        {modelsError && (
          <p className="text-[11px] text-amber-400">⚠️ {modelsError} — showing fallback list.</p>
        )}
        <Field label="Primary model (directive / strategy / probability / chat)">
          <ModelSelect
            value={form.primary_model ?? ""}
            models={models}
            onChange={(v) => setForm({ ...form, primary_model: v })}
          />
        </Field>
        <Field label="Secondary model (situation / lightweight)">
          <ModelSelect
            value={form.secondary_model ?? ""}
            models={models}
            onChange={(v) => setForm({ ...form, secondary_model: v })}
          />
        </Field>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            onClick={testConnection}
            disabled={testing}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:border-blue-500 hover:text-white transition-colors disabled:opacity-50"
          >
            {testing ? <Loader2 size={13} className="animate-spin" /> : <Cpu size={13} />}
            Test connection
          </button>
          {saved && <span className="text-xs text-green-400">saved</span>}
          {test && (
            <span className={clsx("flex items-center gap-1 text-xs", test.ok ? "text-green-400" : "text-red-400")}>
              {test.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              {test.detail}
            </span>
          )}
        </div>
        {cfg.api_key_set && (
          <p className="text-[11px] text-muted">
            Key stored in <span className="font-mono">workspace/state/runtime.json</span> (temporary,
            overlays .env). The trash button clears it.
          </p>
        )}
      </div>
    </div>
  );
}
