import { useState } from "react";
import { Bot, ArrowRight, ArrowLeft, ListChecks, MessageSquare, Loader2 } from "lucide-react";
import clsx from "clsx";
import { CUSTOM_KEY, PROVIDERS, ProviderPreset, fullModel } from "../llm-providers";

interface Props {
  onDone: () => void;
}

export function OnboardingPage({ onDone }: Props) {
  const [step, setStep] = useState<"welcome" | "guided">("welcome");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Shared welcome fields
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [providerKey, setProviderKey] = useState("kimi");
  const [model, setModel] = useState(PROVIDERS.find((p) => p.key === "kimi")!.models[0]);
  const [apiBase, setApiBase] = useState(PROVIDERS.find((p) => p.key === "kimi")!.apiBase);
  const [apiKey, setApiKey] = useState("");
  const [path, setPath] = useState<"guided" | "custom">("guided");

  // Guided questionnaire fields
  const [objective, setObjective] = useState("");
  const [focus, setFocus] = useState("");
  const [constraints, setConstraints] = useState("");
  const [autonomy, setAutonomy] = useState("");

  const provider: ProviderPreset = PROVIDERS.find((p) => p.key === providerKey)!;

  const pickProvider = (key: string) => {
    const p = PROVIDERS.find((x) => x.key === key)!;
    setProviderKey(key);
    setModel(p.models[0]);
    setApiBase(p.apiBase);
  };

  const postWelcome = async () => {
    const body = {
      display_name: name.trim(),
      purpose: purpose.trim(),
      provider: providerKey,
      model: provider.prefix + model,
      secondary_model: fullModel(provider, 1),
      api_base: apiBase,
      api_key: apiKey || null,
    };
    const r = await fetch("/api/onboarding/welcome", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error("welcome failed");
  };

  const complete = async (chosen: "guided" | "custom", answers?: Record<string, string>) => {
    const r = await fetch("/api/onboarding/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: chosen, answers: answers ?? null }),
    });
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || "complete failed");
  };

  const finishWelcome = async () => {
    if (!name.trim() || !purpose.trim()) {
      setError("Add a name and a purpose to continue.");
      return;
    }
    if (provider.key !== "ollama" && !apiKey) {
      setError("This provider needs an API key.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await postWelcome();
      if (path === "custom") {
        await complete(CUSTOM_KEY as "custom");
        onDone();
        window.location.assign("/chat/main");
      } else {
        setStep("guided");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const finishGuided = async () => {
    setBusy(true);
    setError("");
    try {
      await complete("guided", { objective, focus, constraints, autonomy });
      onDone();
      window.location.assign("/chat/main");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center overflow-y-auto bg-surface-0 px-4 py-10">
      <div className="w-full max-w-xl rounded-2xl border border-border bg-surface-1 p-6">
        {/* Bare brand */}
        <div className="mb-5 flex items-center gap-2">
          <Bot size={20} className="text-blue-400" />
          <span className="font-mono text-base font-semibold text-white">littleman</span>
          <span className="ml-auto text-xs text-muted">
            {step === "welcome" ? "step 1 of 2 · welcome" : "step 2 of 2 · details"}
          </span>
        </div>

        {step === "welcome" && (
          <>
            <p className="mb-5 text-sm text-muted">
              Tell the agent who you are and what it's for. The purpose you write is what gives it
              its domain.
            </p>

            <Field label="What should we call you?">
              <input value={name} onChange={(e) => setName(e.target.value)} className={inp} placeholder="Your name" />
            </Field>

            <Field label="What should we do?  (the agent's purpose)">
              <textarea
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                rows={3}
                className={clsx(inp, "resize-none")}
                placeholder="e.g. Research and trade Polymarket prediction markets for profit from a fixed budget, managing risk autonomously."
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Provider">
                <select value={providerKey} onChange={(e) => pickProvider(e.target.value)} className={inp}>
                  {PROVIDERS.map((p) => (
                    <option key={p.key} value={p.key}>{p.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Model">
                <select value={model} onChange={(e) => setModel(e.target.value)} className={inp}>
                  {provider.models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </Field>
            </div>

            {(provider.apiBase || providerKey === "openrouter") && (
              <Field label="API base URL">
                <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} className={inp} />
              </Field>
            )}
            {provider.key !== "ollama" && (
              <Field label="API key">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className={inp}
                  placeholder="Stored locally in .env, never committed"
                />
              </Field>
            )}

            {/* Branch */}
            <div className="mt-5 border-t border-surface-3 pt-5">
              <p className="mb-3 text-sm text-muted">How do you want to set the details and constraints?</p>
              <div className="grid grid-cols-2 gap-3">
                <BranchCard
                  active={path === "guided"}
                  onClick={() => setPath("guided")}
                  icon={ListChecks}
                  title="Guided"
                  desc="A short questionnaire builds your SOUL.md."
                  recommended
                />
                <BranchCard
                  active={path === "custom"}
                  onClick={() => setPath("custom")}
                  icon={MessageSquare}
                  title="Custom"
                  desc="Configure by talking to the agent in chat."
                />
              </div>
            </div>

            {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

            <div className="mt-5 flex justify-end">
              <button onClick={finishWelcome} disabled={busy} className={primaryBtn}>
                {busy ? <Loader2 size={15} className="animate-spin" /> : <>Continue <ArrowRight size={15} /></>}
              </button>
            </div>
          </>
        )}

        {step === "guided" && (
          <>
            <p className="mb-5 text-sm text-muted">
              A few questions to shape the agent. All optional, but the more you give, the better
              its first bearings.
            </p>
            <Field label="Objective and what success looks like">
              <textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={2} className={clsx(inp, "resize-none")} />
            </Field>
            <Field label="Focus  (what to prioritize, what to avoid)">
              <textarea value={focus} onChange={(e) => setFocus(e.target.value)} rows={2} className={clsx(inp, "resize-none")} />
            </Field>
            <Field label="Constraints / red lines  (in your own words)">
              <textarea value={constraints} onChange={(e) => setConstraints(e.target.value)} rows={2} className={clsx(inp, "resize-none")} />
            </Field>
            <Field label="Autonomy and check-in  (how independent, when to pause and ask)">
              <textarea value={autonomy} onChange={(e) => setAutonomy(e.target.value)} rows={2} className={clsx(inp, "resize-none")} />
            </Field>

            {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

            <div className="mt-5 flex items-center justify-between">
              <button onClick={() => setStep("welcome")} className={ghostBtn}>
                <ArrowLeft size={15} /> Back
              </button>
              <button onClick={finishGuided} disabled={busy} className={primaryBtn}>
                {busy ? <Loader2 size={15} className="animate-spin" /> : <>Finish <ArrowRight size={15} /></>}
              </button>
            </div>
          </>
        )}

        <p className="mt-5 text-center text-xs text-muted">
          After this, the agent runs its first onboarding (first light) in chat.
        </p>
      </div>
    </div>
  );
}

const inp =
  "w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-white placeholder-muted outline-none focus:border-blue-500 transition-colors";
const primaryBtn =
  "flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 transition-colors disabled:opacity-50";
const ghostBtn =
  "flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:text-white transition-colors";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-xs text-muted">{label}</label>
      {children}
    </div>
  );
}

function BranchCard({
  active, onClick, icon: Icon, title, desc, recommended,
}: {
  active: boolean; onClick: () => void; icon: typeof ListChecks; title: string; desc: string; recommended?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "rounded-xl border p-3 text-left transition-colors",
        active ? "border-blue-500 bg-surface-2" : "border-border hover:border-surface-4"
      )}
    >
      <div className="mb-1 flex items-center gap-2">
        <Icon size={16} className={active ? "text-blue-400" : "text-muted"} />
        <span className="text-sm font-medium text-white">{title}</span>
        {recommended && (
          <span className="ml-auto rounded bg-surface-3 px-1.5 py-0.5 text-[10px] text-muted">recommended</span>
        )}
      </div>
      <p className="text-xs text-muted">{desc}</p>
    </button>
  );
}
