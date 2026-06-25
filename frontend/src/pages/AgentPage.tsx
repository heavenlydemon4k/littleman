import { useCallback, useEffect, useState } from "react";
import {
  Play, Power, Clock, RefreshCw, Loader2, Activity, GitBranch,
  MessageSquare, ChevronDown, ChevronRight, Zap, Eye, X, Plus,
  ArrowRight, Target, ListChecks,
} from "lucide-react";
import clsx from "clsx";

// -- Types -------------------------------------------------------------------

interface Conn { ok: boolean; detail: string }

interface AgentStatus {
  initialised: boolean;
  application: string;
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
  ended_at: string | null;
  directive: { session_type?: string; primary_focus?: string; secondary_focus?: string; financial_context?: string; constraint_notes?: string } | null;
}

interface ObservationItem {
  id: string;
  action_type: string;
  action_detail: Record<string, unknown>;
  rationale: string | null;
  predicted_probability: number | null;
  market_price_at_action: number | null;
  outcome: string | null;
  logged_at: string | null;
}

interface SpawnedHeartbeat {
  id: string;
  fire_at: string | null;
  reason: string;
  session_type: string;
  status: string;
}

interface PositionOpened {
  id: string;
  market_title: string;
  direction: string;
  size_usdc: number;
  entry_price: number;
  predicted_probability: number;
  status: string;
  outcome: string | null;
  pnl: number | null;
}

interface SessionDetail {
  id: string;
  directive: Session["directive"];
  heartbeat: { reason: string; session_type: string; context: Record<string, unknown> } | null;
  observations: ObservationItem[];
  heartbeats_spawned: SpawnedHeartbeat[];
  positions_opened: PositionOpened[];
  outcome_summary: string | null;
  started_at: string | null;
  ended_at: string | null;
  bets_placed: number;
  research_calls: number;
  heartbeats_created: number;
}

interface GuidanceItem {
  id: string;
  text: string;
  created_at: string | null;
  consumed: boolean;
  consumed_at: string | null;
}

interface SkillItem {
  name: string;
  description: string;
  cost: string;
  available: boolean;
}

interface Runtime {
  mode: string;
  primary_model: string;
  secondary_model: string;
  api_key_set: boolean;
  autonomous: boolean;
}

// -- Constants ---------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  SCHEDULED: "text-blue-400",
  RUNNING: "text-amber-400",
  DONE: "text-green-400",
  FAILED: "text-red-400",
  CANCELLED: "text-muted",
};

const SESSION_TYPE_COLORS: Record<string, string> = {
  FULL_CYCLE: "bg-blue-500/20 text-blue-300",
  RESEARCH: "bg-purple-500/20 text-purple-300",
  MONITOR: "bg-teal-500/20 text-teal-300",
  REFLECTION: "bg-amber-500/20 text-amber-300",
  FIRST_LIGHT: "bg-green-500/20 text-green-300",
};

type TabId = "overview" | "activity" | "construct" | "skills";

// -- Main Component ----------------------------------------------------------

export function AgentPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [lastViewedAt, setLastViewedAt] = useState<Date>(() => {
    const stored = localStorage.getItem("agentLastViewedAt");
    return stored ? new Date(stored) : new Date(0);
  });

  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [construct, setConstruct] = useState<Record<string, string>>({});
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [skills, setSkills] = useState<SkillItem[]>([]);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [sessionDetails, setSessionDetails] = useState<Record<string, SessionDetail>>({});
  const [loadingSession, setLoadingSession] = useState<string | null>(null);

  const [guidance, setGuidance] = useState<GuidanceItem[]>([]);
  const [guidanceInput, setGuidanceInput] = useState("");
  const [guidanceBusy, setGuidanceBusy] = useState(false);

  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [skillDocs, setSkillDocs] = useState<Record<string, string>>({});
  const [loadingSkillDoc, setLoadingSkillDoc] = useState<string | null>(null);

  // -- Data fetching ----------------------------------------------------------

  const loadGuidance = useCallback(async () => {
    try {
      const g = await fetch("/api/agent/guidance").then((r) => r.json());
      setGuidance(Array.isArray(g) ? g : []);
    } catch {
      // non-fatal
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [s, h, se, c, rt, sk] = await Promise.all([
        fetch("/api/agent/status").then((r) => r.json()),
        fetch("/api/agent/heartbeats?limit=20").then((r) => r.json()),
        fetch("/api/agent/sessions?limit=30").then((r) => r.json()),
        fetch("/api/agent/construct").then((r) => r.json()),
        fetch("/api/settings/runtime").then((r) => r.json()),
        fetch("/api/agent/skills").then((r) => r.json()),
      ]);
      setStatus(s);
      setHeartbeats(Array.isArray(h) ? h : []);
      setSessions(Array.isArray(se) ? se : []);
      setConstruct(c.documents || {});
      setRuntime(rt);
      setSkills(Array.isArray(sk) ? sk : []);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
    loadGuidance();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh, loadGuidance]);

  useEffect(() => {
    if (activeTab === "activity") {
      loadGuidance();
      const now = new Date();
      localStorage.setItem("agentLastViewedAt", now.toISOString());
      setLastViewedAt(now);
    }
  }, [activeTab, loadGuidance]);

  // -- Session detail lazy load ----------------------------------------------

  const toggleSession = useCallback(async (id: string) => {
    if (expandedSession === id) {
      setExpandedSession(null);
      return;
    }
    setExpandedSession(id);
    if (!sessionDetails[id] && loadingSession !== id) {
      setLoadingSession(id);
      try {
        const d: SessionDetail = await fetch(`/api/agent/sessions/${id}`).then((r) => r.json());
        setSessionDetails((prev) => ({ ...prev, [id]: d }));
      } finally {
        setLoadingSession(null);
      }
    }
  }, [expandedSession, sessionDetails, loadingSession]);

  // -- Skill doc lazy load ---------------------------------------------------

  const toggleSkill = useCallback(async (name: string) => {
    if (expandedSkill === name) {
      setExpandedSkill(null);
      return;
    }
    setExpandedSkill(name);
    if (!skillDocs[name] && loadingSkillDoc !== name) {
      setLoadingSkillDoc(name);
      try {
        const d = await fetch(`/api/agent/skills/${name}/doc`).then((r) => r.json());
        setSkillDocs((prev) => ({ ...prev, [name]: d.content }));
      } finally {
        setLoadingSkillDoc(null);
      }
    }
  }, [expandedSkill, skillDocs, loadingSkillDoc]);

  // -- Guidance actions ------------------------------------------------------

  const submitGuidance = async () => {
    if (!guidanceInput.trim()) return;
    setGuidanceBusy(true);
    try {
      await fetch("/api/agent/guidance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: guidanceInput.trim() }),
      });
      setGuidanceInput("");
      await loadGuidance();
    } finally {
      setGuidanceBusy(false);
    }
  };

  const deleteGuidance = async (id: string) => {
    await fetch(`/api/agent/guidance/${id}`, { method: "DELETE" });
    await loadGuidance();
  };

  // -- Controls --------------------------------------------------------------

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

  // -- Derived ---------------------------------------------------------------

  const newSessionCount = sessions.filter(
    (s) => s.started_at && new Date(s.started_at) > lastViewedAt
  ).length;

  const pendingGuidance = guidance.filter((g) => !g.consumed);

  // -- Render ----------------------------------------------------------------

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">

        {/* Header (always visible) */}
        <div className="mb-4 flex items-center justify-between">
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
              <span className="text-xs text-muted">Autonomous</span>
              <button
                onClick={toggleAutonomous}
                disabled={busy === "autonomous"}
                className={clsx(
                  "relative h-5 w-10 rounded-full transition-colors",
                  runtime.autonomous ? "bg-green-600" : "bg-surface-4"
                )}
                title={runtime.autonomous ? "Agent wakes itself on schedule" : "Manual only -- no auto runs"}
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

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Tab bar */}
        <div className="mb-5 flex items-center gap-1 border-b border-border">
          <Tab id="overview" active={activeTab} onClick={setActiveTab} icon={Activity}>
            Overview
          </Tab>
          <Tab id="activity" active={activeTab} onClick={setActiveTab} icon={Eye} badge={newSessionCount || undefined}>
            Activity
          </Tab>
          <Tab id="construct" active={activeTab} onClick={setActiveTab} icon={GitBranch}>
            Construct
          </Tab>
          <Tab id="skills" active={activeTab} onClick={setActiveTab} icon={Zap}>
            Skills
          </Tab>
        </div>

        {/* TAB: OVERVIEW */}
        {activeTab === "overview" && (
          <div>
            {/* First Light bootstrap CTA -- only when not yet initialised */}
            {status && !status.initialised && (
              <div className="mb-5 rounded-xl border border-amber-500/25 bg-amber-500/5 p-5">
                <div className="flex items-start gap-4">
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                    <Power size={18} className="text-amber-400" />
                  </div>
                  <div className="flex-1">
                    <h3 className="mb-1 font-mono text-sm font-semibold text-white">
                      Agent not bootstrapped
                    </h3>
                    <p className="mb-3 text-xs leading-relaxed text-muted">
                      <strong className="text-amber-300">First Light</strong> is a one-time bootstrap protocol. It seeds the
                      mental construct from the workspace templates, sets the initial directive, and schedules the first
                      heartbeat. Run it once to activate the agent.
                    </p>
                    <Btn onClick={() => action("/api/agent/boot", "boot")} busy={busy === "boot"} icon={Power}>
                      Run First Light
                    </Btn>
                  </div>
                </div>
              </div>
            )}

            {/* Agent-authored state: written by the agent itself (DIRECTIVE.md / PRIORITIES.md
                via its construct skills), never hardcoded placeholders. */}
            {status?.initialised && (
              <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-2">
                <AuthoredCard title="Current directive" icon={Target} body={construct["DIRECTIVE.md"]} empty="No directive yet." />
                <AuthoredCard title="Priorities" icon={ListChecks} body={summarise(construct["PRIORITIES.md"])} empty="No priorities yet." />
                <AuthoredCard title="Exposure" icon={Activity} body={summarise(construct["EXPOSURE.md"])} empty="No exposure data yet." />
              </div>
            )}

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

            <Panel title="Heartbeat schedule" icon={Clock}>
              {heartbeats.length === 0 && <Empty>No heartbeats scheduled. The agent writes these for itself once it is running.</Empty>}
              {heartbeats.map((h) => (
                <div key={h.id} className="border-b border-surface-3 py-2 last:border-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-white">{h.session_type}</span>
                    <span className={clsx("font-mono text-xs", STATUS_COLORS[h.status] ?? "text-muted")}>{h.status}</span>
                  </div>
                  <p className="truncate text-xs text-muted">{h.reason}</p>
                  <p className="font-mono text-[10px] text-muted/70">{fmt(h.fire_at)}</p>
                </div>
              ))}
            </Panel>
          </div>
        )}

        {/* TAB: ACTIVITY */}
        {activeTab === "activity" && (
          <div>
            {/* Guidance injection */}
            <div className="mb-5 rounded-xl border border-border bg-surface-1 p-4">
              <div className="mb-3 flex items-center gap-2">
                <MessageSquare size={14} className="text-blue-400" />
                <h2 className="font-mono text-sm font-semibold text-white">Guidance</h2>
                {pendingGuidance.length > 0 && (
                  <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                    {pendingGuidance.length} pending
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <textarea
                  value={guidanceInput}
                  onChange={(e) => setGuidanceInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && e.metaKey && submitGuidance()}
                  placeholder="Inject guidance into the agent's next session... (Cmd+Enter to submit)"
                  rows={2}
                  className="flex-1 resize-none rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-white placeholder-muted outline-none focus:border-blue-500/50"
                />
                <button
                  onClick={submitGuidance}
                  disabled={guidanceBusy || !guidanceInput.trim()}
                  className="flex items-center gap-1.5 self-start rounded-lg border border-border px-3 py-2 text-xs text-muted hover:border-blue-500 hover:text-white transition-colors disabled:opacity-40"
                >
                  {guidanceBusy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                  Add
                </button>
              </div>

              {guidance.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {pendingGuidance.map((g) => (
                    <div key={g.id} className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2">
                      <p className="flex-1 text-xs text-white">{g.text}</p>
                      <span className="flex-shrink-0 font-mono text-[10px] text-amber-400">pending</span>
                      <button
                        onClick={() => deleteGuidance(g.id)}
                        className="flex-shrink-0 text-muted hover:text-red-400 transition-colors"
                        title="Delete guidance"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                  {guidance.filter((g) => g.consumed).map((g) => (
                    <div key={g.id} className="flex items-start gap-2 rounded-lg border border-surface-3 bg-surface-0/50 px-3 py-2 opacity-50">
                      <p className="flex-1 text-xs text-muted line-through">{g.text}</p>
                      <span className="flex-shrink-0 font-mono text-[10px] text-muted">consumed</span>
                    </div>
                  ))}
                </div>
              )}
              {guidance.length === 0 && (
                <p className="mt-2 text-[11px] text-muted/60">
                  No guidance yet. Add a note above and it will be injected into the agent's next session.
                </p>
              )}
            </div>

            {/* Session log */}
            <Panel title="Session log" icon={Activity}>
              {sessions.length === 0 && <Empty>No sessions yet.</Empty>}
              {sessions.map((s) => {
                const isNew = s.started_at && new Date(s.started_at) > lastViewedAt;
                const isExpanded = expandedSession === s.id;
                const detail = sessionDetails[s.id];
                return (
                  <div key={s.id} className="border-b border-surface-3 last:border-0">
                    <button
                      onClick={() => toggleSession(s.id)}
                      className="flex w-full items-start gap-2 py-3 text-left hover:bg-surface-2/30 rounded transition-colors px-1"
                    >
                      {isExpanded
                        ? <ChevronDown size={13} className="mt-0.5 flex-shrink-0 text-muted" />
                        : <ChevronRight size={13} className="mt-0.5 flex-shrink-0 text-muted" />
                      }
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {s.directive?.session_type && (
                            <span className={clsx("rounded px-1.5 py-0.5 font-mono text-[9px]",
                              SESSION_TYPE_COLORS[s.directive.session_type] ?? "bg-surface-4 text-muted")}>
                              {s.directive.session_type}
                            </span>
                          )}
                          {isNew && (
                            <span className="rounded-full bg-blue-500 px-1.5 py-0.5 font-mono text-[9px] font-bold text-white">
                              NEW
                            </span>
                          )}
                          <span className="font-mono text-[10px] text-muted/70">{fmt(s.started_at)}</span>
                          {s.bets_placed > 0 && <Pill color="green">{s.bets_placed} bet{s.bets_placed !== 1 ? "s" : ""}</Pill>}
                          {s.research_calls > 0 && <Pill color="blue">{s.research_calls} research</Pill>}
                        </div>
                        {s.outcome_summary && (
                          <p className="mt-1 text-xs text-muted">{s.outcome_summary}</p>
                        )}
                      </div>
                      {loadingSession === s.id && <Loader2 size={13} className="animate-spin flex-shrink-0 text-muted" />}
                    </button>

                    {isExpanded && (
                      <div className="mb-3 ml-5 space-y-3 rounded-xl border border-border bg-surface-0/60 p-4">
                        {!detail && loadingSession === s.id && (
                          <p className="text-xs text-muted">Loading details...</p>
                        )}
                        {detail && (
                          <>
                            {/* Trigger context */}
                            {detail.heartbeat && (
                              <Section title="Trigger">
                                <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs space-y-1">
                                  <KV k="type" v={detail.heartbeat.session_type} />
                                  <KV k="reason" v={detail.heartbeat.reason} />
                                  {detail.heartbeat.context && Object.keys(detail.heartbeat.context).length > 0 && (
                                    <div className="mt-2">
                                      <p className="mb-1 text-[10px] text-muted/60 uppercase tracking-wider">Context blob</p>
                                      {Object.entries(detail.heartbeat.context).map(([k, v]) => (
                                        <KV key={k} k={k} v={String(v)} />
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </Section>
                            )}

                            {/* Directive */}
                            {detail.directive && (
                              <Section title="Directive">
                                <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs space-y-1">
                                  {Object.entries(detail.directive).filter(([, v]) => v).map(([k, v]) => (
                                    <KV key={k} k={k} v={String(v)} />
                                  ))}
                                </div>
                              </Section>
                            )}

                            {/* Observations */}
                            {detail.observations.length > 0 && (
                              <Section title={`Observations (${detail.observations.length})`}>
                                <div className="space-y-1.5">
                                  {detail.observations.map((o) => (
                                    <div key={o.id} className="rounded-lg border border-border bg-surface-2 p-3 text-xs">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className={clsx("rounded px-1.5 py-0.5 font-mono text-[9px]",
                                          o.action_type === "BET" ? "bg-green-500/20 text-green-300"
                                          : o.action_type === "PASS" ? "bg-surface-4 text-muted"
                                          : "bg-blue-500/20 text-blue-300")}>
                                          {o.action_type}
                                        </span>
                                        {o.predicted_probability != null && (
                                          <span className="text-muted">
                                            est. <span className="text-white">{(o.predicted_probability * 100).toFixed(0)}%</span>
                                          </span>
                                        )}
                                        {o.market_price_at_action != null && (
                                          <span className="text-muted">
                                            mkt <span className="text-white">{(o.market_price_at_action * 100).toFixed(0)}%</span>
                                          </span>
                                        )}
                                        <span className="ml-auto font-mono text-[10px] text-muted/60">{fmt(o.logged_at)}</span>
                                      </div>
                                      {o.action_detail && typeof o.action_detail === "object" && Boolean((o.action_detail as Record<string, unknown>).market_title) && (
                                        <p className="mb-1 text-white">{String((o.action_detail as Record<string, unknown>).market_title)}</p>
                                      )}
                                      {o.rationale && <p className="text-muted">{o.rationale}</p>}
                                    </div>
                                  ))}
                                </div>
                              </Section>
                            )}

                            {/* Positions opened */}
                            {detail.positions_opened.length > 0 && (
                              <Section title={`Positions opened (${detail.positions_opened.length})`}>
                                <div className="space-y-1.5">
                                  {detail.positions_opened.map((p) => (
                                    <div key={p.id} className="rounded-lg border border-border bg-surface-2 p-3 text-xs">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className={clsx("font-mono text-[10px]",
                                          p.direction === "YES" ? "text-green-400" : "text-red-400")}>
                                          {p.direction}
                                        </span>
                                        <span className="font-mono text-white">${p.size_usdc.toFixed(2)}</span>
                                        <span className="text-muted">@ {(p.entry_price * 100).toFixed(0)}%</span>
                                        <span className={clsx("ml-auto font-mono text-[10px]",
                                          p.status === "OPEN" ? "text-blue-400" : p.pnl != null && p.pnl >= 0 ? "text-green-400" : "text-red-400")}>
                                          {p.status}{p.pnl != null ? ` · ${p.pnl >= 0 ? "+" : ""}$${p.pnl.toFixed(2)}` : ""}
                                        </span>
                                      </div>
                                      <p className="text-muted">{p.market_title}</p>
                                    </div>
                                  ))}
                                </div>
                              </Section>
                            )}

                            {/* Spawned heartbeats */}
                            {detail.heartbeats_spawned.length > 0 && (
                              <Section title={`Heartbeats scheduled (${detail.heartbeats_spawned.length})`}>
                                <div className="space-y-1">
                                  {detail.heartbeats_spawned.map((h) => (
                                    <div key={h.id} className="flex items-center gap-2 text-xs">
                                      <ArrowRight size={11} className="flex-shrink-0 text-muted" />
                                      <span className={clsx("font-mono text-[9px] rounded px-1.5 py-0.5",
                                        SESSION_TYPE_COLORS[h.session_type] ?? "bg-surface-4 text-muted")}>
                                        {h.session_type}
                                      </span>
                                      <span className="flex-1 truncate text-muted">{h.reason}</span>
                                      <span className="flex-shrink-0 font-mono text-[10px] text-muted/60">{fmt(h.fire_at)}</span>
                                      <span className={clsx("flex-shrink-0 font-mono text-[10px]", STATUS_COLORS[h.status] ?? "text-muted")}>{h.status}</span>
                                    </div>
                                  ))}
                                </div>
                              </Section>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </Panel>
          </div>
        )}

        {/* TAB: CONSTRUCT */}
        {activeTab === "construct" && (
          <div className="space-y-4">
            {Object.keys(construct).length === 0 && (
              <Empty>Mental construct not yet initialised. Run First Light on the Overview tab.</Empty>
            )}
            {Object.entries(construct).map(([filename, content]) => (
              <div key={filename} className="rounded-xl border border-border bg-surface-1">
                <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                  <GitBranch size={13} className="text-blue-400" />
                  <span className="font-mono text-xs font-semibold text-white">{filename}</span>
                </div>
                <div className="max-h-80 overflow-y-auto px-4 py-3">
                  {content ? (
                    <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted">
                      {content}
                    </pre>
                  ) : (
                    <p className="text-xs text-muted/60 italic">Empty</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB: SKILLS */}
        {activeTab === "skills" && (
          <div className="space-y-2">
            {skills.length === 0 && <Empty>No skills registered.</Empty>}
            {skills.map((s) => (
              <div key={s.name} className="rounded-xl border border-border bg-surface-1 overflow-hidden">
                <button
                  onClick={() => toggleSkill(s.name)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2/30 transition-colors"
                >
                  <span className={clsx("h-2 w-2 flex-shrink-0 rounded-full",
                    s.available ? "bg-green-400" : "bg-surface-4")} />
                  <div className="min-w-0 flex-1">
                    <span className={clsx("font-mono text-sm",
                      s.available ? "text-blue-300" : "text-muted line-through")}>{s.name}</span>
                    <p className="truncate text-xs text-muted">{s.description}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className="font-mono text-[10px] text-muted">{s.cost}</span>
                    {loadingSkillDoc === s.name
                      ? <Loader2 size={13} className="animate-spin text-muted" />
                      : expandedSkill === s.name
                        ? <ChevronDown size={13} className="text-muted" />
                        : <ChevronRight size={13} className="text-muted" />
                    }
                  </div>
                </button>
                {expandedSkill === s.name && (
                  <div className="border-t border-border bg-surface-0/50 px-4 py-3">
                    {skillDocs[s.name] ? (
                      <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted">
                        {skillDocs[s.name]}
                      </pre>
                    ) : (
                      <p className="text-xs text-muted italic">No documentation available.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}

// -- Sub-components ----------------------------------------------------------

function Tab({
  id, active, onClick, icon: Icon, children, badge,
}: {
  id: TabId; active: TabId; onClick: (id: TabId) => void;
  icon: typeof Activity; children: React.ReactNode; badge?: number;
}) {
  const isActive = active === id;
  return (
    <button
      onClick={() => onClick(id)}
      className={clsx(
        "flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-medium transition-colors",
        isActive
          ? "border-blue-400 text-white"
          : "border-transparent text-muted hover:text-white hover:border-surface-4"
      )}
    >
      <Icon size={13} />
      {children}
      {badge != null && badge > 0 && (
        <span className="rounded-full bg-blue-500 px-1.5 py-0.5 text-[9px] font-bold text-white leading-none">
          {badge}
        </span>
      )}
    </button>
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

function AuthoredCard({
  title, icon: Icon, body, empty,
}: {
  title: string; icon: typeof Activity; body: string | undefined; empty: string;
}) {
  const content = (body || "").trim();
  return (
    <div className="rounded-xl border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon size={13} className="text-blue-400" />
        <span className="font-mono text-xs font-semibold text-white">{title}</span>
        <span className="ml-auto text-[10px] text-muted/60">agent-written</span>
      </div>
      {content ? (
        <pre className="max-h-44 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted">
          {content}
        </pre>
      ) : (
        <p className="text-xs italic text-muted/60">{empty}</p>
      )}
    </div>
  );
}

// Pull the "## Current Summary" section out of a construct doc, else truncate.
function summarise(md: string | undefined): string {
  if (!md) return "";
  const m = md.match(/##\s*Current Summary\s*([\s\S]*?)(?:\n##\s|\n#\s|$)/i);
  if (m) return m[1].trim();
  return md.length > 500 ? md.slice(0, 500) + "\n…" : md;
}

function Panel({ title, icon: Icon, children }: { title: string; icon: typeof Clock; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon size={14} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="max-h-[600px] overflow-y-auto">{children}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-4 text-center text-xs text-muted">{children}</p>;
}

function Pill({ children, color }: { children: React.ReactNode; color: "green" | "blue" | "purple" }) {
  return (
    <span className={clsx(
      "rounded px-1.5 py-0.5 font-mono text-[9px]",
      color === "green" ? "bg-green-500/15 text-green-400"
        : color === "blue" ? "bg-blue-500/15 text-blue-400"
        : "bg-purple-500/15 text-purple-400"
    )}>
      {children}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-muted/70">{title}</p>
      {children}
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2 text-[11px]">
      <span className="w-28 flex-shrink-0 text-muted/70">{k}</span>
      <span className="text-white break-all">{v}</span>
    </div>
  );
}

// -- Helpers -----------------------------------------------------------------

function fmt(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

