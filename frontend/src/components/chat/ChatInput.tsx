import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { Send, Square, Brain, Wrench, X } from "lucide-react";
import clsx from "clsx";

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
}

export function ChatInput({ onSend, onStop, streaming, disabled }: Props) {
  const [value, setValue] = useState("");
  const [thinking, setThinking] = useState(false);
  const [skillsOn, setSkillsOn] = useState(true);
  const [showSkills, setShowSkills] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (showSkills && skills.length === 0) {
      fetch("/api/agent/skills").then((r) => r.json()).then(setSkills).catch(() => {});
    }
  }, [showSkills, skills.length]);

  const submit = () => {
    const text = value.trim();
    if (!text || streaming || disabled) return;
    onSend(text, { thinking, skills: skillsOn });
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  };

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

  return (
    <div className="border-t border-border bg-surface-1 p-4">
      {/* Skills popover */}
      {showSkills && (
        <div className="mx-auto mb-2 max-w-3xl rounded-xl border border-border bg-surface-2 p-3">
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
        </div>
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
          <button
            onClick={() => setShowSkills((v) => !v)}
            className="text-xs text-muted hover:text-white transition-colors"
          >
            view skills
          </button>
        </div>

        <div className="flex items-end gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3 focus-within:border-blue-500 transition-colors">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            onInput={onInput}
            placeholder={disabled ? "Connecting..." : "Message littleman... (Enter to send, Shift+Enter for newline)"}
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
        <p className="mt-1.5 text-center text-xs text-muted">
          littleman can make mistakes. Verify bets before they execute.
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
