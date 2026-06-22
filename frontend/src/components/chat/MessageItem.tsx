import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import type { ChatMessage } from "../../types";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCallBlock } from "./ToolCallBlock";

interface Props {
  message: ChatMessage & { _streaming?: boolean };
}

export function MessageItem({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={clsx("flex gap-3 px-4 py-3", isUser && "flex-row-reverse")}>
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
      <div className={clsx("flex flex-col gap-1 max-w-[80%]", isUser && "items-end")}>
        {/* Thinking */}
        {message.thinking && <ThinkingBlock content={message.thinking} />}

        {/* Tool calls */}
        {message.tool_calls?.map((tc) => (
          <ToolCallBlock key={tc.id} call={tc} />
        ))}

        {/* Text body */}
        {message.content && (
          <div
            className={clsx(
              "rounded-lg px-4 py-3 text-sm leading-relaxed",
              isUser
                ? "bg-surface-3 text-white"
                : "bg-surface-2 text-white"
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
        )}

        {/* Streaming cursor */}
        {message._streaming && !message.content && !message.thinking && !message.tool_calls?.length && (
          <div className="rounded-lg bg-surface-2 px-4 py-3">
            <span className="inline-block w-1.5 h-4 bg-blue-400 animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
