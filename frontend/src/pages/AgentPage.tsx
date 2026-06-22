import { useCallback, useEffect, useState } from "react";
import {
  Play, Power, Clock, RefreshCw, Loader2, Wallet, TrendingUp,
  ShieldAlert, Activity, GitBranch,
} from "lucide-react";
import clsx from "clsx";

interface Conn { ok: boolean; detail: string }

interface AgentStatus {
  initialised: boolean;
  wallet_balance_usdc: number;
  available_balance_usdc: number;
  total_pnl: number;
  open_positions: number;
  open_exposure_usdc: number;
  circuit_breaker_active: boolean;
  balance_is_simulated: boolean;
  connections: { llm: Conn; polymarket_wallet: Conn; search: Conn };
  next_heartbeat: { fire_at: string; reason: string; session_type: string } | null;
  last_session: { summary: string; started_at: string } | null;
}

interface Heartbeat {
  id: string;
  fire_at: string;
  reason: string;
  session_type: string;
  status: string;
  spawned_by: string | null;
}

interface Session {
  id: string;
  outcome_summary: string | null;
  bets_placed: number;
  research_calls: number;
  heartbeats_created: number;
  started_at: string | null;
  directive: { session_type?: string; primary_focus?: string; financial_context?: string } | null;
}

const STATUS_COLORS: Record<string, string> = {
  SCHEDULED: "text-blue-400",
  RUNNING: "text-amber-400",
  DONE: "text-green-400",
  FAILED: "text-red-400",
  CANCELLED: "text-muted",
};

interface Runtime {
  mode: string;
  primary_model: string;
  secondary_model: string;
  api_key_set: boolean;
  autonomous: boolean;
}

export function AgentPage() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [construct, setConstruct] = useState<Record<string, string>>({});
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [focus, setFocus] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, se, c, rt] = await Promise.all([
        fetch("/api/agent/status").then((r) => r.json()),
        fetch("/api/agent/heartbeats?limit=20").then((r) => r.json()),
        fetch("/api/agent/sessions?limit=15").then((r) => r.json()),
        fetch("/api/agent/construct").then((r) => r.json()),
        fetch("/api/settings/runtime").then((r) => r.json()),
      ]);
      setStatus(s);
      setHeartbeats(h);
      setSessions(se);
      setConstruct(c.documents || {});
      setRuntime(rt);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const toggleAutonomous = async () => {
    if (!runtime) return;
    setBusy("autonomous");
    try {
      const r = await fetch("/api/settings/runtime", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ autonomous: !runtime.autonomous }),
      });
      setRuntime(await r.json());
    } finally {
      setBusy(null);
    }
  };

  const runWithFocus = async () => {
    setBusy("run");
    setError("");
    try {
      const r = await fetch("/api/agent/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(focus.trim() ? { focus: focus.trim() } : {}),
      });
      const data = await r.json();
      if (!r.ok) setError(data.detail || "run failed");
      setFocus("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const action = async (path: string, label: string) => {
    setBusy(label);
    setError("");
    try {
      const r = await fetch(path, { method: "POST" });
      const data = await r.json();
      if (!r.ok) setError(data.detail || `${label} failed`);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
        {/* Header + controls */}
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-blue-400" />
            <h1 className="font-mono text-lg font-semibold text-white">Agent</h1>
            {status && !status.initialised && (
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
                not bootstrapped
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Btn onClick={() => action("/api/agent/boot", "boot")} busy={busy === "boot"} icon={Power}>
              First Light
            </Btn>
            <Btn onClick={() => action("/api/agent/run-due", "due")} busy={busy === "due"} icon={Clock}>
              Fire due
            </Btn>
            <button
              onClick={refresh}
              className="rounded-lg border border-border p-2 text-muted hover:text-white transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Runtime + autonomy bar */}
        {runtime && (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-1 px-4 py-3">
            <span className="font-mono text-xs text-muted">
              model: <span className="text-blue-300">{runtime.primary_model}</span>
              <span className="mx-2 text-surface-4">·</span>
              mode: <span className={runtime.mode === "real" ? "text-green-400" : "text-amber-400"}>{runtime.mode}</span>
              <span className="mx-2 text-surface-4">·</span>
              key: <span className={runtime.api_key_set ? "text-green-400" : "text-red-400"}>{runtime.api_key_set ? "set" : "missing"}</span>
            </span>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-muted">Autonomous scheduler</span>
              <button
                onClick={toggleAutonomous}
                disabled={busy === "autonomous"}
                className={clsx(
                  "relative h-5 w-10 rounded-full transition-colors",
                  runtime.autonomous ? "bg-green-600" : "bg-surface-4"
                )}
                title={runtime.autonomous ? "Agent wakes itself on schedule" : "Manual only — no auto runs"}
              >
                <span
                  className={clsx(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
                    runtime.autonomous ? "translate-x-5" : "translate-x-0.5"
                  )}
                />
              </button>
              <span className={clsx("font-mono text-xs", runtime.autonomous ? "text-green-400" : "text-muted")}>
                {runtime.autonomous ? "ON" : "OFF"}
              </span>
            </div>
          </div>
        )}

        {/* Brief directive session */}
        <div className="mb-5 flex items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 py-2">
          <input
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runWithFocus()}
            placeholder="Run a session with an optional focus, e.g. 'survey politics markets closing this week'…"
            className="flex-1 bg-transparent text-sm text-white placeholder-muted outline-none"
          />
          <Btn onClick={runWithFocus} busy={busy === "run"} icon={Play}>
            Run session
          </Btn>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Status cards */}
        {status && (
          <>
            <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat
                icon={Wallet}
                label={status.balance_is_simulated ? "Balance (sim)" : "Wallet"}
                value={`$${status.wallet_balance_usdc.toFixed(2)}`}
              />
              <Stat
                icon={TrendingUp}
                label="Total P&L"
                value={`${status.total_pnl >= 0 ? "+" : ""}$${status.total_pnl.toFixed(2)}`}
                tone={status.total_pnl >= 0 ? "pos" : "neg"}
              />
              <Stat
                icon={Activity}
                label="Exposure"
                value={`$${status.open_exposure_usdc.toFixed(2)} (${status.open_positions})`}
              />
              <Stat
                icon={ShieldAlert}
                label="Circuit breaker"
                value={status.circuit_breaker_active ? "TRIPPED" : "clear"}
                tone={status.circuit_breaker_active ? "neg" : "pos"}
              />
            </div>

            {/* Connection checks */}
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <ConnChip label="LLM" conn={status.connections.llm} />
              <ConnChip label="Wallet" conn={status.connections.polymarket_wallet} />
              <ConnChip label="Search" conn={status.connections.search} />
              {status.balance_is_simulated && (
                <span className="text-[11px] text-amber-400/80">
                  balance is the simulated budget — no live Polymarket wallet connected
                </span>
              )}
            </div>
          </>
        )}

        {/* Next heartbeat */}
        {status?.next_heartbeat && (
          <div className="mb-5 flex items-center gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3">
            <Clock size={16} className="flex-shrink-0 text-blue-400" />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-white">
                Next wake: <span className="font-mono text-blue-300">{status.next_heartbeat.session_type}</span>
              </p>
              <p className="truncate text-xs text-muted">{status.next_heartbeat.reason}</p>
            </div>
            <span className="flex-shrink-0 font-mono text-xs text-muted">
              {fmt(status.next_heartbeat.fire_at)}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Heartbeat schedule */}
          <Panel title="Heartbeat schedule" icon={Clock}>
            {heartbeats.length === 0 && <Empty>No heartbeats yet — run First Light.</Empty>}
            {heartbeats.map((h) => (
              <div key={h.id} className="border-b border-surface-3 py-2 last:border-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-white">{h.session_type}</span>
                  <span className={clsx("font-mono text-xs", STATUS_COLORS[h.status] ?? "text-muted")}>
                    {h.status}
                  </span>
                </div>
                <p className="truncate text-xs text-muted">{h.reason}</p>
                <p className="font-mono text-[10px] text-muted/70">{fmt(h.fire_at)}</p>
              </div>
            ))}
          </Panel>

          {/* Session history — click a row to expand its directive */}
          <Panel title="Sessions" icon={Activity}>
            {sessions.length === 0 && <Empty>No sessions run yet.</Empty>}
            {sessions.map((s) => (
              <div key={s.id} className="border-b border-surface-3 py-2 last:border-0">
                <button
                  onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                  className="w-full text-left"
                >
                  <p className="text-xs text-white hover:text-blue-300 transition-colors">
                    {s.outcome_summary || "(no summary)"}
                  </p>
                  <p className="font-mono text-[10px] text-muted/70">
                    {fmt(s.started_at)} · {s.bets_placed} bets · {s.research_calls} research ·{" "}
                    {s.heartbeats_created} scheduled
                  </p>
                </button>
                {expanded === s.id && s.directive && (
                  <div className="mt-2 rounded-lg border border-surface-3 bg-surface-0 p-2 text-[11px]">
                    <p className="text-blue-300">{s.directive.session_type}</p>
                    {s.directive.primary_focus && (
                      <p className="mt-1 text-muted">
                        <span className="text-white">Focus:</span> {s.directive.primary_focus}
                      </p>
                    )}
                    {s.directive.financial_context && (
                      <p className="mt-1 text-muted">{s.directive.financial_context}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </Panel>
        </div>

        {/* Mental construct */}
        <div className="mt-5">
          <Panel title="Mental construct" icon={GitBranch}>
            {Object.entries(construct).map(([name, body]) => (
              <details key={name} className="border-b border-surface-3 py-1.5 last:border-0">
                <summary className="cursor-pointer font-mono text-xs text-blue-300 hover:text-white">
                  {name}
                </summary>
                <pre className="mt-1.5 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted">
                  {body?.trim() || "(empty)"}
                </pre>
              </details>
            ))}
            <p className="mt-2 text-[10px] text-muted/60">
              Edit these in the Workspace tab — they are the agent's cognition.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Btn({
  onClick, busy, icon: Icon, children,
}: {
  onClick: () => void; busy: boolean; icon: typeof Play; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:border-blue-500 hover:text-white transition-colors disabled:opacity-50"
    >
      {busy ? <Loader2 size={13} className="animate-spin" /> : <Icon size={13} />}
      {children}
    </button>
  );
}

function Stat({
  icon: Icon, label, value, tone,
}: {
  icon: typeof Wallet; label: string; value: string; tone?: "pos" | "neg";
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
      <div className="mb-1 flex items-center gap-1.5 text-muted">
        <Icon size={12} />
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <p className={clsx("font-mono text-sm font-medium",
        tone === "pos" ? "text-green-400" : tone === "neg" ? "text-red-400" : "text-white")}>
        {value}
      </p>
    </div>
  );
}

function Panel({ title, icon: Icon, children }: { title: string; icon: typeof Clock; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon size={14} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="max-h-80 overflow-y-auto">{children}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-4 text-center text-xs text-muted">{children}</p>;
}

function ConnChip({ label, conn }: { label: string; conn: { ok: boolean; detail: string } }) {
  return (
    <span
      title={conn.detail}
      className={clsx(
        "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
        conn.ok ? "border-green-500/30 text-green-400" : "border-surface-4 text-muted"
      )}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", conn.ok ? "bg-green-400" : "bg-surface-4")} />
      {label}: {conn.ok ? "connected" : "off"}
    </span>
  );
}

function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
