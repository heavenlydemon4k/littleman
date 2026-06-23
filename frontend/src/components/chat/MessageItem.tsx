import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { Copy, Check } from "lucide-react";
import type { ChatMessage } from "../../types";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCallBlock } from "./ToolCallBlock";

interface Props {
  message: ChatMessage & { _streaming?: boolean };
}

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function MessageItem({ message }: Props) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const copy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={clsx("group flex gap-3 px-4 py-3", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={clsx(
          "flex-shrink-0 w-7 h-7 rounded flex items-center justify-center text-xs font-mono font-semibold select-none mt-0.5",
          isUser ? "bg-surface-4 text-white" : "bg-blue-600 text-white"
        )}
      >
        {isUser ? "you" : "lm"}
      </div>

      {/* Content */}
      <div className={clsx("flex flex-col gap-1 max-w-[80%] min-w-0", isUser && "items-end")}>
        {/* Thinking */}
        {message.thinking && <ThinkingBlock content={message.thinking} />}

        {/* Tool calls */}
        {message.tool_calls?.map((tc) => (
          <ToolCallBlock key={tc.id} call={tc} />
        ))}

        {/* Text body */}
        {message.content && (
          <div className="relative">
            <div
              className={clsx(
                "rounded-lg px-4 py-3 text-sm leading-relaxed",
                isUser ? "bg-surface-3 text-white" : "bg-surface-2 text-white"
              )}
            >
              {isUser ? (
                <span className="whitespace-pre-wrap">{message.content}</span>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const isBlock = className?.startsWith("language-");
                      return isBlock ? (
                        <pre className="my-2 overflow-x-auto rounded bg-surface-0 px-3 py-2 font-mono text-xs">
                          <code>{children}</code>
                        </pre>
                      ) : (
                        <code
                          className="rounded bg-surface-0 px-1 py-0.5 font-mono text-xs text-blue-300"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    p({ children }) {
                      return <p className="mb-2 last:mb-0">{children}</p>;
                    },
                    ul({ children }) {
                      return <ul className="mb-2 ml-4 list-disc">{children}</ul>;
                    },
                    ol({ children }) {
                      return <ol className="mb-2 ml-4 list-decimal">{children}</ol>;
                    },
                    li({ children }) {
                      return <li className="mb-0.5">{children}</li>;
                    },
                    h1({ children }) {
                      return <h1 className="mb-2 text-base font-semibold">{children}</h1>;
                    },
                    h2({ children }) {
                      return <h2 className="mb-2 text-sm font-semibold">{children}</h2>;
                    },
                    h3({ children }) {
                      return <h3 className="mb-1 text-sm font-medium">{children}</h3>;
                    },
                    blockquote({ children }) {
                      return (
                        <blockquote className="my-2 border-l-2 border-surface-4 pl-3 text-muted">
                          {children}
                        </blockquote>
                      );
                    },
                    table({ children }) {
                      return (
                        <div className="overflow-x-auto">
                          <table className="my-2 w-full border-collapse text-xs">{children}</table>
                        </div>
                      );
                    },
                    th({ children }) {
                      return (
                        <th className="border border-surface-4 px-2 py-1 text-left font-semibold">
                          {children}
                        </th>
                      );
                    },
                    td({ children }) {
                      return (
                        <td className="border border-surface-4 px-2 py-1">{children}</td>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>

            {/* Hover actions row */}
            <div className={clsx(
              "mt-1 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100",
              isUser ? "justify-end" : "justify-start"
            )}>
              {!isUser && (
                <button
                  onClick={copy}
                  title="Copy message"
                  className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted hover:text-white transition-colors"
                >
                  {copied ? (
                    <><Check size={11} className="text-green-400" /><span className="text-green-400">copied</span></>
                  ) : (
                    <><Copy size={11} />copy</>
                  )}
                </button>
              )}
              {message.created_at && (
                <span className="text-[10px] text-muted/50">
                  {fmtTime(message.created_at)}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Streaming cursor -- shown while waiting for first token */}
        {message._streaming && !message.content && !message.thinking && !message.tool_calls?.length && (
          <div className="rounded-lg bg-surface-2 px-4 py-3">
            <span className="inline-block w-1.5 h-4 bg-blue-400 animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
