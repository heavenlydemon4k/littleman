import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
  Wrench,
} from "lucide-react";
import type { AgentEvent } from "../../types";
import { Island } from "../ui/Island";

/** One executed (or in-flight) tool action, with the reasoning that led to it. */
interface ActionRow {
  kind: "action";
  key: string;
  name: string;
  cost?: string;
  args?: string;
  reasoning?: string;
  done: boolean;
  ok?: boolean;
  summary?: string;
  error?: string;
}
interface StageRow {
  kind: "stage";
  key: string;
  label: string;
}
interface NoteRow {
  kind: "note";
  key: string;
  text: string;
}
type Row = ActionRow | StageRow | NoteRow;

interface WakeGroup {
  sessionId: string;
  trigger?: string;
  sessionType?: string;
  reason?: string;
  done: boolean;
  doneSummary?: string;
  rows: Row[];
}

const str = (v: unknown): string | undefined =>
  typeof v === "string" ? v : v === undefined || v === null ? undefined : String(v);

/** Fold the flat event stream into per-wake groups of renderable rows. */
function buildGroups(events: AgentEvent[]): WakeGroup[] {
  const groups = new Map<string, WakeGroup>();
  const order: string[] = [];
  // Reasoning seen since the last action — attributed to the next tool call.
  const pendingReasoning = new Map<string, string[]>();

  const groupFor = (sid: string): WakeGroup => {
    let g = groups.get(sid);
    if (!g) {
      g = { sessionId: sid, done: false, rows: [] };
      groups.set(sid, g);
      order.push(sid);
      pendingReasoning.set(sid, []);
    }
    return g;
  };

  for (const e of events) {
    const g = groupFor(e.agent_session_id);
    const p = e.payload || {};
    switch (e.type) {
      case "session_start":
        g.trigger = str(p.trigger);
        g.sessionType = str(p.session_type);
        g.reason = str(p.reason);
        break;
      case "stage":
        g.rows.push({ kind: "stage", key: e.id, label: str(p.label) || str(p.stage) || "stage" });
        break;
      case "reasoning": {
        const t = str(p.text);
        if (t) pendingReasoning.get(e.agent_session_id)!.push(t);
        break;
      }
      case "tool_call": {
        const buffered = pendingReasoning.get(e.agent_session_id)!;
        g.rows.push({
          kind: "action",
          key: e.id,
          name: str(p.name) || "tool",
          cost: str(p.cost),
          args: str(p.args),
          reasoning: buffered.length ? buffered.join("\n\n") : undefined,
          done: false,
        });
        pendingReasoning.set(e.agent_session_id, []);
        break;
      }
      case "tool_result": {
        // Attach to the most recent unfinished action of the same name.
        const name = str(p.name);
        for (let i = g.rows.length - 1; i >= 0; i--) {
          const r = g.rows[i];
          if (r.kind === "action" && !r.done && r.name === name) {
            r.done = true;
            r.ok = p.ok === true;
            r.summary = str(p.summary);
            r.error = str(p.error);
            break;
          }
        }
        break;
      }
      case "session_done":
        g.done = true;
        g.doneSummary = str(p.summary);
        break;
    }
  }

  // Any trailing reasoning with no following tool call → standalone note.
  for (const sid of order) {
    const buffered = pendingReasoning.get(sid)!;
    if (buffered.length) {
      groups.get(sid)!.rows.push({ kind: "note", key: `${sid}-note`, text: buffered.join("\n\n") });
    }
  }

  return order.map((sid) => groups.get(sid)!);
}

function ActionItem({ row }: { row: ActionRow }) {
  const [open, setOpen] = useState(false);
  const expandable = !!(row.reasoning || row.args || row.summary || row.error);
  return (
    <Island surface={1}>
      <button
        onClick={() => expandable && setOpen((v) => !v)}
        className={clsx(
          "flex w-full items-center gap-2 px-3 py-2 text-left",
          expandable && "hover:bg-surface-2 transition-colors"
        )}
      >
        {!row.done ? (
          <Loader2 size={13} className="flex-shrink-0 animate-spin text-blue-400" />
        ) : row.ok ? (
          <CheckCircle2 size={13} className="flex-shrink-0 text-green-400" />
        ) : (
          <XCircle size={13} className="flex-shrink-0 text-red-400" />
        )}
        <Wrench size={11} className="flex-shrink-0 text-muted" />
        <span className="font-mono text-xs text-white">{row.name}</span>
        {row.cost && row.cost !== "LOW" && (
          <span className="rounded bg-surface-3 px-1 text-[10px] text-muted">{row.cost}</span>
        )}
        <span className="ml-auto flex items-center gap-1 text-[10px] text-muted">
          {!row.done ? "working…" : row.ok ? "done" : "failed"}
          {expandable && (
            <ChevronRight
              size={13}
              className={clsx("transition-transform", open && "rotate-90")}
            />
          )}
        </span>
      </button>
      {open && expandable && (
        <div className="space-y-2 border-t border-border px-3 py-2 text-xs">
          {row.reasoning && (
            <div>
              <p className="mb-0.5 text-[10px] uppercase tracking-wide text-muted">reasoning</p>
              <p className="whitespace-pre-wrap italic text-gray-300">{row.reasoning}</p>
            </div>
          )}
          {row.args && row.args !== "{}" && (
            <div>
              <p className="mb-0.5 text-[10px] uppercase tracking-wide text-muted">input</p>
              <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11px] text-gray-300">
                {row.args}
              </pre>
            </div>
          )}
          {(row.summary || row.error) && (
            <div>
              <p className="mb-0.5 text-[10px] uppercase tracking-wide text-muted">result</p>
              <pre
                className={clsx(
                  "overflow-x-auto whitespace-pre-wrap font-mono text-[11px]",
                  row.error ? "text-red-300" : "text-gray-300"
                )}
              >
                {row.error || row.summary}
              </pre>
            </div>
          )}
        </div>
      )}
    </Island>
  );
}

export function ActivityFeed({ events }: { events: AgentEvent[] }) {
  const groups = useMemo(() => buildGroups(events), [events]);
  if (groups.length === 0) return null;

  // Oldest wake first so the active (latest) one sits at the bottom, where the view scrolls.
  return (
    <div className="mx-auto mb-4 max-w-3xl space-y-3 px-4">
      {groups.map((g) => (
        <Island key={g.sessionId} floating className="p-3">
          <div className="mb-2 flex items-center gap-2">
            {g.done ? (
              <Activity size={13} className="text-muted" />
            ) : (
              <Loader2 size={13} className="animate-spin text-blue-400" />
            )}
            <span className="font-mono text-xs font-semibold text-white">
              {g.sessionType || "wake"}
            </span>
            <span className="text-[10px] text-muted">{g.trigger || ""}</span>
            <span className="ml-auto text-[10px] text-muted">
              {g.done ? "complete" : "active"}
            </span>
          </div>
          {g.reason && <p className="mb-2 text-[11px] text-muted">{g.reason}</p>}

          <div className="space-y-1.5">
            {g.rows.map((r) =>
              r.kind === "action" ? (
                <ActionItem key={r.key} row={r} />
              ) : r.kind === "stage" ? (
                <div key={r.key} className="flex items-center gap-2 py-0.5">
                  <span className="h-px flex-1 bg-border" />
                  <span className="text-[10px] uppercase tracking-wide text-muted">{r.label}</span>
                  <span className="h-px flex-1 bg-border" />
                </div>
              ) : (
                <p key={r.key} className="whitespace-pre-wrap px-1 text-[11px] italic text-gray-300">
                  {r.text}
                </p>
              )
            )}
          </div>

          {g.done && g.doneSummary && (
            <p className="mt-2 border-t border-border pt-2 text-[11px] text-gray-300">
              {g.doneSummary}
            </p>
          )}
        </Island>
      ))}
    </div>
  );
}
