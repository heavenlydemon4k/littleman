import type { Elicitation } from "../types";

const ASK_RE = /```ask\s*\n([\s\S]*?)\n?```/;

/**
 * Split an assistant message into the prose to render in the bubble and an optional structured
 * ask (the fenced ```ask block the model emits — see CHAT_ELICITATION_GUIDE on the backend).
 * Tolerant: malformed JSON or a missing question yields no ask, and the raw text is left as prose.
 */
export function parseAsk(content: string | null): { prose: string; ask: Elicitation | null } {
  if (!content) return { prose: "", ask: null };
  const m = content.match(ASK_RE);
  if (!m) return { prose: content, ask: null };

  let ask: Elicitation | null = null;
  try {
    const raw = JSON.parse(m[1]) as Partial<Elicitation>;
    const options = Array.isArray(raw.options) ? raw.options.map(String).filter(Boolean) : [];
    if (typeof raw.question === "string" && raw.question.trim()) {
      ask = { question: raw.question.trim(), options, multi: !!raw.multi };
    }
  } catch {
    ask = null;
  }

  const prose = content.replace(ASK_RE, "").trim();
  return { prose, ask };
}
