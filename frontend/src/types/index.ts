export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  thinking: string | null;
  tool_calls: ToolCall[] | null;
  tool_call_id: string | null;
  tool_name: string | null;
  created_at: string;
}

export interface LLMConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  api_key: string | null;
  base_url: string | null;
  is_primary: boolean;
  is_secondary: boolean;
  extra_params: Record<string, unknown>;
  created_at: string;
}

export interface WorkspaceFile {
  path: string;
  name: string;
  size: number;
}

// Live action feed — events emitted by a running wake (see littleman/agent/events.py)
export type AgentEventType =
  | "session_start"
  | "stage"
  | "reasoning"
  | "tool_call"
  | "tool_result"
  | "session_done";

export interface AgentEvent {
  seq: number;
  id: string;
  agent_session_id: string;
  type: AgentEventType;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export type ActivityWsEvent =
  | { type: "backlog"; events: AgentEvent[] }
  | { type: "events"; events: AgentEvent[] };

// WebSocket event types streamed from the backend
export type WsEvent =
  | { type: "user_message"; message: ChatMessage }
  | { type: "assistant_start"; id: string }
  | { type: "token"; content: string }
  | { type: "thinking"; content: string }
  | { type: "tool_call"; call: ToolCall }
  | { type: "assistant_done"; id: string }
  | { type: "error"; message: string }
  | { type: "done" };
