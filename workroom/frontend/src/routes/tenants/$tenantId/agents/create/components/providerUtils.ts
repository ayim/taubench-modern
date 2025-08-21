export function normalizeProviderToGroup(input: unknown): string {
  if (typeof input !== 'string') return 'unknown';
  const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  const providerMap: Record<string, string> = {
    openai: 'openai',
    azure: 'azure',
    azureopenai: 'azure',
    bedrock: 'bedrock',
    amazonbedrock: 'bedrock',
  };
  const key = normalize(input);
  return providerMap[key] || key;
}
