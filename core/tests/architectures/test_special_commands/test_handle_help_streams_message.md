Special Commands

### /debug
Dump internal info (no model call).

### /data
Show data frames, semantic models, and data context prompt.

### /help
Show this help.

### /toggle <memory|data-frames> <on|off>
Quick toggle for common agent settings.

### /set agent_settings.<path> <value>
Set arbitrary agent_settings value. Value parsed as JSON if possible,
else used as string.

### /unset agent_settings.<path>
Remove a setting at the given path.

Examples:
- /toggle memory on
- /toggle data-frames off
- /set agent_settings.temperature 0.4
- /set agent_settings.execution.max_iterations 12
- /unset agent_settings.integrations.enable_web_search
