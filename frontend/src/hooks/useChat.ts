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

  const { status, send, subscribe, reconnect, disconnect } = useWebSocket(sessionId);

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

        case "tool_result":
          if (streamBuffer.current) {
            streamBuffer.current.tool_calls = streamBuffer.current.tool_calls.map((tc) =>
              tc.id === event.call_id ? { ...tc, result: event.result } : tc
            );
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamBuffer.current?.id
                  ? {
                      ...m,
                      tool_calls: [...(streamBuffer.current?.tool_calls ?? [])],
                    }
                  : m
              )
            );
          }
          break;

        case "assistant_done":
          setStreaming(false);
          if (streamBuffer.current) {
            const id = streamBuffer.current.id;
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, _streaming: false } : m))
            );
            streamBuffer.current = null;
          }
          break;

        case "error": {
          setStreaming(false);
          // Surface the failure in the bubble rather than dropping it — a turn must never end
          // silently. Show the server's detail, keeping any partial text already streamed.
          const detail = (event as { message?: string }).message || "generation failed";
          const id = streamBuffer.current?.id;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id
                ? {
                    ...m,
                    _streaming: false,
                    content: m.content ? `${m.content}\n\n⚠️ ${detail}` : `⚠️ ${detail}`,
                  }
                : m
            )
          );
          streamBuffer.current = null;
          break;
        }
      }
    });
  }, [subscribe, sessionId]);

  const sendMessage = useCallback(
    (content: string, opts?: { thinking?: boolean; skills?: boolean }) => {
      if (!content.trim() || streaming) return;
      send({
        type: "user_message",
        content,
        thinking: opts?.thinking ?? false,
        skills: opts?.skills ?? true,
      });
    },
    [send, streaming]
  );

  // Stop an in-progress stream: close the socket (killing the server stream),
  // mark the partial message as done, then reconnect for next message.
  const stopStreaming = useCallback(() => {
    disconnect();
    setStreaming(false);
    if (streamBuffer.current) {
      const id = streamBuffer.current.id;
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, _streaming: false } : m))
      );
      streamBuffer.current = null;
    }
    // Re-establish the socket after a tick so it is ready for the next message
    setTimeout(reconnect, 150);
  }, [disconnect, reconnect]);

  return { messages, streaming, status, sendMessage, stopStreaming, reconnect };
}
