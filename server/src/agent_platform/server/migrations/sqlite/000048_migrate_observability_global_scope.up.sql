-- Migrate existing observability integrations to have global scope
-- This ensures pre-existing integrations continue to work after scope system introduction
INSERT INTO v2_integration_scopes (integration_id, agent_id, scope)
SELECT id, NULL, 'global'
FROM v2_integration
WHERE kind = 'observability'
  AND id NOT IN (SELECT integration_id FROM v2_integration_scopes)
ON CONFLICT DO NOTHING;
