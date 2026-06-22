import { useCallback, useEffect, useRef, useState } from "react";
import type { WsEvent } from "../types";

type Status = "disconnected" | "connecting" | "connected" | "error";

export function useWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<Status>("disconnected");
  const listeners = useRef<Set<(e: WsEvent) => void>>(new Set());

  const connect = useCallback(() => {
    if (!sessionId) return;
    if (ws.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const url = `ws://${window.location.host}/api/chat/sessions/${sessionId}/ws`;
    const socket = new WebSocket(url);

    socket.onopen = () => setStatus("connected");
    socket.onclose = () => setStatus("disconnected");
    socket.onerror = () => setStatus("error");
    socket.onmessage = (ev) => {
      try {
        const event: WsEvent = JSON.parse(ev.data);
        listeners.current.forEach((fn) => fn(event));
      } catch {
        // malformed frame — ignore
      }
    };

    ws.current = socket;
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      ws.current?.close();
      ws.current = null;
      setStatus("disconnected");
    };
  }, [connect]);

  const send = useCallback((data: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  const subscribe = useCallback((fn: (e: WsEvent) => void) => {
    listeners.current.add(fn);
    return () => listeners.current.delete(fn);
  }, []);

  return { status, send, subscribe, reconnect: connect };
}
