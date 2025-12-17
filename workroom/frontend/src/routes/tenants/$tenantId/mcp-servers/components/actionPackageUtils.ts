import { components } from '@sema4ai/agent-server-interface';

/**
 * Parse the whitelist string into an array of action names.
 * Returns null if no whitelist is defined.
 */
export function parseWhitelist(whitelist: string | null | undefined): string[] | null {
  if (!whitelist) return null;
  const items = whitelist
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean);
  return items.length > 0 ? items : null;
}

/**
 * Get unique secret names from an action package, filtered by whitelist.
 */
export function getUniqueSecretNames(
  actionPackage: components['schemas']['AgentPackageActionPackageMetadata'],
  whitelist: string[] | null,
): Set<string> {
  const uniqueSecrets = new Set<string>();

  if (!actionPackage.secrets) {
    return uniqueSecrets;
  }

  Object.values(actionPackage.secrets).forEach((secretsConfig) => {
    if (whitelist && !whitelist.includes(secretsConfig.action)) {
      return;
    }
    Object.keys(secretsConfig.secrets ?? {}).forEach((secretName) => {
      uniqueSecrets.add(secretName);
    });
  });

  return uniqueSecrets;
}

/**
 * Get unique secrets with their descriptions from an action package, filtered by whitelist.
 */
export function getUniqueSecretsMap(
  actionPackage: components['schemas']['AgentPackageActionPackageMetadata'],
  whitelist: string[] | null,
): Map<string, { description?: string; actions: string[] }> {
  const uniqueSecretsMap = new Map<string, { description?: string; actions: string[] }>();

  if (!actionPackage.secrets) {
    return uniqueSecretsMap;
  }

  Object.values(actionPackage.secrets).forEach((secretsConfig) => {
    if (whitelist && !whitelist.includes(secretsConfig.action)) {
      return;
    }

    Object.entries(secretsConfig.secrets ?? {}).forEach(([secretName, secretDef]) => {
      if (!uniqueSecretsMap.has(secretName)) {
        uniqueSecretsMap.set(secretName, {
          description: secretDef.description,
          actions: [],
        });
      }
      uniqueSecretsMap.get(secretName)!.actions.push(secretsConfig.action);
    });
  });

  return uniqueSecretsMap;
}
