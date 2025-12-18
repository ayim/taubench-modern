-- Revert selected_tools data from new format back to old format
-- New: {"tools": [{"name": "..."}]}
-- Old: {"tool_names": [{"tool_name": "..."}]}

UPDATE v2."agent"
SET selected_tools = jsonb_build_object(
    'tool_names',
    (
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object('tool_name', tool_obj->>'name')
            ),
            '[]'::jsonb
        )
        FROM jsonb_array_elements(selected_tools->'tools') AS tool_obj
    )
)
WHERE selected_tools ? 'tools'
  AND NOT selected_tools ? 'tool_names';
