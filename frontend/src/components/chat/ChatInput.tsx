import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { Send, Square, Brain, Wrench, X, Sparkles, HelpCircle } from "lucide-react";
import clsx from "clsx";
import { Island } from "../ui/Island";
import type { Elicitation } from "../../types";

interface Skill {
  name: string;
  description: string;
  cost: string;
  available: boolean;
}

interface Props {
  onSend: (text: string, opts: { thinking: boolean; skills: boolean }) => void;
  onStop?: () => void;
  streaming: boolean;
  disabled: boolean;
  centered?: boolean;
  /** Session id, used to fetch predictive suggestions when the Suggest toggle is on. */
  sessionId?: string;
  /** An LLM-emitted question to answer; when present the composer morphs into a question card. */
  elicitation?: Elicitation | null;
}

const SUGGEST_KEY = "littleman.suggest";

export function ChatInput({ onSend, onStop, streaming, disabled, centered, sessionId, elicitation }: Props) {
  const [value, setValue] = useState("");
  const [thinking, setThinking] = useState(false);
  const [skillsOn, setSkillsOn] = useState(true);
  const [showSkills, setShowSkills] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  // Suggestion bar — opt-in (off by default) so it never spends tokens unless the operator asks.
  const [suggestOn, setSuggestOn] = useState(() => localStorage.getItem(SUGGEST_KEY) === "1");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (showSkills && skills.length === 0) {
      fetch("/api/agent/skills").then((r) => r.json()).then(setSkills).catch(() => {});
    }
  }, [showSkills, skills.length]);

  // Fetch predictive suggestions when enabled and the conversation is idle (never mid-stream,
  // never on a loop). Re-runs when a turn completes (streaming → false) or the toggle flips on.
  useEffect(() => {
    if (!suggestOn || streaming || !sessionId) return;
    let cancelled = false;
    setSuggestLoading(true);
    fetch(`/api/chat/sessions/${sessionId}/suggestions`, { method: "POST" })
      .then((r) => r.json())
      .then((d: { suggestions?: string[] }) => {
        if (!cancelled) setSuggestions(Array.isArray(d.suggestions) ? d.suggestions : []);
      })
      .catch(() => { if (!cancelled) setSuggestions([]); })
      .finally(() => { if (!cancelled) setSuggestLoading(false); });
    return () => { cancelled = true; };
  }, [suggestOn, streaming, sessionId]);

  const toggleSuggest = () => {
    setSuggestOn((v) => {
      const next = !v;
      localStorage.setItem(SUGGEST_KEY, next ? "1" : "0");
      if (!next) setSuggestions([]);
      return next;
    });
  };

  const send = (text: string) => {
    const t = text.trim();
    if (!t || streaming || disabled) return;
    onSend(t, { thinking, skills: skillsOn });
    setValue("");
    setSuggestions([]);
    if (ref.current) ref.current.style.height = "auto";
  };

  const submit = () => send(value);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onInput = () => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 200)}px`;
    }
  };

  const fillSuggestion = (text: string) => {
    setValue(text);
    setTimeout(() => { ref.current?.focus(); onInput(); }, 0);
  };

  return (
    <div className={centered ? "px-4 pb-2" : "border-t border-border bg-surface-1 p-4"}>
      {/* Skills popover */}
      {showSkills && (
        <Island floating className="mx-auto mb-2 max-w-3xl p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-xs text-white">Available skills</span>
            <button onClick={() => setShowSkills(false)} className="text-muted hover:text-white">
              <X size={14} />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            {skills.map((s) => (
              <div key={s.name} className="flex items-start gap-2 text-xs">
                <span className={clsx("mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full",
                  s.available ? "bg-green-400" : "bg-surface-4")} />
                <div className="min-w-0">
                  <span className={clsx("font-mono", s.available ? "text-blue-300" : "text-muted line-through")}>
                    {s.name}
                  </span>
                  <p className="truncate text-muted">{s.description}</p>
                </div>
              </div>
            ))}
            {skills.length === 0 && <p className="text-xs text-muted">Loading...</p>}
          </div>
        </Island>
      )}

      <div className="mx-auto max-w-3xl">
        {/* Option toggles */}
        <div className="mb-2 flex items-center gap-2">
          <Toggle active={thinking} onClick={() => setThinking((v) => !v)} icon={Brain} title="Show model reasoning (if supported)">
            Thinking
          </Toggle>
          <Toggle active={skillsOn} onClick={() => setSkillsOn((v) => !v)} icon={Wrench} title="Expose agent skills/tools to this chat">
            Skills
          </Toggle>
          <Toggle active={suggestOn} onClick={toggleSuggest} icon={Sparkles} title="Predictive prompt suggestions (uses the model; off by default)">
            Suggest
          </Toggle>
          <button
            onClick={() => setShowSkills((v) => !v)}
            className="text-xs text-muted hover:text-white transition-colors"
          >
            view skills
          </button>
        </div>

        {/* Suggestion bar — predictive prompts the operator likely wants next */}
        {suggestOn && !elicitation && (suggestions.length > 0 || suggestLoading) && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {suggestLoading && suggestions.length === 0 ? (
              <span className="text-[11px] text-muted">thinking of suggestions…</span>
            ) : (
              suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => fillSuggestion(s)}
                  className="rounded-island border border-border bg-surface-2 px-2.5 py-1 text-left text-[11px] text-gray-300 hover:border-blue-500 hover:text-white transition-colors"
                >
                  {s}
                </button>
              ))
            )}
          </div>
        )}

        <Island interactive className="px-4 py-3">
          {/* Elicitation morph — the composer becomes the LLM's question card */}
          {elicitation && (
            <div className="mb-3 border-b border-border pb-3">
              <div className="mb-2 flex items-start gap-2">
                <HelpCircle size={14} className="mt-0.5 flex-shrink-0 text-blue-400" />
                <span className="text-sm text-white">{elicitation.question}</span>
              </div>
              {elicitation.options.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {elicitation.options.map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => send(opt)}
                      disabled={disabled || streaming}
                      className="rounded-island border border-blue-500/40 bg-blue-500/10 px-3 py-1.5 text-xs text-blue-200 hover:bg-blue-500/20 disabled:opacity-50 transition-colors"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
              <p className="mt-2 text-[10px] text-muted">or type your own answer below</p>
            </div>
          )}

          <div className="flex items-end gap-3">
            <textarea
              ref={ref}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={onKeyDown}
              onInput={onInput}
              placeholder={
                disabled ? "Connecting..."
                : elicitation ? "Type your own answer..."
                : "Message littleman... (Enter to send, Shift+Enter for newline)"
              }
              disabled={disabled || streaming}
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-white placeholder-muted outline-none disabled:opacity-50"
              style={{ minHeight: "24px", maxHeight: "200px" }}
            />
            {streaming ? (
              <button
                onClick={onStop}
                title="Stop generating"
                className="flex-shrink-0 rounded-lg border border-red-500/40 p-1.5 text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                onClick={submit}
                disabled={!value.trim() || disabled}
                className={clsx(
                  "flex-shrink-0 rounded-lg p-1.5 transition-colors",
                  value.trim() && !disabled
                    ? "text-blue-400 hover:bg-surface-4"
                    : "text-muted cursor-not-allowed"
                )}
              >
                <Send size={18} />
              </button>
            )}
          </div>
        </Island>
        <p className="mt-1.5 text-center text-xs text-muted">
          littleman can make mistakes. Review its actions.
        </p>
      </div>
    </div>
  );
}

function Toggle({
  active, onClick, icon: Icon, title, children,
}: {
  active: boolean; onClick: () => void; icon: typeof Brain; title: string; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={clsx(
        "flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-colors",
        active
          ? "border-blue-500 bg-blue-500/10 text-blue-300"
          : "border-border text-muted hover:text-white"
      )}
    >
      <Icon size={12} />
      {children}
    </button>
  );
}
