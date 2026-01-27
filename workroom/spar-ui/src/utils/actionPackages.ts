import { AgentPackageInspectionResponse } from '../queries/agentPackageInspection';

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
