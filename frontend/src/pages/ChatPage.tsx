import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import clsx from "clsx";
import { MessageItem } from "../components/chat/MessageItem";
import { ChatInput } from "../components/chat/ChatInput";
import { useChat } from "../hooks/useChat";
import { Wifi, WifiOff, Loader2 } from "lucide-react";
import type { ChatMessage } from "../types";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { messages, streaming, status, sendMessage, reconnect } = useChat(sessionId ?? null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!sessionId) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-muted">Select a conversation or start a new one</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Status bar */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-xs text-muted font-mono">session: {sessionId.slice(0, 8)}</span>
        <div className="flex items-center gap-1.5">
          {status === "connected" && <Wifi size={12} className="text-green-400" />}
          {status === "disconnected" && (
            <button onClick={reconnect} className="flex items-center gap-1 text-xs text-muted hover:text-white">
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 && !streaming && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted">Send a message to start</p>
          </div>
        )}
        {messages.map((m) => (
          <MessageItem
            key={m.id}
            message={m as ChatMessage & { _streaming?: boolean }}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      <ChatInput
        onSend={sendMessage}
        streaming={streaming}
        disabled={status !== "connected"}
      />
    </div>
  );
}
