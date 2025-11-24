import { logger } from '../logger';
import { PromptEndpointClient, PromptEndpointClientConfig } from '../agent-prompt/client';
import { PlatformConfig } from '../platform-config';
import { AgentArchitecture, EphemeralAgentClient } from '../agent-ephemeral';
import { AgentContext } from '../types';
import {
  EphemeralAgentRunbookEditor,
  EphemeralAgents,
  EphemeralAgentSetup,
  EphemeralAgentsNames,
  EphemeralAgentsNamesType,
  EphemeralGeneric,
} from '../agent-ephemeral/ephemeral-agents';

const DEFAULT_EPHEMERAL_AGENT_TIMEOUT = 30000;

/**
 * Configuration interface for the SAI SDK
 */
export interface SaiSDKConfig {
  /** Configuration for the Prompt Endpoint Client */
  promptClient: PromptEndpointClientConfig;
  /** Platform configuration (API keys, etc.) for PromptRequest */
  platformConfig: PlatformConfig;
  /** Agent ID */
  agentId?: string;
  /** Agent architecture */
  agentArchitecture?: AgentArchitecture;
  /** Default model to use for scenario execution */
  defaultModel?: string;
  /** Agent context for the SAI SDK */
  agentContext?: AgentContext;
  /** Additional configuration options */
  options?: {
    /** Whether to enable debug logging */
    debug?: boolean;
    /** Request timeout in milliseconds */
    timeout?: number;
    /** Retry configuration */
    retry?: {
      attempts?: number;
      delay?: number;
    };
  };
}

/**
 * Singleton class to manage global SDK configuration
 * This class ensures that all scenarios have access to the same configuration
 * when their execute functions are called.
 */
export class SaiSDKConfiguration {
  private static instance: SaiSDKConfiguration | null = null;
  private config: SaiSDKConfig | null = null;
  private promptClient: PromptEndpointClient | null = null;

  private ephemeralAgentClient: EphemeralAgentClient | null = null;
  private ephemeralAgents: EphemeralAgents | null = null;

  /**
   * Private constructor to enforce singleton pattern
   */
  private constructor() {}

  /**
   * Get the singleton instance
   */
  public static getInstance(): SaiSDKConfiguration {
    if (!SaiSDKConfiguration.instance) {
      SaiSDKConfiguration.instance = new SaiSDKConfiguration();
    }
    return SaiSDKConfiguration.instance;
  }

  /**
   * Initialize the SDK configuration
   * This must be called before any scenario execution
   */
  public initialize(config: SaiSDKConfig): SaiSDKConfiguration {
    // Initialize the configuration
    this.config = config;

    // Initialize the prompt client
    this.promptClient = new PromptEndpointClient({
      ...config.promptClient,
      verbose: config.options?.debug,
    });

    // Initialize the ephemeral agent client
    this.ephemeralAgentClient = new EphemeralAgentClient({
      baseUrl: config.promptClient.baseUrl,
      timeout: config.options?.timeout ?? DEFAULT_EPHEMERAL_AGENT_TIMEOUT,
      verbose: config.options?.debug,
    });
    // Initialize the ephemeral agents
    this.ephemeralAgents = {
      generic: new EphemeralGeneric(config),
      agentSetup: new EphemeralAgentSetup(config),
      agentRunbookEditor: new EphemeralAgentRunbookEditor(config),
    };

    // Log the configuration
    if (config.options?.debug) {
      logger.info('SAI SDK Configuration initialized:', {
        baseUrl: config.promptClient.baseUrl,
        ephemeralAgentClient: this.ephemeralAgentClient,
        ephemeralAgents: this.ephemeralAgents,
        defaultModel: config.defaultModel,
        options: config.options,
      });
    }

    return this;
  }

  /**
   * Get the current configuration
   */
  public getConfig(): SaiSDKConfig {
    if (!this.config) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    return this.config;
  }

  /**
   * Get the Prompt Endpoint Client
   */
  public getPromptClient(): PromptEndpointClient {
    if (!this.promptClient) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    return this.promptClient;
  }

  /**
   * Get the platform configuration
   */
  public getPlatformConfig(): PlatformConfig {
    if (!this.config) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    return this.config.platformConfig;
  }

  /**
   * Get the ephemeral agent client
   */
  public getEphemeralAgentClient(): EphemeralAgentClient {
    if (!this.ephemeralAgentClient) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    return this.ephemeralAgentClient;
  }

  /**
   * Get the ephemeral agents
   */
  public getEphemeralAgents(): EphemeralAgents {
    if (!this.ephemeralAgents) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    return this.ephemeralAgents;
  }

  /**
   * Get the default model
   */
  public getDefaultModel(): string | undefined {
    return this.config?.defaultModel;
  }

  /**
   * Check if the SDK is initialized
   */
  public isInitialized(): boolean {
    return this.config !== null && this.promptClient !== null;
  }

  /**
   * Reset the configuration (useful for testing)
   */
  public reset(): void {
    this.config = null;
    this.promptClient = null;
    this.ephemeralAgentClient = null;
    this.ephemeralAgents = null;
  }

  /**
   * Update configuration without reinitializing
   */
  public updateConfig(updates: Partial<SaiSDKConfig>): void {
    if (!this.config) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }

    // Deep merge the configuration
    this.config = {
      ...this.config,
      ...updates,
      promptClient: {
        ...this.config.promptClient,
        ...updates.promptClient,
      },
      platformConfig: {
        ...this.config.platformConfig,
        ...updates.platformConfig,
      },
      options: {
        ...this.config.options,
        ...updates.options,
      },
    };

    // Recreate the prompt client if the promptClient config changed
    if (updates.promptClient) {
      this.promptClient = new PromptEndpointClient(this.config.promptClient);
    }

    if (this.config.options?.debug) {
      logger.info('SDK Configuration updated!');
    }
  }

  /**
   * Update the ephemeral agent configuration
   */
  public updateEphemeralAgentConfig(agentName: EphemeralAgentsNamesType, config: SaiSDKConfig): void {
    if (!this.ephemeralAgents) {
      throw new Error('SDK not initialized. Call initialize() first.');
    }
    switch (agentName) {
      case EphemeralAgentsNames.generic:
        this.ephemeralAgents.generic = new EphemeralGeneric(config);
        break;
      case EphemeralAgentsNames.agentSetup:
        this.ephemeralAgents.agentSetup = new EphemeralAgentSetup(config);
        break;
      case EphemeralAgentsNames.agentRunbookEditor:
        this.ephemeralAgents.agentRunbookEditor = new EphemeralAgentRunbookEditor(config);
        break;
      default:
        throw new Error(`Invalid agent name: ${agentName}`);
    }
  }
}

/**
 * Convenience function to get the singleton instance
 */
export function getSDKConfig(): SaiSDKConfiguration {
  return SaiSDKConfiguration.getInstance();
}

/**
 * Convenience function to initialize the SDK
 */
export function initializeSDK(config: SaiSDKConfig): SaiSDKConfiguration {
  return SaiSDKConfiguration.getInstance().initialize(config);
}
