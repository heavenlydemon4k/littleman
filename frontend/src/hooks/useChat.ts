import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, ToolCall } from "../types";
import { useWebSocket } from "./useWebSocket";

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const streamBuffer = useRef<{
    id: string;
    content: string;
    thinking: string;
    tool_calls: ToolCall[];
  } | null>(null);

  const { status, send, subscribe, reconnect } = useWebSocket(sessionId);

  // Load history when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    fetch(`/api/chat/sessions/${sessionId}/messages`)
      .then((r) => r.json())
      .then((msgs: ChatMessage[]) => setMessages(msgs))
      .catch(console.error);
  }, [sessionId]);

  // Handle incoming WS events
  useEffect(() => {
    return subscribe((event) => {
      switch (event.type) {
        case "user_message":
          setMessages((prev) => [...prev, event.message]);
          break;

        case "assistant_start":
          streamBuffer.current = {
            id: event.id,
            content: "",
            thinking: "",
            tool_calls: [],
          };
          setStreaming(true);
          // Insert a placeholder assistant message
          setMessages((prev) => [
            ...prev,
            {
              id: event.id,
              session_id: sessionId ?? "",
              role: "assistant",
              content: null,
              thinking: null,
              tool_calls: null,
              tool_call_id: null,
              tool_name: null,
              created_at: new Date().toISOString(),
              _streaming: true,
            } as ChatMessage & { _streaming: boolean },
          ]);
          break;

        case "token":
          if (streamBuffer.current) {
            streamBuffer.current.content += event.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamBuffer.current?.id
                  ? { ...m, content: streamBuffer.current.content }
                  : m
              )
            );
          }
          break;

        case "thinking":
          if (streamBuffer.current) {
            streamBuffer.current.thinking += event.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamBuffer.current?.id
                  ? { ...m, thinking: streamBuffer.current.thinking }
                  : m
              )
            );
          }
          break;

        case "tool_call":
          if (streamBuffer.current) {
            streamBuffer.current.tool_calls.push(event.call);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamBuffer.current?.id
                  ? { ...m, tool_calls: [...(streamBuffer.current?.tool_calls ?? [])] }
                  : m
              )
            );
          }
          break;

        case "assistant_done":
          setStreaming(false);
          streamBuffer.current = null;
          break;

        case "error":
          setStreaming(false);
          streamBuffer.current = null;
          break;
      }
    });
  }, [subscribe, sessionId]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || streaming) return;
      send({ type: "user_message", content });
    },
    [send, streaming]
  );

  return { messages, streaming, status, sendMessage, reconnect };
}
