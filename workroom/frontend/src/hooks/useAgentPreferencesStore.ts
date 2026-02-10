import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type RecentAgent = {
  agentId: string;
  timestamp: number;
};

const MAX_RECENT_AGENTS = 20;
const MAX_FAVOURITES = 20;

type AgentPreferencesState = {
  favouritesByTenant: Record<string, string[]>;
  recentAgentsByTenant: Record<string, RecentAgent[]>;
};

type AgentPreferencesActions = {
  addFavourite: (tenantId: string, agentId: string) => void;
  removeFavourite: (tenantId: string, agentId: string) => void;
  reorderFavourites: (tenantId: string, fromIndex: number, toIndex: number) => void;
  trackAgentInteraction: (tenantId: string, agentId: string) => void;
  cleanupStaleAgents: (tenantId: string, validAgentIds: Set<string>) => void;
};

type AgentPreferencesStore = AgentPreferencesState & AgentPreferencesActions;

const EMPTY_FAVOURITES: string[] = [];
const EMPTY_RECENT: RecentAgent[] = [];

const getFavourites = (state: AgentPreferencesState, tenantId: string): string[] =>
  state.favouritesByTenant[tenantId] ?? EMPTY_FAVOURITES;

const getRecentAgents = (state: AgentPreferencesState, tenantId: string): RecentAgent[] =>
  state.recentAgentsByTenant[tenantId] ?? EMPTY_RECENT;

/**
 * Store managing user's favourite and recently-interacted agents.
 * Data is scoped per tenant and persisted to localStorage.
 * Stale agent IDs are cleaned up when the agent list is available.
 */
export const useAgentPreferencesStore = create<AgentPreferencesStore>()(
  persist(
    (set, get) => ({
      favouritesByTenant: {},
      recentAgentsByTenant: {},

      addFavourite: (tenantId: string, agentId: string) => {
        const favourites = getFavourites(get(), tenantId);
        if (favourites.includes(agentId) || favourites.length >= MAX_FAVOURITES) {
          return;
        }
        set({
          favouritesByTenant: { ...get().favouritesByTenant, [tenantId]: [...favourites, agentId] },
        });
      },

      removeFavourite: (tenantId: string, agentId: string) => {
        set({
          favouritesByTenant: {
            ...get().favouritesByTenant,
            [tenantId]: getFavourites(get(), tenantId).filter((id) => id !== agentId),
          },
        });
      },

      reorderFavourites: (tenantId: string, fromIndex: number, toIndex: number) => {
        const newFavourites = [...getFavourites(get(), tenantId)];
        const [moved] = newFavourites.splice(fromIndex, 1);
        newFavourites.splice(toIndex, 0, moved);
        set({ favouritesByTenant: { ...get().favouritesByTenant, [tenantId]: newFavourites } });
      },

      trackAgentInteraction: (tenantId: string, agentId: string) => {
        const recentAgents = getRecentAgents(get(), tenantId);
        const filtered = recentAgents.filter((r) => r.agentId !== agentId);
        const updated = [{ agentId, timestamp: Date.now() }, ...filtered].slice(0, MAX_RECENT_AGENTS);
        set({ recentAgentsByTenant: { ...get().recentAgentsByTenant, [tenantId]: updated } });
      },

      cleanupStaleAgents: (tenantId: string, validAgentIds: Set<string>) => {
        const state = get();
        const favourites = getFavourites(state, tenantId).filter((id) => validAgentIds.has(id));
        const recentAgents = getRecentAgents(state, tenantId).filter((r) => validAgentIds.has(r.agentId));
        set({
          favouritesByTenant: { ...state.favouritesByTenant, [tenantId]: favourites },
          recentAgentsByTenant: { ...state.recentAgentsByTenant, [tenantId]: recentAgents },
        });
      },
    }),
    {
      name: 'agent-preferences',
      partialize: (state) => ({
        favouritesByTenant: state.favouritesByTenant,
        recentAgentsByTenant: state.recentAgentsByTenant,
      }),
    },
  ),
);

/**
 * Convenience selectors for use in components that already know the tenantId.
 */
export const selectFavourites = (state: AgentPreferencesStore, tenantId: string): string[] =>
  getFavourites(state, tenantId);

export const selectRecentAgents = (state: AgentPreferencesStore, tenantId: string): RecentAgent[] =>
  getRecentAgents(state, tenantId);
