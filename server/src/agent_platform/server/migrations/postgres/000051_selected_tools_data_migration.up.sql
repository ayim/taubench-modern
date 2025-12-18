-- Migrate selected_tools data from old format to new format
-- Old: {"tool_names": [{"tool_name": "..."}]}
-- New: {"tools": [{"name": "..."}]}

UPDATE v2."agent"
SET selected_tools = jsonb_build_object(
    'tools',
    (
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object('name', tool_obj->>'tool_name')
            ),
            '[]'::jsonb
        )
        FROM jsonb_array_elements(selected_tools->'tool_names') AS tool_obj
    )
)
WHERE selected_tools ? 'tool_names'
  AND NOT selected_tools ? 'tools';
