/**
 * Shared loading state configurations for DocIntel components
 * Prevents duplication of ProcessingLoadingState props across components
 */

interface Step {
  id: string;
  label: string;
  status: 'loading' | 'pending';
}

interface LoadingStateConfig {
  title: string;
  description?: string;
  steps?: Step[];
}

export const PROCESSING_STATES = {
  GENERATING_SCHEMA: {
    title: 'Generating schema from document',
    description: 'Analyzing document structure and creating extraction schema',
    steps: [{ id: 'generate-schema', label: 'Generating schema', status: 'loading' as const }],
  },
  EXTRACTING: {
    title: 'Extracting document',
    description: 'Extracting structured data from your document',
    steps: [{ id: 'extract', label: 'Extracting document', status: 'loading' as const }],
  },
  PARSING: {
    title: 'Parsing your document',
  },
} satisfies Record<string, LoadingStateConfig>;
