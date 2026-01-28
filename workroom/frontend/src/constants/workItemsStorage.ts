export const WORK_ITEMS_STORAGE_KEYS = {
  QUERY_SETTINGS: 'querySettings',
  NAVIGATION_CONTEXT: 'navigationContext',
} as const;

export const getStoragePrefixFromPathname = (pathname: string): string => {
  return pathname.replace(/^\/+/, '').replace(/\/+$/, '').replace(/\//g, '.');
};

export const createWorkItemsStorageKey = (prefix: string, key: keyof typeof WORK_ITEMS_STORAGE_KEYS) => {
  return `${prefix}.${WORK_ITEMS_STORAGE_KEYS[key]}`;
};
