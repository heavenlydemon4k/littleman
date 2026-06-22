import { KeyboardEvent, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import clsx from "clsx";

interface Props {
  onSend: (text: string) => void;
  streaming: boolean;
  disabled: boolean;
}

export function ChatInput({ onSend, streaming, disabled }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const text = value.trim();
    if (!text || streaming || disabled) return;
    onSend(text);
    setValue("");
    if (ref.current) {
      ref.current.style.height = "auto";
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onInput = () => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="border-t border-border bg-surface-1 p-4">
      <div className="flex items-end gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3 focus-within:border-blue-500 transition-colors">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onInput={onInput}
          placeholder={disabled ? "Select a session to start chatting" : "Message littleman… (Enter to send, Shift+Enter for newline)"}
          disabled={disabled || streaming}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-white placeholder-muted outline-none disabled:opacity-50"
          style={{ minHeight: "24px", maxHeight: "200px" }}
        />
        <button
          onClick={submit}
          disabled={!value.trim() || streaming || disabled}
          className={clsx(
            "flex-shrink-0 rounded-lg p-1.5 transition-colors",
            value.trim() && !streaming && !disabled
              ? "text-blue-400 hover:bg-surface-4"
              : "text-muted cursor-not-allowed"
          )}
        >
          {streaming ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Send size={18} />
          )}
        </button>
      </div>
      <p className="mt-1.5 text-center text-xs text-muted">
        littleman can make mistakes. Verify bets before they execute.
      </p>
    </div>
  );
}
