import { describe, it, expect, beforeEach } from 'vitest';
import { useAgentPreferencesStore, selectFavourites, selectRecentAgents } from './useAgentPreferencesStore';

const TENANT = 'tenant-1';
const TENANT_2 = 'tenant-2';

const resetStore = () => {
  useAgentPreferencesStore.setState({
    favouritesByTenant: {},
    recentAgentsByTenant: {},
  });
};

describe('useAgentPreferencesStore', () => {
  beforeEach(resetStore);

  describe('addFavourite', () => {
    it('adds an agent to favourites', () => {
      useAgentPreferencesStore.getState().addFavourite(TENANT, 'agent-1');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-1']);
    });

    it('does not add duplicates', () => {
      const { addFavourite } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      addFavourite(TENANT, 'agent-1');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-1']);
    });

    it('respects max favourites limit', () => {
      const { addFavourite } = useAgentPreferencesStore.getState();
      for (let i = 0; i < 25; i += 1) {
        addFavourite(TENANT, `agent-${i}`);
      }

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toHaveLength(20);
    });

    it('preserves insertion order', () => {
      const { addFavourite } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-a');
      addFavourite(TENANT, 'agent-b');
      addFavourite(TENANT, 'agent-c');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-a', 'agent-b', 'agent-c']);
    });
  });

  describe('removeFavourite', () => {
    it('removes an agent from favourites', () => {
      const { addFavourite, removeFavourite } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      addFavourite(TENANT, 'agent-2');
      removeFavourite(TENANT, 'agent-1');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-2']);
    });

    it('is a no-op for non-existent agent', () => {
      const { addFavourite, removeFavourite } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      removeFavourite(TENANT, 'agent-999');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-1']);
    });
  });

  describe('reorderFavourites', () => {
    it('moves an item forward', () => {
      const { addFavourite, reorderFavourites } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'a');
      addFavourite(TENANT, 'b');
      addFavourite(TENANT, 'c');
      reorderFavourites(TENANT, 0, 2);

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['b', 'c', 'a']);
    });

    it('moves an item backward', () => {
      const { addFavourite, reorderFavourites } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'a');
      addFavourite(TENANT, 'b');
      addFavourite(TENANT, 'c');
      reorderFavourites(TENANT, 2, 0);

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['c', 'a', 'b']);
    });
  });

  describe('trackAgentInteraction', () => {
    it('adds an agent to recent list', () => {
      useAgentPreferencesStore.getState().trackAgentInteraction(TENANT, 'agent-1');

      const recent = selectRecentAgents(useAgentPreferencesStore.getState(), TENANT);
      expect(recent).toHaveLength(1);
      expect(recent[0].agentId).toBe('agent-1');
    });

    it('moves existing agent to the front', () => {
      const { trackAgentInteraction } = useAgentPreferencesStore.getState();
      trackAgentInteraction(TENANT, 'agent-1');
      trackAgentInteraction(TENANT, 'agent-2');
      trackAgentInteraction(TENANT, 'agent-1');

      const recent = selectRecentAgents(useAgentPreferencesStore.getState(), TENANT);
      expect(recent).toHaveLength(2);
      expect(recent[0].agentId).toBe('agent-1');
      expect(recent[1].agentId).toBe('agent-2');
    });

    it('caps at 20 entries', () => {
      const { trackAgentInteraction } = useAgentPreferencesStore.getState();
      for (let i = 0; i < 25; i += 1) {
        trackAgentInteraction(TENANT, `agent-${i}`);
      }

      expect(selectRecentAgents(useAgentPreferencesStore.getState(), TENANT)).toHaveLength(20);
    });

    it('keeps the most recent entries when capped', () => {
      const { trackAgentInteraction } = useAgentPreferencesStore.getState();
      for (let i = 0; i < 25; i += 1) {
        trackAgentInteraction(TENANT, `agent-${i}`);
      }

      const recent = selectRecentAgents(useAgentPreferencesStore.getState(), TENANT);
      expect(recent[0].agentId).toBe('agent-24');
      expect(recent[19].agentId).toBe('agent-5');
    });
  });

  describe('cleanupStaleAgents', () => {
    it('removes deleted agents from favourites', () => {
      const { addFavourite, cleanupStaleAgents } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      addFavourite(TENANT, 'agent-2');
      addFavourite(TENANT, 'agent-3');

      cleanupStaleAgents(TENANT, new Set(['agent-1', 'agent-3']));

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-1', 'agent-3']);
    });

    it('removes deleted agents from recents', () => {
      const { trackAgentInteraction, cleanupStaleAgents } = useAgentPreferencesStore.getState();
      trackAgentInteraction(TENANT, 'agent-1');
      trackAgentInteraction(TENANT, 'agent-2');

      cleanupStaleAgents(TENANT, new Set(['agent-2']));

      const recent = selectRecentAgents(useAgentPreferencesStore.getState(), TENANT);
      expect(recent).toHaveLength(1);
      expect(recent[0].agentId).toBe('agent-2');
    });

    it('handles empty valid set by clearing all', () => {
      const { addFavourite, trackAgentInteraction, cleanupStaleAgents } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      trackAgentInteraction(TENANT, 'agent-1');

      cleanupStaleAgents(TENANT, new Set());

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual([]);
      expect(selectRecentAgents(useAgentPreferencesStore.getState(), TENANT)).toEqual([]);
    });
  });

  describe('tenant scoping', () => {
    it('keeps favourites separate per tenant', () => {
      const { addFavourite } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      addFavourite(TENANT_2, 'agent-2');

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual(['agent-1']);
      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT_2)).toEqual(['agent-2']);
    });

    it('keeps recents separate per tenant', () => {
      const { trackAgentInteraction } = useAgentPreferencesStore.getState();
      trackAgentInteraction(TENANT, 'agent-1');
      trackAgentInteraction(TENANT_2, 'agent-2');

      expect(selectRecentAgents(useAgentPreferencesStore.getState(), TENANT)).toHaveLength(1);
      expect(selectRecentAgents(useAgentPreferencesStore.getState(), TENANT)[0].agentId).toBe('agent-1');
      expect(selectRecentAgents(useAgentPreferencesStore.getState(), TENANT_2)[0].agentId).toBe('agent-2');
    });

    it('cleanup only affects the specified tenant', () => {
      const { addFavourite, cleanupStaleAgents } = useAgentPreferencesStore.getState();
      addFavourite(TENANT, 'agent-1');
      addFavourite(TENANT_2, 'agent-1');

      cleanupStaleAgents(TENANT, new Set());

      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT)).toEqual([]);
      expect(selectFavourites(useAgentPreferencesStore.getState(), TENANT_2)).toEqual(['agent-1']);
    });

    it('returns empty arrays for unknown tenant', () => {
      expect(selectFavourites(useAgentPreferencesStore.getState(), 'unknown')).toEqual([]);
      expect(selectRecentAgents(useAgentPreferencesStore.getState(), 'unknown')).toEqual([]);
    });
  });

  describe('selector reference stability', () => {
    it('returns the same favourites reference for unknown tenants across calls', () => {
      const state = useAgentPreferencesStore.getState();
      const first = selectFavourites(state, 'no-such-tenant');
      const second = selectFavourites(state, 'no-such-tenant');

      expect(first).toBe(second);
    });

    it('returns the same recent agents reference for unknown tenants across calls', () => {
      const state = useAgentPreferencesStore.getState();
      const first = selectRecentAgents(state, 'no-such-tenant');
      const second = selectRecentAgents(state, 'no-such-tenant');

      expect(first).toBe(second);
    });

    it('returns the same favourites reference across different unknown tenants', () => {
      const state = useAgentPreferencesStore.getState();
      const a = selectFavourites(state, 'tenant-x');
      const b = selectFavourites(state, 'tenant-y');

      expect(a).toBe(b);
    });

    it('returns the same recent agents reference across different unknown tenants', () => {
      const state = useAgentPreferencesStore.getState();
      const a = selectRecentAgents(state, 'tenant-x');
      const b = selectRecentAgents(state, 'tenant-y');

      expect(a).toBe(b);
    });
  });
});
