import { AgentPackageInspectionResponse } from '../queries/agentPackageInspection';

export const agentPackageSecretsToHeaderEntries = (
  secrets: Record<string, string> | undefined,
): { key: string; value: string; type: 'secret' }[] | undefined => {
  if (!secrets) return undefined;

  const entries = Object.entries(secrets)
    .filter(([, value]) => value && value.trim() !== '')
    .map(([key, value]) => ({ key, value, type: 'secret' as const }));

  return entries.length > 0 ? entries : undefined;
};

export const parseWhitelist = (whitelist: string): string[] | null => {
  const items = whitelist
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean);
  return items.length > 0 ? items : null;
};

export const getUniqueSecretNames = (
  actionPackage: NonNullable<NonNullable<AgentPackageInspectionResponse>['action_packages']>[number],
  whitelist: string[] | null,
): Set<string> => {
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
};

export const getUniqueSecretsMap = (
  actionPackage: NonNullable<NonNullable<AgentPackageInspectionResponse>['action_packages']>[number],
  whitelist: string[] | null,
): Map<string, { description?: string; actions: string[] }> => {
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
};
