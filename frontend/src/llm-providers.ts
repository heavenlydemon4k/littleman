export interface ProviderPreset {
  key: string;
  label: string;
  prefix: string;
  apiBase: string;
  models: string[];
}

export const PROVIDERS: ProviderPreset[] = [
  {
    key: "openai",
    label: "OpenAI",
    prefix: "openai/",
    apiBase: "",
    models: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  },
  {
    key: "kimi",
    label: "Kimi / Moonshot",
    prefix: "openai/",
    apiBase: "https://api.moonshot.ai/v1",
    models: ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
  },
  {
    key: "anthropic",
    label: "Anthropic",
    prefix: "anthropic/",
    apiBase: "",
    models: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  },
  {
    key: "openrouter",
    label: "OpenRouter",
    prefix: "openrouter/",
    apiBase: "https://openrouter.ai/api/v1",
    models: ["anthropic/claude-sonnet-4-6", "openai/gpt-4o"],
  },
  {
    key: "ollama",
    label: "Ollama",
    prefix: "ollama/",
    apiBase: "http://localhost:11434",
    models: ["llama3.1:8b", "qwen2.5:14b", "llama3.3:70b"],
  },
];

export const CUSTOM_KEY = "custom";

export function fullModel(provider: ProviderPreset, index: number): string {
  const base = provider.models[index] ?? provider.models[0];
  return `${provider.prefix}${base}`;
}
