import { useState } from "react";
import { ChevronDown, ChevronRight, Brain } from "lucide-react";

interface Props {
  content: string;
}

export function ThinkingBlock({ content }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-2 rounded border border-surface-4 bg-surface-1 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-muted hover:text-white transition-colors"
      >
        <Brain size={12} className="text-blue-500 flex-shrink-0" />
        <span className="font-mono text-blue-400">thinking</span>
        <span className="ml-auto">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {open && (
        <div className="border-t border-surface-4 px-3 py-2 font-mono text-muted leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      )}
    </div>
  );
}
