export const snakeCaseToCamelCase = (str: string): string => {
  return str
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  hour12: true,
});

export const formatDatetime = (date?: Date | string | null): string | undefined => {
  if (!date) return undefined;
  const result = dateTimeFormatter.format(new Date(date));
  return result;
};

export type SearchRule<T> = {
  value: (item: T) => string;
};

export type SearchRules<T> = Record<string, SearchRule<T>>;

/**
 * Simple fuzzy data searcher that matches search terms against data items
 */
export function fuzzyDataSearcher<T>(searchRules: SearchRules<T>, data: T[]) {
  return (searchTerm: string): T[] => {
    if (!searchTerm || searchTerm.trim() === '') {
      return data;
    }

    const lowerSearchTerm = searchTerm.toLowerCase();

    return data.filter((item) => {
      return Object.values(searchRules).some((rule) => {
        const value = rule.value(item);
        return value.toLowerCase().includes(lowerSearchTerm);
      });
    });
  };
}

