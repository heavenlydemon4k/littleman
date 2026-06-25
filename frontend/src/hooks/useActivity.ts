import { useEffect, useRef, useState } from "react";
import type { ActivityWsEvent, AgentEvent } from "../types";

/**
 * Subscribes to the agent's live action feed (/api/agent/activity/ws).
 *
 * The backend tails the agent_event table — which any wake process appends to — so this is a
 * read-only stream of what the agent is doing as it does it. Events are deduped by their
 * monotonic `seq` and kept in order. Reconnects on drop.
 */
export function useActivity(enabled: boolean) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let ws: WebSocket | null = null;

    const add = (incoming: AgentEvent[]) => {
      const fresh = incoming.filter((e) => !seen.current.has(e.seq));
      if (fresh.length === 0) return;
      fresh.forEach((e) => seen.current.add(e.seq));
      setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.seq - b.seq));
    };

    const connect = () => {
      ws = new WebSocket(`ws://${window.location.host}/api/agent/activity/ws`);
      ws.onmessage = (ev) => {
        try {
          const msg: ActivityWsEvent = JSON.parse(ev.data);
          if (msg.type === "backlog" || msg.type === "events") add(msg.events);
        } catch {
          // malformed frame — ignore
        }
      };
      ws.onclose = () => {
        if (!stopped) reconnectTimer = setTimeout(connect, 2000);
      };
    };
    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [enabled]);

  return events;
}
