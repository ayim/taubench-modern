-- Revert selected_tools data from new format back to old format
-- New: {"tools": [{"name": "..."}]}
-- Old: {"tool_names": [{"tool_name": "..."}]}

UPDATE v2_agent
SET selected_tools = json_object(
    'tool_names',
    (
        SELECT json_group_array(
            json_object('tool_name', json_extract(value, '$.name'))
        )
        FROM json_each(json_extract(selected_tools, '$.tools'))
    )
)
WHERE json_extract(selected_tools, '$.tools') IS NOT NULL
  AND json_extract(selected_tools, '$.tool_names') IS NULL;
