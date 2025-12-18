-- Migrate selected_tools data from old format to new format
-- Old: {"tool_names": [{"tool_name": "..."}]}
-- New: {"tools": [{"name": "..."}]}

UPDATE v2_agent
SET selected_tools = json_object(
    'tools',
    (
        SELECT json_group_array(
            json_object('name', json_extract(value, '$.tool_name'))
        )
        FROM json_each(json_extract(selected_tools, '$.tool_names'))
    )
)
WHERE json_extract(selected_tools, '$.tool_names') IS NOT NULL
  AND json_extract(selected_tools, '$.tools') IS NULL;
