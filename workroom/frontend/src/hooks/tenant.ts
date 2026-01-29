import { useMemo } from 'react';

export const useTenantId = (): string => {
  const tenantId = useMemo(() => {
    const metaEl = document.head.querySelector('meta[name=tenantId]');
    if (!metaEl) {
      throw new Error('No meta for tenantId found in document');
    }

    return metaEl.getAttribute('content') as string;
  }, []);

  return tenantId;
};
