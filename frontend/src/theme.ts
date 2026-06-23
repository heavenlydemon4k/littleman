// Accent theming. The default scheme is monochrome (black); the user can recolor the accent
// in Settings. Each preset sets the --accent-* CSS variables that Tailwind's blue/accent
// scale resolves to (see tailwind.config.ts). Choice persists in localStorage.

export interface AccentPreset {
  key: string;
  label: string;
  // 200..700, light to strong. 200-400 are used for text/icons on dark; 600-700 for fills.
  stops: [string, string, string, string, string, string];
}

export const ACCENT_PRESETS: AccentPreset[] = [
  { key: "mono", label: "Monochrome", stops: ["#eaeaea", "#dcdcdc", "#c4c4c4", "#9a9a9a", "#333333", "#3f3f3f"] },
  { key: "blue", label: "Blue", stops: ["#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8"] },
  { key: "green", label: "Green", stops: ["#a7f3d0", "#6ee7b7", "#34d399", "#10b981", "#059669", "#047857"] },
  { key: "amber", label: "Amber", stops: ["#fde68a", "#fcd34d", "#fbbf24", "#f59e0b", "#d97706", "#b45309"] },
  { key: "purple", label: "Purple", stops: ["#ddd6fe", "#c4b5fd", "#a78bfa", "#8b5cf6", "#7c3aed", "#6d28d9"] },
];

const STORAGE_KEY = "littleman.accent";
const LEVELS = [200, 300, 400, 500, 600, 700];

export function applyAccent(key: string): void {
  const preset = ACCENT_PRESETS.find((p) => p.key === key) ?? ACCENT_PRESETS[0];
  const root = document.documentElement;
  preset.stops.forEach((color, i) => root.style.setProperty(`--accent-${LEVELS[i]}`, color));
  localStorage.setItem(STORAGE_KEY, preset.key);
}

export function currentAccent(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "mono";
}

// Apply the saved accent as early as possible (called from main.tsx before render).
export function initAccent(): void {
  applyAccent(currentAccent());
}
