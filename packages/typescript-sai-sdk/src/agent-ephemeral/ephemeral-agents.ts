import { AgentContext } from '../types';
import { UpsertAgentPayload } from './types';
import { SaiSDKConfig } from '../sdk/config';
import { createSaiGenericAgentConfig } from './agents/agent-generic';
import { createSaiAgentSetupConfig } from './agents/agent-setup';
import { createSaiAgentRunbookEditorConfig } from './agents/agent-runbook-editor';

export enum EphemeralAgentsNames {
  generic = 'generic',
  agentSetup = 'agentSetup',
  agentRunbookEditor = 'agentRunbookEditor',
}

export type EphemeralAgentsNamesType = (typeof EphemeralAgentsNames)[keyof typeof EphemeralAgentsNames];

export type EphemeralAgents = {
  [K in EphemeralAgentsNamesType]: EphemeralAgent;
};

export class EphemeralAgent {
  protected config: SaiSDKConfig;
  protected context: AgentContext | undefined = undefined;
  public agentPayload: UpsertAgentPayload;

  constructor(config: SaiSDKConfig) {
    this.config = config;
    this.agentPayload = {
      name: '',
      description: '',
      version: '',
    };
    this.context = config.agentContext;
  }

  public setContext(context: AgentContext): void {
    this.context = context;
  }
}

export class EphemeralGeneric extends EphemeralAgent {
  constructor(config: SaiSDKConfig) {
    super(config);
    this.agentPayload = createSaiGenericAgentConfig({
      platform_configs: [config.platformConfig],
      agent_id: config.agentId,
      agent_architecture: config.agentArchitecture,
      agent_context: this.context ?? undefined,
    });
  }

  public setContext(context: AgentContext): void {
    super.setContext(context);
    this.agentPayload = createSaiGenericAgentConfig({
      platform_configs: [this.config.platformConfig],
      agent_id: this.config.agentId,
      agent_architecture: this.config.agentArchitecture,
      agent_context: context,
    });
  }
}

export class EphemeralAgentSetup extends EphemeralAgent {
  constructor(config: SaiSDKConfig) {
    super(config);
    this.agentPayload = createSaiAgentSetupConfig({
      platform_configs: [config.platformConfig],
      agent_id: config.agentId,
      agent_architecture: config.agentArchitecture,
      agent_context: this.context ?? undefined,
    });
  }

  public setContext(context: AgentContext): void {
    super.setContext(context);
    this.agentPayload = createSaiAgentSetupConfig({
      platform_configs: [this.config.platformConfig],
      agent_id: this.config.agentId,
      agent_architecture: this.config.agentArchitecture,
      agent_context: context,
    });
  }
}

export class EphemeralAgentRunbookEditor extends EphemeralAgent {
  constructor(config: SaiSDKConfig) {
    super(config);
    this.agentPayload = createSaiAgentRunbookEditorConfig({
      platform_configs: [config.platformConfig],
      agent_id: config.agentId,
      agent_architecture: config.agentArchitecture,
      agent_context: this.context ?? undefined,
    });
  }

  public setContext(context: AgentContext): void {
    super.setContext(context);
    this.agentPayload = createSaiAgentRunbookEditorConfig({
      platform_configs: [this.config.platformConfig],
      agent_id: this.config.agentId,
      agent_architecture: this.config.agentArchitecture,
      agent_context: context,
    });
  }
}
