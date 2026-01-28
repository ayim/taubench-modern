import { ThreadMessage } from '@sema4ai/agent-server-interface';

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

/**
 * Formats a timestamp as relative time (e.g., "Today", "2d ago", "1w ago").
 *
 * Similar to `formatRelativeDate` from `@sema4ai/components/src/utils/date.ts` with variations:
 * - Returns "Today" for < 1 day (DS uses "Xs ago", "Xm ago", "Xh ago")
 * - Supports weeks ("Xw ago") and months ("Xmo ago") (DS caps at "Xd ago" then falls back to formatted date)
 * - Returns null for invalid/epoch dates (DS falls back to formatted date after 2 days)
 * - IMPORTANT - returns null for date set to 1970 (the agent server appears to have it set as a default until the "correct" value is set)
 */
export const formatRelativeTime = (timestamp: string): string | null => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime()) || date.getFullYear() === 1970) {
    return null;
  }

  const now = new Date();
  const todayMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((todayMidnight.getTime() - dateMidnight.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 1) {
    return 'Today';
  }

  if (diffDays === 1) {
    return '1d ago';
  }
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7);
    return weeks === 1 ? '1w ago' : `${weeks}w ago`;
  }
  if (diffDays < 365) {
    const months = Math.floor(diffDays / 30);
    return months === 1 ? '1mo ago' : `${months}mo ago`;
  }
  const years = Math.floor(diffDays / 365);
  return years === 1 ? '1y ago' : `${years}y ago`;
};

export const formatMessageInfo = (message: ThreadMessage): string => {
  const lines: string[] = [];

  let isDataPending = false;
  if (message.created_at) {
    const date = new Date(message.created_at);
    if (date.getFullYear() === 1970) {
      isDataPending = true;
    }
  }

  if (isDataPending) {
    return 'Fetching data, check back soon.';
  }

  if (message.created_at) {
    const date = new Date(message.created_at);
    if (!Number.isNaN(date.getTime())) {
      const timestamp = date.toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      lines.push(`Timestamp: ${timestamp}`);
    }
  }

  const modelString = message.agent_metadata?.model as string | undefined;
  const platform = message.agent_metadata?.platform;

  if (platform) {
    lines.push(`Platform: ${platform}`);
  }

  if (modelString) {
    const parts = modelString.split('/');
    if (parts.length === 3) {
      const [, provider, model] = parts;
      lines.push(`Provider: ${provider}`);
      lines.push(`Model: ${model}`);
    } else {
      lines.push(`Model: ${modelString}`);
    }
  }

  const totalUsage = message.agent_metadata?.total_usage as
    | {
        input_tokens?: number;
        output_tokens?: number;
        total_tokens?: number;
        cached_tokens?: number;
        reasoning_tokens?: number;
      }
    | undefined;

  if (totalUsage) {
    const isValidNumber = (val: unknown): val is number => typeof val === 'number' && !Number.isNaN(val);

    const hasValidTokens =
      isValidNumber(totalUsage.input_tokens) ||
      isValidNumber(totalUsage.output_tokens) ||
      isValidNumber(totalUsage.total_tokens);

    if (hasValidTokens) {
      lines.push('');
    }

    if (isValidNumber(totalUsage.input_tokens)) {
      lines.push(`Input tokens: ${totalUsage.input_tokens.toLocaleString()}`);
    }
    if (isValidNumber(totalUsage.cached_tokens) && totalUsage.cached_tokens > 0) {
      const cacheRate =
        isValidNumber(totalUsage.input_tokens) && totalUsage.input_tokens > 0
          ? ((totalUsage.cached_tokens / totalUsage.input_tokens) * 100).toFixed(0)
          : '0';
      lines.push(`Cached tokens: ${totalUsage.cached_tokens.toLocaleString()} (${cacheRate}%)`);
    }
    if (isValidNumber(totalUsage.output_tokens)) {
      lines.push(`Output tokens: ${totalUsage.output_tokens.toLocaleString()}`);
    }
    if (isValidNumber(totalUsage.reasoning_tokens) && totalUsage.reasoning_tokens > 0) {
      lines.push(`Reasoning tokens: ${totalUsage.reasoning_tokens.toLocaleString()}`);
    }
    if (isValidNumber(totalUsage.total_tokens)) {
      lines.push(`Total tokens: ${totalUsage.total_tokens.toLocaleString()}`);
    }
  }

  return lines.join('\n');
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

/**
 * Comparator function to sort items by created_at date in descending order (newest first)
 * @example
 * const sortedItems = items.sort(sortByCreatedAtDesc);
 */
export const sortByCreatedAtDesc = <T extends { created_at?: string | null }>(a: T, b: T): number => {
  return new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime();
};

export const sanitizeFileName = (fileName: string) => {
  return fileName.replace(/[^A-Za-z0-9_.-]/g, '_');
};

export const downloadFile = (data: Blob, fileName: string) => {
  const url = URL.createObjectURL(data);
  const a = document.createElement('a');

  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);

  a.click();

  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const downloadMarkdown = (filename: string, content: string) => {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
  downloadFile(blob, filename);
};

export const safeParseJson = (text: string | null | undefined) => {
  if (typeof text !== 'string') return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
