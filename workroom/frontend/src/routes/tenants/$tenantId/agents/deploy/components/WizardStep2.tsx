import { Box, Button, Input, Select } from '@sema4ai/components';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams, useRouteContext } from '@tanstack/react-router';
import { FC, useEffect, useMemo, useRef } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { PROVIDERS } from '~/components/platforms/llms/components/llmSchemas';
import { normalizeProviderToGroup } from './providerUtils';

import { AgentDeploymentFormSchema } from './context';
type PlatformConfig = {
  platform_id: string;
  name: string;
  kind: string;
  models?: Record<string, string[]>;
};

type Props = {
  errorMessage?: string;
};

export const WizardStep2: FC<Props> = ({ errorMessage }) => {
  const navigate = useNavigate();
  const { register, watch, control, setValue } = useFormContext<AgentDeploymentFormSchema>();
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const { llmId } = watch();
  const initialLlmIdRef = useRef<string | undefined>(llmId as string | undefined);

  const packageSuggestion = useMemo(() => {
    if (initialLlmIdRef.current && initialLlmIdRef.current.startsWith('package:')) {
      const [, providerRaw, modelRaw] = initialLlmIdRef.current.split(':');
      if (providerRaw && modelRaw) return { provider: providerRaw.toLowerCase(), model: modelRaw } as const;
    }
    return null;
  }, []);

  const { data: platformsResponse, error: platformsError } = useQuery({
    queryKey: ['platforms', tenantId],
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/', {
        silent: true,
      });

      if (!response.success) {
        throw new Error(response?.message || 'Failed to fetch platforms');
      }

      return response.data as PlatformConfig[];
    },
  });

  const platforms = useMemo<PlatformConfig[]>(
    () => (Array.isArray(platformsResponse) ? platformsResponse : []),
    [platformsResponse],
  );

  const recommendedPlatformIds = useMemo<Set<string>>(() => {
    if (!packageSuggestion) return new Set();
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
    const matches = platforms
      .filter((p) => normalizeProviderToGroup(p.kind) === packageSuggestion.provider)
      .filter((p) => {
        const group = normalizeProviderToGroup(p.kind);
        const kindKey = group || normalize(p.kind || '');
        const modelsForKind = p.models?.[kindKey] || p.models?.[normalize(p.kind || '')] || [];
        return modelsForKind.includes(packageSuggestion.model);
      })
      .map((p) => p.platform_id);
    return new Set(matches);
  }, [packageSuggestion, platforms]);

  useEffect(() => {
    if (packageSuggestion) {
      const matches = recommendedPlatformIds;
      if (
        matches.size > 0 &&
        typeof initialLlmIdRef.current === 'string' &&
        initialLlmIdRef.current.startsWith('package:')
      ) {
        const first = Array.from(matches)[0] as string;
        setValue('llmId', first);
      } else if (matches.size === 0) {
        setValue('llmId', '');
      }
    } else if (!llmId && platforms.length > 0) {
      setValue('llmId', platforms[0].platform_id);
    }
  }, [packageSuggestion, recommendedPlatformIds, llmId, platforms, setValue]);

  const providerItems = useMemo(() => {
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
    const groupFor = (kind: string) => normalizeProviderToGroup(kind);
    const providerOrderIndex = (g: string) => {
      const idx = (PROVIDERS as readonly string[]).indexOf(g);
      return idx === -1 ? Number.MAX_SAFE_INTEGER : idx;
    };
    const beautifyModelLabel = (value: string): string => {
      const id = value.split(':')[1] || value;
      return id
        .replace(/-/g, ' ')
        .replace(/^gpt /, 'GPT ')
        .replace(/^o(\d)/i, (_, d) => `O${d} `)
        .replace(/\bmini\b/i, 'Mini')
        .replace(/\bhigh\b/i, 'High')
        .replace(/\bopenai service\b/i, 'OpenAI Service')
        .replace(/\bamazon bedrock\b/i, 'Amazon Bedrock')
        .replace(/\bazure\b/i, 'Azure')
        .replace(/\bopenai\b/i, 'OpenAI')
        .replace(/\bbedrock\b/i, 'Bedrock')
        .replace(/\b(\w)/g, (m) => m.toUpperCase());
    };

    const enriched = platforms.map((p) => {
      const group = groupFor(p.kind);
      const kindKey = group || normalize(p.kind || '');
      const modelsForKind = p.models?.[kindKey] || p.models?.[normalize(p.kind || '')] || [];
      const primaryModel = modelsForKind[0];
      const prettyModel = primaryModel ? beautifyModelLabel(`${kindKey}:${primaryModel}`) : p.kind;
      return {
        group,
        item: {
          optgroup: group.toUpperCase(),
          value: p.platform_id,
          label: `${p.name} — ${prettyModel}`,
          badge: recommendedPlatformIds.has(p.platform_id)
            ? ({ variant: 'success', label: 'Recommended' } as const)
            : undefined,
        },
      };
    });

    enriched.sort((a, b) => {
      const ra = providerOrderIndex(a.group);
      const rb = providerOrderIndex(b.group);
      if (ra !== rb) return ra - rb;
      return a.item.label.localeCompare(b.item.label);
    });

    return enriched.map((e) => e.item);
  }, [platforms, recommendedPlatformIds]);

  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        <Input label="Name" {...register('name')} error={errorMessage} />
      </Box>

      <Box>
        <Input
          label="Description"
          {...register('description')}
          description="This description is visible to all users who have access to the agent."
          autoGrow={4}
        />
      </Box>

      <Box>
        <Controller
          name="llmId"
          control={control}
          render={({ field }) => (
            <Select
              label="Large Language Model"
              items={providerItems}
              value={field.value}
              onChange={(value) => {
                field.onChange(value);
                setValue('apiKey', '');
              }}
              onBlur={field.onBlur}
              ref={field.ref}
              description="Choose a model platform (e.g., openai, google, anthropic)."
              disabled={platforms.length === 0}
            />
          )}
        />
        <Box mt="$8">
          <Button onClick={() => navigate({ to: '/tenants/$tenantId/agents/deploy/llms/new', params: { tenantId } })}>
            Configure new LLM
          </Button>
        </Box>
        {packageSuggestion && recommendedPlatformIds.size === 0 && (
          <Box mt="$8" color="content.subtle" fontSize="$12">
            This agent works best with "{packageSuggestion.model}". Configure a new LLM below.
          </Box>
        )}
        {platformsError && (
          <Box mt="$8" color="content.error" fontSize="$12">
            {(platformsError as Error).message || 'Failed to load platforms'}
          </Box>
        )}
      </Box>
    </Box>
  );
};
