-- The up migration targets situations where agent server upgrades were accidentally applied
-- Note that we don't do this for sqlite. If studio were to get into the same state,
-- a factory reset would be the best way to recover.
BEGIN;
UPDATE agent
SET advanced_config = jsonb_set(
    advanced_config::jsonb,
    '{architecture}',
    '"agent"'
)
WHERE advanced_config->>'architecture' NOT IN (
    'agent',
    'plan_execute',
    'multi_agent_hierarchical_planning'
);
COMMIT;