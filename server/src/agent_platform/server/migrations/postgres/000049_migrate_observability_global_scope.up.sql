-- Migrate existing observability integrations to have global scope
-- This ensures pre-existing integrations continue to work after scope system introduction
INSERT INTO v2.integration_scopes (integration_id, agent_id, scope)
SELECT id, NULL, 'global'
FROM v2.integration
WHERE kind = 'observability'
  AND id NOT IN (SELECT integration_id FROM v2.integration_scopes)
ON CONFLICT DO NOTHING;

