import { useMemo } from 'react';

let __tenantId: string | null = null;

export const useTenantId = (): string => {
  const tenantId = useMemo(() => {
    if (__tenantId) {
      return __tenantId;
    }

    const metaEl = document.head.querySelector('meta[name=tenantId]');
    if (!metaEl) {
      throw new Error('No meta for tenantId found in document');
    }

    __tenantId = metaEl.getAttribute('content');

    return __tenantId as string;
  }, []);

  return tenantId;
};
