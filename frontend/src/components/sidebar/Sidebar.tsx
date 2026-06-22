import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Plus, Trash2, MessageSquare, Settings, FolderOpen, Bot, Activity } from "lucide-react";
import clsx from "clsx";
import type { ChatSession } from "../../types";

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
        <span className="font-mono font-semibold text-white">littleman</span>
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

      {/* New chat */}
      <div className="p-3">
        <button
          onClick={newSession}
          className="flex w-full items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:border-blue-500 hover:text-white transition-colors"
        >
          <Plus size={15} />
          New conversation
        </button>
      </div>

      {/* Session list */}
      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {sessions.length === 0 && (
          <p className="px-3 py-4 text-xs text-muted">No conversations yet</p>
        )}
        {sessions.map((s) => (
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
            <button
              onClick={(e) => deleteSession(e, s.id)}
              className="invisible ml-auto flex-shrink-0 rounded p-0.5 text-muted hover:text-red-400 group-hover:visible"
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
