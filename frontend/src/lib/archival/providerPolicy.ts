export const ALLOWED_LOCAL_PROVIDERS = [
  'ollama',
  'openai_compatible',
] as const

export type AllowedLocalProvider = typeof ALLOWED_LOCAL_PROVIDERS[number]

export function isAllowedLocalProvider(provider: string): provider is AllowedLocalProvider {
  return ALLOWED_LOCAL_PROVIDERS.includes(provider as AllowedLocalProvider)
}

export const LOCAL_PROVIDER_LABELS: Record<AllowedLocalProvider, string> = {
  ollama: 'Ollama',
  openai_compatible: 'OpenAI-compatible local',
}