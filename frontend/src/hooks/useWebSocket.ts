import { useCallback, useEffect, useRef, useState } from "react";
import type { WsEvent } from "../types";

type Status = "disconnected" | "connecting" | "connected" | "error";

// Exponential backoff delays (ms)
const BACKOFF = [1000, 3000, 8000, 20000];

export function useWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<Status>("disconnected");
  const listeners = useRef<Set<(e: WsEvent) => void>>(new Set());
  const attempts = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Flag: true when we intentionally closed — prevents auto-reconnect
  const intentional = useRef(false);

  const clearTimer = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!sessionId) return;
    // Don't open a second socket if one is already open or connecting
    if (
      ws.current &&
      (ws.current.readyState === WebSocket.OPEN ||
        ws.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearTimer();
    intentional.current = false;
    setStatus("connecting");

    const socket = new WebSocket(
      `ws://${window.location.host}/api/chat/sessions/${sessionId}/ws`
    );

    socket.onopen = () => {
      setStatus("connected");
      attempts.current = 0;
    };

    socket.onclose = () => {
      setStatus("disconnected");
      if (!intentional.current) {
        // Schedule reconnect with backoff
        const delay = BACKOFF[Math.min(attempts.current, BACKOFF.length - 1)];
        attempts.current++;
        timer.current = setTimeout(() => {
          timer.current = null;
          connect();
        }, delay);
      }
    };

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
  }, [sessionId, clearTimer]);

  // Intentional close — no auto-reconnect follows
  const disconnect = useCallback(() => {
    intentional.current = true;
    clearTimer();
    ws.current?.close();
    ws.current = null;
    setStatus("disconnected");
  }, [clearTimer]);

  useEffect(() => {
    connect();
    return () => {
      intentional.current = true;
      clearTimer();
      ws.current?.close();
      ws.current = null;
    };
  }, [connect, clearTimer]);

  const send = useCallback((data: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  const subscribe = useCallback((fn: (e: WsEvent) => void) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  return { status, send, subscribe, reconnect: connect, disconnect };
}
