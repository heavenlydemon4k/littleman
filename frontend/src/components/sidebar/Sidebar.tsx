import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Plus, Trash2, MessageSquare, Settings, FolderOpen, Bot, Activity, Radio } from "lucide-react";
import clsx from "clsx";
import type { ChatSession } from "../../types";

function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return "now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function Sidebar() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const loadSessions = () =>
    fetch("/api/chat/sessions")
      .then((r) => r.json())
      .then(setSessions)
      .catch(console.error);

  useEffect(() => {
    loadSessions();
  }, []);

  const newSession = async () => {
    const res = await fetch("/api/chat/sessions", { method: "POST" });
    const session: { id: string } = await res.json();
    await loadSessions();
    navigate(`/chat/${session.id}`);
  };

  const deleteSession = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    await fetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
    await loadSessions();
    if (sessionId === id) navigate("/");
  };

  return (
    <aside className="flex w-60 flex-shrink-0 flex-col border-r border-border bg-surface-1">
      {/* Logo */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <Bot size={18} className="text-blue-400" />
        <div className="flex flex-col leading-none">
          <span className="font-mono font-semibold text-white">littleman</span>
          <span className="mt-0.5 text-[10px] text-muted">agent platform</span>
        </div>
      </div>

      {/* Agent dashboard link */}
      <div className="px-2 pt-2">
        <Link
          to="/agent"
          className={clsx(
            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
            location.pathname.startsWith("/agent")
              ? "bg-surface-3 text-white"
              : "text-muted hover:bg-surface-2 hover:text-white"
          )}
        >
          <Activity size={15} className="text-blue-400" />
          Agent
        </Link>
      </div>

      {/* Main agent session (pinned) */}
      {sessions.some((s) => s.id === "main") && (
        <div className="px-2 pt-2">
          <Link
            to="/chat/main"
            className={clsx(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
              sessionId === "main"
                ? "bg-surface-3 text-white"
                : "text-muted hover:bg-surface-2 hover:text-white"
            )}
          >
            <Radio size={14} className="flex-shrink-0 text-green-400" />
            <span className="flex-1 truncate">Main agent</span>
            <span className="rounded bg-surface-4 px-1.5 py-0.5 text-[10px] text-muted">auto</span>
          </Link>
        </div>
      )}

      {/* New chat */}
      <div className="px-3 pb-2 pt-2">
        <button
          onClick={newSession}
          className="flex w-full items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:border-blue-500 hover:text-white transition-colors"
        >
          <Plus size={15} />
          New conversation
        </button>
      </div>

      {/* User session list */}
      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {sessions.filter((s) => s.id !== "main").length === 0 && (
          <p className="px-3 py-4 text-xs text-muted">No conversations yet</p>
        )}
        {sessions.filter((s) => s.id !== "main").map((s) => (
          <Link
            key={s.id}
            to={`/chat/${s.id}`}
            className={clsx(
              "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
              sessionId === s.id
                ? "bg-surface-3 text-white"
                : "text-muted hover:bg-surface-2 hover:text-white"
            )}
          >
            <MessageSquare size={14} className="flex-shrink-0" />
            <span className="flex-1 truncate">{s.title}</span>
            <span className="flex-shrink-0 text-[10px] text-muted/60 group-hover:hidden">
              {relTime(s.updated_at)}
            </span>
            <button
              onClick={(e) => deleteSession(e, s.id)}
              className="invisible hidden flex-shrink-0 rounded p-0.5 text-muted hover:text-red-400 group-hover:visible group-hover:block"
            >
              <Trash2 size={13} />
            </button>
          </Link>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="border-t border-border p-2">
        <Link
          to="/workspace"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-white transition-colors"
        >
          <FolderOpen size={15} />
          Workspace
        </Link>
        <Link
          to="/settings"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-white transition-colors"
        >
          <Settings size={15} />
          Settings
        </Link>
      </div>
    </aside>
  );
}
