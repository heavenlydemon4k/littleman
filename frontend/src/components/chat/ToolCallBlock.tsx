import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import type { ToolCall } from "../../types";

interface Props {
  call: ToolCall;
}

export function ToolCallBlock({ call }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-2 rounded border border-surface-4 bg-surface-1 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 hover:bg-surface-2 transition-colors"
      >
        <Wrench size={12} className="text-amber-400 flex-shrink-0" />
        <span className="font-mono text-amber-400">{call.name}</span>
        <span className="ml-auto text-muted">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {open && (
        <div className="border-t border-surface-4 px-3 py-2">
          <pre className="font-mono text-muted overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(call.args, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
