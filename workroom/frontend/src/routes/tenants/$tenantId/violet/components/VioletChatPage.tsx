import { FC, useEffect, useMemo, useState } from 'react';
import { Badge, Button, Input, Progress, Select, Typography } from '@sema4ai/components';
import { Link, useParams } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@sema4ai/agent-server-interface';

import { useSparUIContext, SparUIContext } from '~/api/context';
import { streamManager } from '~/hooks';
import { useThreadsQuery } from '~/queries/threads';
import { NewThreadItem } from '~/components/Thread/components/NewThreadItem';
import { ThreadItem } from '~/components/Thread/components/ThreadItem';
import { getThreadQueryOptions } from '~/queries/thread';
import { Chat } from './Chat';

const LITELLM_BASE_URL = 'https://llm.backend.sema4ai.dev';

type Props = {
  agentId: string;
  violetAgent: components['schemas']['AgentCompat'];
  initialThreadMessage?: string;
};

export const VioletChatPage: FC<Props> = ({ agentId, violetAgent, initialThreadMessage }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  const { agentAPIClient } = useSparUIContext();
  const [threadId, setThreadId] = useState<string | undefined>();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingInitialMessage, setPendingInitialMessage] = useState(initialThreadMessage);
  const platformPresets = useMemo(
    () => [
      {
        label: 'Sema4.ai (normal)',
        value: 'litellm-normal',
        models: { openai: ['gpt-5-1-codex-max', 'gpt-5-low', 'gpt-5-mini'] },
      },
      { label: 'Sema4.ai (accelerated)', value: 'groq-accelerated', models: { groq: ['gpt-oss-120b'] } },
    ],
    [],
  );
  const [platformId, setPlatformId] = useState<string | undefined>(platformPresets[0]?.value);
  const [apiKey, setApiKey] = useState('');
  const [savedConfig, setSavedConfig] = useState<{ platformId: string; apiKey: string } | null>(null);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [agentForSave, setAgentForSave] = useState<Record<string, unknown> | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [loadConfigError, setLoadConfigError] = useState<string | null>(null);
  const { data: threads, isLoading: isThreadsLoading } = useThreadsQuery({
    agentId,
    limit: 50,
  });

  const threadsWithScenario = useMemo(
    () =>
      (threads || []).map((thread) => ({
        ...thread,
        scenarioId: thread.metadata?.scenario_id as string | undefined,
      })),
    [threads],
  );

  // Create or select a thread if one isn't set yet
  useEffect(() => {
    const createThreadIfNeeded = async () => {
      if (threadId || isCreating || isThreadsLoading) {
        return;
      }

      if (threads && threads.length) {
        setThreadId(threads[0]?.thread_id);
        return;
      }

      setIsCreating(true);
      setError(null);

      try {
        const response = await agentAPIClient.agentFetch('post', '/api/v2/threads/', {
          body: {
            name: 'Violet Chat',
            agent_id: agentId,
            messages: pendingInitialMessage
              ? [
                  {
                    role: 'user',
                    content: [{ kind: 'text', text: pendingInitialMessage, complete: true }],
                    complete: true,
                    commited: false,
                  },
                ]
              : undefined,
          },
          errorMsg: 'Failed to start Violet chat',
        });

        if (!response.success || !response.data.thread_id) {
          setError(response.success ? 'Failed to start Violet chat' : response.message);
          return;
        }

        const newThreadId = response.data.thread_id;
        setThreadId(newThreadId);
        setPendingInitialMessage(undefined);

        if (pendingInitialMessage) {
          streamManager.initiateStream({
            content: [{ kind: 'text', text: pendingInitialMessage, complete: true }],
            agentId,
            queryClient,
            threadId: newThreadId,
            startWebsocketStream: async (aid: string) => {
              const { url, token, withBearerTokenAuth } = await agentAPIClient.getWsStreamUrl({
                agentId: aid,
              });
              return withBearerTokenAuth ? new WebSocket(url, ['Bearer', token]) : new WebSocket(url);
            },
          });
        }
      } finally {
        setIsCreating(false);
      }
    };

    createThreadIfNeeded();
  }, [agentAPIClient, agentId, isCreating, isThreadsLoading, pendingInitialMessage, queryClient, threadId, threads]);

  const threadQueryOptions = useMemo(
    () => getThreadQueryOptions({ threadId: threadId ?? 'pending', agentAPIClient }),
    [agentAPIClient, threadId],
  );

  const { data: threadResult, isLoading: isThreadLoading } = useQuery({
    ...threadQueryOptions,
    enabled: Boolean(threadId),
  });

  const currentThread = threadResult?.success ? threadResult.data : undefined;

  // Hide the global sidebar while this view is mounted without touching shared layout components.
  useEffect(() => {
    const className = 'violet-chat-mode';
    const style = document.createElement('style');
    style.textContent = `
      .${className} main {
        grid-template-columns: 1fr !important;
        grid-template-areas: 'section' !important;
      }
      .${className} main > aside {
        display: none !important;
      }
      .${className} [aria-label="Toggle main menu"] {
        display: none !important;
      }
    `;
    document.body.classList.add(className);
    document.head.appendChild(style);
    return () => {
      document.body.classList.remove(className);
      document.head.removeChild(style);
    };
  }, []);

  const preset = platformPresets.find((item) => item.value === platformId);
  const isDirty = savedConfig
    ? savedConfig.platformId !== platformId || savedConfig.apiKey !== apiKey
    : Boolean(platformId || apiKey);
  const canSave = Boolean(platformId && apiKey && preset) && !isSavingConfig && !isLoadingConfig;
  const statusBadge = (() => {
    if (isSavingConfig) {
      return { variant: 'info' as const, label: 'Saving...' };
    }
    if (isLoadingConfig) {
      return { variant: 'info' as const, label: 'Loading...' };
    }
    if (!savedConfig && !isDirty) {
      return { variant: 'warning' as const, label: 'Not configured' };
    }
    if (isDirty) {
      return { variant: 'info' as const, label: 'Unsaved changes' };
    }
    return { variant: 'success' as const, label: 'Saved' };
  })();

  // Load current platform config (raw, so api key is included) and hydrate UI
  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setIsLoadingConfig(true);
      setLoadConfigError(null);
      const resp = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}/raw', {
        params: { path: { aid: agentId } },
        errorMsg: 'Failed to load agent config',
      });
      if (!isMounted) return;

      if (!resp.success || !resp.data) {
        const msg = (resp as { message?: string }).message;
        setLoadConfigError(msg || 'Failed to load agent config');
        setIsLoadingConfig(false);
        return;
      }

      const agent = resp.data as Record<string, unknown>;
      setAgentForSave(agent);

      const platformConfigs = (agent.platform_configs as unknown[]) || [];
      const litellmConfig = platformConfigs.find((cfg) => {
        const c = cfg as Record<string, unknown>;
        return c.kind === 'litellm';
      }) as components['schemas']['LiteLLMPlatformParameters'] | undefined;
      const groqConfig = platformConfigs.find((cfg) => {
        const c = cfg as Record<string, unknown>;
        return c.kind === 'groq';
      }) as components['schemas']['GroqPlatformParameters'] | undefined;

      if (litellmConfig) {
        const models = (litellmConfig.models as Record<string, string[]>) || {};
        let detectedPlatformId: string | undefined;
        if (models.openai?.includes('gpt-5-low')) {
          detectedPlatformId = 'litellm-normal';
        }

        if (detectedPlatformId) {
          setPlatformId(detectedPlatformId);
          const key = (litellmConfig.litellm_api_key?.value as string) || '';
          setApiKey(key);
          setSavedConfig({ platformId: detectedPlatformId, apiKey: key });
        }
      } else if (groqConfig) {
        const models = (groqConfig.models as Record<string, string[]>) || {};
        if (models.groq?.includes('gpt-oss-120b')) {
          setPlatformId('groq-accelerated');
          const key = (groqConfig.groq_api_key?.value as string) || '';
          setApiKey(key);
          setSavedConfig({ platformId: 'groq-accelerated', apiKey: key });
        }
      }

      setIsLoadingConfig(false);
    };

    load();
    return () => {
      isMounted = false;
    };
  }, [agentAPIClient, agentId]);

  const handleSave = async () => {
    if (!platformId || !apiKey || !preset) {
      return;
    }
    setIsSavingConfig(true);
    setSaveError(null);

    // Fetch latest (raw) agent if we don't have one cached
    let agent = agentForSave;
    if (!agent) {
      const agentResponse = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}/raw', {
        params: { path: { aid: agentId } },
        errorMsg: 'Failed to load agent',
      });

      if (!agentResponse.success) {
        const msg = (agentResponse as { message?: string }).message;
        setIsSavingConfig(false);
        setSaveError(msg || 'Failed to load agent');
        return;
      }

      agent = agentResponse.data as Record<string, unknown>;
      setAgentForSave(agent);
    }

    const payload =
      platformId === 'litellm-normal'
        ? [
            {
              kind: 'litellm',
              litellm_api_key: apiKey,
              litellm_base_url: LITELLM_BASE_URL,
              models: preset.models,
            },
          ]
        : [
            {
              kind: 'groq',
              groq_api_key: apiKey,
              // Same base URL for Groq, we just want to use the Groq platform
              // client we have as it does some "payload massaging" that apparently,
              // even when using Groq via LiteLLM, we still need to do.
              groq_base_url: LITELLM_BASE_URL,
              models: preset.models,
            },
          ];

    try {
      const response = await agentAPIClient.agentFetch('put', '/api/v2/agents/{aid}', {
        params: { path: { aid: agentId } },
        body: {
          name: (agent.name as string) ?? violetAgent.name,
          description: (agent.description as string) ?? '',
          version: (agent.version as string) ?? '1.0.0',
          platform_configs: payload,
          agent_architecture: agent.agent_architecture ?? agent.architecture ?? null,
          runbook: agent.runbook ?? null,
          structured_runbook: agent.structured_runbook ?? null,
          action_packages: agent.action_packages ?? [],
          mcp_servers: agent.mcp_servers ?? [],
          mcp_server_ids: agent.mcp_server_ids ?? [],
          selected_tools: agent.selected_tools ?? {},
          platform_params_ids: agent.platform_params_ids ?? [],
          question_groups: agent.question_groups ?? [],
          observability_configs: agent.observability_configs ?? [],
          mode: agent.mode ?? 'conversational',
          extra: agent.extra ?? {},
          agent_settings: agent.agent_settings ?? {},
          document_intelligence: agent.document_intelligence ?? null,
          advanced_config: agent.advanced_config ?? {},
          metadata: agent.metadata ?? {},
        } as never,
        errorMsg: 'Failed to update platform config',
      });

      if (!response.success) {
        setSaveError(response.message || 'Failed to update platform config');
        return;
      }

      setSavedConfig({ platformId, apiKey });
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update platform config');
    } finally {
      setIsSavingConfig(false);
    }
  };

  const sparAPIContextValue = useMemo(
    () => ({
      platformConfig: { snowflakeEAIUrl: null },
      agentAPIClient,
      tenantId,
    }),
    [agentAPIClient],
  );

  return (
    <SparUIContext.Provider value={sparAPIContextValue}>
      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'row',
          height: '100vh',
          maxHeight: '100vh',
          minHeight: 0,
          width: '100%',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: 280,
            borderRight: '1px solid #e0e0e0',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <Typography variant="body-medium" fontWeight="bold">
            History
          </Typography>
          <NewThreadItem />
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              overflowY: 'auto',
              flex: 1,
              minHeight: 0,
            }}
          >
            {threadsWithScenario.map((thread) => (
              <ThreadItem key={thread.thread_id} item={thread} />
            ))}
            {!threadsWithScenario.length && !isThreadsLoading && (
              <Typography variant="body-small" style={{ color: '#6f6f6f' }}>
                No chats yet
              </Typography>
            )}
          </div>
          <div style={{ marginTop: 'auto' }}>
            <Link to="/tenants/$tenantId/home" params={{ tenantId }} style={{ textDecoration: 'none' }}>
              <Button variant="ghost" size="small" round>
                Home
              </Button>
            </Link>
          </div>
        </div>

        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            padding: '16px',
            gap: '12px',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <Typography variant="body-medium" fontWeight="bold">
                {violetAgent.name}
              </Typography>
              <Typography variant="body-small" style={{ color: '#6f6f6f' }}>
                Zero-config Violet assistant
              </Typography>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '12px' }}>
              <div style={{ minWidth: 180 }}>
                <Select
                  label="Platform"
                  items={platformPresets}
                  value={platformId}
                  onChange={(value) => setPlatformId(String(value))}
                />
              </div>
              <div style={{ minWidth: 220 }}>
                <Input
                  label="API key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Paste key"
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Badge variant={statusBadge.variant} label={statusBadge.label} />
                <Button size="small" onClick={handleSave} disabled={!canSave || !isDirty}>
                  Save
                </Button>
              </div>
            </div>
          </div>

          {error && (
            <Typography variant="body-small" style={{ color: '#b42318' }}>
              {error}
            </Typography>
          )}
          {loadConfigError && (
            <Typography variant="body-small" style={{ color: '#b42318' }}>
              {loadConfigError}
            </Typography>
          )}
          {saveError && (
            <Typography variant="body-small" style={{ color: '#b42318' }}>
              {saveError}
            </Typography>
          )}

          {!threadId || isThreadLoading ? (
            <Progress variant="page" />
          ) : (
            <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
              <Chat agentId={agentId} threadId={threadId} agentType="conversational" thread={currentThread} />
            </div>
          )}
        </div>
      </div>
    </SparUIContext.Provider>
  );
};
