import { useEffect, useRef, useState } from "react";
import { FileText, Save, Loader2, CheckCircle } from "lucide-react";
import clsx from "clsx";
import type { WorkspaceFile } from "../types";

type SaveState = "idle" | "saving" | "saved" | "error";

export function WorkspacePage() {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    fetch("/api/workspace/files")
      .then((r) => r.json())
      .then((f: WorkspaceFile[]) => {
        setFiles(f);
        if (f.length > 0 && !selected) openFile(f[0].path);
      })
      .catch(console.error);
  }, []);

  const openFile = (path: string) => {
    setSelected(path);
    setSaveState("idle");
    fetch(`/api/workspace/files/${path}`)
      .then((r) => r.json())
      .then((data: { path: string; content: string }) => {
        setContent(data.content);
        setOriginal(data.content);
      })
      .catch(console.error);
  };

  const save = async () => {
    if (!selected) return;
    setSaveState("saving");
    try {
      await fetch(`/api/workspace/files/${selected}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setOriginal(content);
      setSaveState("saved");
      clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => setSaveState("idle"), 2000);
    } catch {
      setSaveState("error");
    }
  };

  const dirty = content !== original;

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* File tree */}
      <div className="w-52 flex-shrink-0 overflow-y-auto border-r border-border bg-surface-1 py-2">
        <p className="px-4 pb-2 pt-1 text-xs font-semibold uppercase tracking-widest text-muted">
          Workspace
        </p>
        {files.map((f) => (
          <button
            key={f.path}
            onClick={() => openFile(f.path)}
            className={clsx(
              "flex w-full items-center gap-2 px-4 py-1.5 text-sm transition-colors",
              selected === f.path
                ? "bg-surface-3 text-white"
                : "text-muted hover:bg-surface-2 hover:text-white"
            )}
          >
            <FileText size={13} className="flex-shrink-0" />
            <span className="truncate font-mono text-xs">{f.name}</span>
          </button>
        ))}
      </div>

      {/* Editor */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {selected ? (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <span className="font-mono text-xs text-muted">{selected}</span>
              <div className="flex items-center gap-2">
                {dirty && <span className="h-1.5 w-1.5 rounded-full bg-amber-400" title="Unsaved changes" />}
                {saveState === "saved" && (
                  <span className="flex items-center gap-1 text-xs text-green-400">
                    <CheckCircle size={12} /> saved
                  </span>
                )}
                {saveState === "error" && (
                  <span className="text-xs text-red-400">save failed</span>
                )}
                <button
                  onClick={save}
                  disabled={!dirty || saveState === "saving"}
                  className={clsx(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors",
                    dirty && saveState !== "saving"
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-surface-3 text-muted cursor-not-allowed"
                  )}
                >
                  {saveState === "saving" ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Save size={12} />
                  )}
                  Save
                </button>
              </div>
            </div>

            {/* Textarea */}
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
              className="flex-1 resize-none bg-surface-0 p-5 font-mono text-sm text-white outline-none leading-relaxed"
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "s") {
                  e.preventDefault();
                  save();
                }
                // Tab key inserts 2 spaces
                if (e.key === "Tab") {
                  e.preventDefault();
                  const el = e.currentTarget;
                  const start = el.selectionStart;
                  const end = el.selectionEnd;
                  const newVal = content.slice(0, start) + "  " + content.slice(end);
                  setContent(newVal);
                  requestAnimationFrame(() => {
                    el.selectionStart = el.selectionEnd = start + 2;
                  });
                }
              }}
            />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-muted">
            Select a file to edit
          </div>
        )}
      </div>
    </div>
  );
}
