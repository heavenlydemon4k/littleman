import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { MessageItem } from "../components/chat/MessageItem";
import { ChatInput } from "../components/chat/ChatInput";
import { ActivityFeed } from "../components/activity/ActivityFeed";
import { useChat } from "../hooks/useChat";
import { useActivity } from "../hooks/useActivity";
import { Wifi, WifiOff, Loader2, Plus, Bot, ChevronDown, Pencil, Check, X, Play, Circle } from "lucide-react";
import type { ChatMessage } from "../types";
import { parseAsk } from "../lib/elicitation";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { messages, streaming, status, sendMessage, stopStreaming, reconnect } = useChat(sessionId ?? null);

  // The Main session mirrors the agent's autonomous activity, so it carries the live action feed.
  const activity = useActivity(sessionId === "main");

  // Session title
  const [sessionTitle, setSessionTitle] = useState<string>("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!sessionId) { setSessionTitle(""); return; }
    fetch(`/api/chat/sessions/${sessionId}`)
      .then((r) => r.ok ? r.json() : null)
      .then((s) => { if (s) { setSessionTitle(s.title); setTitleInput(s.title); } })
      .catch(console.error);
  }, [sessionId]);

  // Re-fetch title after first message lands (backend auto-sets it from first user message)
  const prevMsgLen = useRef(0);
  useEffect(() => {
    if (!sessionId) return;
    if (messages.length > 0 && prevMsgLen.current === 0) {
      fetch(`/api/chat/sessions/${sessionId}`)
        .then((r) => r.ok ? r.json() : null)
        .then((s) => { if (s) { setSessionTitle(s.title); setTitleInput(s.title); } })
        .catch(console.error);
    }
    prevMsgLen.current = messages.length;
  }, [messages.length, sessionId]);

  const startEditTitle = () => {
    setEditingTitle(true);
    setTitleInput(sessionTitle);
    setTimeout(() => titleRef.current?.select(), 0);
  };

  const saveTitle = async () => {
    if (!sessionId) return;
    setEditingTitle(false);
    const newTitle = titleInput.trim() || sessionTitle;
    setSessionTitle(newTitle);
    await fetch(`/api/chat/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
  };

  const cancelEditTitle = () => {
    setEditingTitle(false);
    setTitleInput(sessionTitle);
  };

  // Scroll to bottom
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const scrollToBottom = (smooth = true) => {
    scrollAreaRef.current?.scrollTo({
      top: scrollAreaRef.current.scrollHeight,
      behavior: smooth ? "smooth" : "instant",
    });
  };

  const handleScroll = () => {
    if (!scrollAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollAreaRef.current;
    setIsAtBottom(scrollHeight - scrollTop - clientHeight < 80);
  };

  useEffect(() => {
    if (isAtBottom) scrollToBottom();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, activity.length]);

  // New conversation
  const createSession = async () => {
    const res = await fetch("/api/chat/sessions", { method: "POST" });
    const session: { id: string } = await res.json();
    navigate(`/chat/${session.id}`);
  };

  // Send + force scroll
  const handleSend = (text: string, opts: { thinking: boolean; skills: boolean }) => {
    sendMessage(text, opts);
    setIsAtBottom(true);
    setTimeout(() => scrollToBottom(false), 50);
  };

  // First Light (compulsory first activation), shown on the empty Main session
  const FL_STEPS = [
    "waking",
    "reading SOUL.md and onboarding answers",
    "gathering bearings",
    "forming first understanding",
  ];
  const [flBusy, setFlBusy] = useState(false);
  const [flStep, setFlStep] = useState(0);
  const [flError, setFlError] = useState("");

  const runFirstLight = async () => {
    setFlBusy(true);
    setFlStep(0);
    setFlError("");
    const timer = setInterval(() => setFlStep((s) => Math.min(s + 1, FL_STEPS.length - 1)), 3500);
    try {
      const r = await fetch("/api/agent/first-light", { method: "POST" });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || body.error || `first light failed (${r.status})`);
      }
      clearInterval(timer);
      // The greeting is now in the Main session; reload to show it as a normal chat.
      window.location.reload();
    } catch (e) {
      clearInterval(timer);
      setFlBusy(false);
      setFlError(String(e));
    }
  };

  const isEmpty = messages.length === 0 && !streaming;
  const isMain = sessionId === "main";

  // An unanswered LLM question morphs the composer into a card. Active only when the very last
  // message is an assistant turn carrying an ```ask block (a following user message clears it).
  const last = messages[messages.length - 1];
  const activeElicitation =
    !streaming && last && last.role === "assistant"
      ? parseAsk(last.content).ask
      : null;

  // Empty state
  if (!sessionId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-5">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-surface-2">
            <Bot size={26} className="text-blue-400" />
          </div>
          <div>
            <p className="font-mono text-sm font-semibold text-white">No conversation open</p>
            <p className="mt-1 text-xs text-muted">
              Talk to littleman directly -- ask about markets, request research, or explore positions.
            </p>
          </div>
        </div>
        <button
          onClick={createSession}
          className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted hover:border-blue-500 hover:text-white transition-colors"
        >
          <Plus size={14} />
          New conversation
        </button>
      </div>
    );
  }

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5 gap-3">
        {/* Title / inline rename */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {editingTitle ? (
            <>
              <input
                ref={titleRef}
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveTitle();
                  if (e.key === "Escape") cancelEditTitle();
                }}
                onBlur={saveTitle}
                className="flex-1 min-w-0 rounded border border-blue-500/50 bg-surface-2 px-2 py-0.5 text-sm text-white outline-none"
              />
              <button onClick={saveTitle} className="text-green-400 hover:text-green-300">
                <Check size={14} />
              </button>
              <button onClick={cancelEditTitle} className="text-muted hover:text-white">
                <X size={14} />
              </button>
            </>
          ) : (
            <button
              onClick={startEditTitle}
              title="Click to rename"
              className="group flex min-w-0 items-center gap-1.5 rounded px-1 py-0.5 hover:bg-surface-2 transition-colors"
            >
              <span className="truncate text-sm text-white">
                {sessionTitle || sessionId.slice(0, 8)}
              </span>
              <Pencil size={11} className="flex-shrink-0 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          )}
        </div>

        {/* WS status */}
        <div className="flex flex-shrink-0 items-center gap-1.5">
          {status === "connected" && <Wifi size={12} className="text-green-400" />}
          {status === "disconnected" && (
            <button
              onClick={reconnect}
              className="flex items-center gap-1 text-xs text-muted hover:text-white"
              title="Reconnect"
            >
              <WifiOff size={12} className="text-red-400" />
              reconnect
            </button>
          )}
          {status === "connecting" && <Loader2 size={12} className="animate-spin text-muted" />}
          {status === "error" && <WifiOff size={12} className="text-red-400" />}
          <span className={clsx("text-xs", {
            "text-green-400": status === "connected",
            "text-red-400": status === "error" || status === "disconnected",
            "text-muted": status === "connecting",
          })}>
            {status}
          </span>
        </div>
      </div>

      {/* Message list */}
      <div
        ref={scrollAreaRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto py-4"
      >
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
            {/* Bare brand */}
            <div className="flex items-center gap-2">
              <Bot size={22} className="text-blue-400" />
              <span className="font-mono text-lg font-semibold text-white">littleman</span>
            </div>

            {isMain ? (
              /* First Light: a button, not a text field */
              <div className="flex flex-col items-center gap-4">
                <p className="text-xs text-muted">first activation, let the agent gather its bearings</p>
                {!flBusy ? (
                  <button
                    onClick={runFirstLight}
                    className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm text-white hover:bg-blue-700 transition-colors"
                  >
                    <Play size={16} /> Begin onboarding
                  </button>
                ) : (
                  <div className="flex w-72 flex-col gap-2">
                    {FL_STEPS.map((s, i) => (
                      <div key={s} className="flex items-center gap-2 text-xs">
                        {i < flStep ? (
                          <Check size={14} className="text-green-400" />
                        ) : i === flStep ? (
                          <Loader2 size={14} className="animate-spin text-blue-400" />
                        ) : (
                          <Circle size={14} className="text-muted" />
                        )}
                        <span className={i <= flStep ? "text-white" : "text-muted"}>{s}</span>
                      </div>
                    ))}
                  </div>
                )}
                {flError && <p className="text-xs text-red-400">{flError}</p>}
              </div>
            ) : (
              /* Regular empty session: centered composer */
              <div className="w-full max-w-2xl">
                <ChatInput
                  onSend={handleSend}
                  onStop={stopStreaming}
                  streaming={streaming}
                  disabled={status !== "connected"}
                  sessionId={sessionId}
                  centered
                />
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map((m) => (
              <MessageItem key={m.id} message={m as ChatMessage & { _streaming?: boolean }} />
            ))}
            {isMain && <ActivityFeed events={activity} />}
          </>
        )}
      </div>

      {/* Scroll-to-bottom button */}
      {!isAtBottom && (
        <div className="pointer-events-none absolute inset-x-0 bottom-28 flex justify-center">
          <button
            onClick={() => { setIsAtBottom(true); scrollToBottom(); }}
            className="pointer-events-auto flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-3 py-1.5 text-xs text-muted shadow-lg hover:border-blue-500 hover:text-white transition-colors"
          >
            <ChevronDown size={13} />
            Scroll to bottom
          </button>
        </div>
      )}

      {/* Bottom composer once the conversation has started (empty state owns the centered one) */}
      {!isEmpty && (
        <ChatInput
          onSend={handleSend}
          onStop={stopStreaming}
          streaming={streaming}
          disabled={status !== "connected"}
          sessionId={sessionId}
          elicitation={activeElicitation}
        />
      )}
    </div>
  );
}
