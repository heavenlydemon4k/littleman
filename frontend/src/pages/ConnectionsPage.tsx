import { useCallback, useEffect, useState } from "react";
import { Plug, Cpu, Search, Wallet, RefreshCw, Loader2 } from "lucide-react";
import clsx from "clsx";

interface Conn { ok: boolean; detail: string }

interface Status {
  wallet_balance_usdc: number;
  available_balance_usdc: number;
  open_positions: number;
  open_exposure_usdc: number;
  balance_is_simulated: boolean;
  last_reconcile_at: string | null;
  connections: { llm: Conn; polymarket_wallet: Conn; search: Conn };
}

interface Runtime {
  mode: string;
  primary_model: string;
  secondary_model: string;
  api_key_set: boolean;
}

interface Position {
  id: string;
  market_title: string;
  direction: string;
  size_usdc: number;
  entry_price: number;
  status: string;
  pnl: number | null;
}

// Connections are the platform's integrations. New plugins/connectors register here; each
// reports live status pulled from the API. The Polymarket reference application's wallet detail
// lives here, off the (domain-agnostic) agent dashboard.
export function ConnectionsPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, rt, pos] = await Promise.all([
        fetch("/api/agent/status").then((r) => r.json()),
        fetch("/api/settings/runtime").then((r) => r.json()),
        fetch("/api/agent/positions").then((r) => r.json()),
      ]);
      setStatus(s);
      setRuntime(rt);
      setPositions(Array.isArray(pos) ? pos : []);
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const reconcile = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await fetch("/api/agent/reconcile", { method: "POST" }).then((x) => x.json());
      setMsg(r.reconciled ? `Reconciled: $${r.pusd_balance} pUSD, ${r.positions_count} positions` : (r.reason || "reconcile failed"));
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-1 flex items-center gap-2">
          <Plug size={18} className="text-blue-400" />
          <h1 className="font-mono text-lg font-semibold text-white">Connections</h1>
        </div>
        <p className="mb-6 text-sm text-muted">
          Integrations the agent can use. Each shows live status; configure credentials in Settings.
        </p>

        {/* LLM */}
        <ConnCard
          icon={Cpu}
          title="Language model"
          conn={status?.connections.llm}
        >
          {runtime && (
            <div className="space-y-1 text-xs text-muted">
              <Row k="Primary" v={runtime.primary_model} />
              <Row k="Secondary" v={runtime.secondary_model} />
              <Row k="Mode" v={runtime.mode} />
              <Row k="API key" v={runtime.api_key_set ? "set" : "not set"} />
            </div>
          )}
        </ConnCard>

        {/* Web search */}
        <ConnCard icon={Search} title="Web search" conn={status?.connections.search}>
          <p className="text-xs text-muted">{status?.connections.search.detail}</p>
        </ConnCard>

        {/* Polymarket wallet (reference application) */}
        <ConnCard icon={Wallet} title="Polymarket wallet" conn={status?.connections.polymarket_wallet}>
          {status && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <Metric label={status.balance_is_simulated ? "Balance (sim)" : "Balance"} value={`$${status.wallet_balance_usdc.toFixed(2)}`} />
                <Metric label="Available" value={`$${status.available_balance_usdc.toFixed(2)}`} />
                <Metric label="Open positions" value={String(status.open_positions)} />
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={reconcile}
                  disabled={busy}
                  className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:border-blue-500 hover:text-white transition-colors disabled:opacity-50"
                >
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                  Reconcile from chain
                </button>
                {status.last_reconcile_at && (
                  <span className="text-[11px] text-muted/70">last: {fmt(status.last_reconcile_at)}</span>
                )}
                {msg && <span className="text-[11px] text-muted">{msg}</span>}
              </div>

              {positions.length > 0 && (
                <div className="mt-2 overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-xs">
                    <thead className="border-b border-border bg-surface-2 text-muted">
                      <tr>
                        <th className="px-3 py-1.5 text-left font-mono text-[10px] uppercase">Market</th>
                        <th className="px-3 py-1.5 text-left font-mono text-[10px] uppercase">Dir</th>
                        <th className="px-3 py-1.5 text-right font-mono text-[10px] uppercase">Size</th>
                        <th className="px-3 py-1.5 text-left font-mono text-[10px] uppercase">Status</th>
                        <th className="px-3 py-1.5 text-right font-mono text-[10px] uppercase">P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p) => (
                        <tr key={p.id} className="border-b border-surface-3 last:border-0">
                          <td className="max-w-[260px] truncate px-3 py-2 text-white">{p.market_title}</td>
                          <td className={clsx("px-3 py-2 font-mono", p.direction === "YES" ? "text-green-400" : "text-red-400")}>{p.direction}</td>
                          <td className="px-3 py-2 text-right font-mono text-white">${p.size_usdc.toFixed(2)}</td>
                          <td className="px-3 py-2 font-mono text-muted">{p.status}</td>
                          <td className={clsx("px-3 py-2 text-right font-mono", p.pnl == null ? "text-muted" : p.pnl >= 0 ? "text-green-400" : "text-red-400")}>
                            {p.pnl != null ? `${p.pnl >= 0 ? "+" : ""}$${p.pnl.toFixed(2)}` : "--"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </ConnCard>

        <p className="mt-4 text-[11px] text-muted/60">
          More connectors plug in here. Credentials and models are managed in Settings.
        </p>
      </div>
    </div>
  );
}

function ConnCard({
  icon: Icon, title, conn, children,
}: {
  icon: typeof Cpu; title: string; conn?: Conn; children: React.ReactNode;
}) {
  const ok = conn?.ok;
  return (
    <div className="mb-3 rounded-xl border border-border bg-surface-1 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={16} className="text-blue-400" />
        <h2 className="font-mono text-sm font-semibold text-white">{title}</h2>
        <span className={clsx(
          "ml-auto flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
          ok ? "border-green-500/30 text-green-400" : "border-surface-4 text-muted"
        )}>
          <span className={clsx("h-1.5 w-1.5 rounded-full", ok ? "bg-green-400" : "bg-surface-4")} />
          {ok ? "connected" : "not connected"}
        </span>
      </div>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <span className="w-24 flex-shrink-0 text-muted/70">{k}</span>
      <span className="text-white break-all">{v}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="font-mono text-sm text-white">{value}</p>
    </div>
  );
}

function fmt(iso: string | null): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
