"""Configuration system for Agent Platform.

The configuration system provides a centralized mechanism for defining, loading,
and managing configuration values across the Agent Platform. It supports automatic
discovery, validation, persistence, and overriding of configurations.

## Key Components

### Configuration Base Class

The `Configuration` class serves as the base for all configuration classes.
Configurations are defined as dataclasses with type hints and default values,
and can include metadata like descriptions and environment variable mappings.

### Configuration Registry

Configuration classes are automatically registered during import, making
them discoverable by the configuration manager.

### Configuration Manager

The `ConfigurationManager` in the server package handles loading and persisting
configurations from various sources, following a precedence order:

1. Command line arguments (highest priority)
2. Environment variables
3. Configuration file values (JSON/YAML)
4. Default values (lowest priority)

## Usage Examples

### Defining a Configuration

```python
from dataclasses import dataclass, field
from pathlib import Path
from agent_platform.core.configurations import Configuration

@dataclass
class SystemPaths(Configuration):
    \"\"\"Configuration for system paths.\"\"\"

    data_dir: Path = field(
        default=Path("/path/to/default/data"),
        metadata={
            "description": "Base directory for data storage",
            "env_vars": ["AGENT_PLATFORM_DATA_DIR", "DATA_DIR"],
        }
    )
    log_dir: Path = field(
        default=Path("/path/to/default/logs"),
        metadata={
            "description": "Directory for log files",
            "env_vars": ["AGENT_PLATFORM_LOG_DIR", "LOG_DIR"],
        }
    )
```

### Accessing Configuration Values

```python
# Use class-level attribute access
data_dir = SystemPaths.data_dir

# Or create a fresh default instance
default_paths = SystemPaths.default()
```

### Working with the Configuration Manager

```python
from agent_platform.server.configuration_manager import get_configuration_manager

# Get the configuration manager
manager = get_configuration_manager()

# Update a configuration
new_paths = SystemPaths(data_dir=Path("/custom/data"))
manager.update_configuration(SystemPaths, new_paths)

# Get complete configuration data
config_data = manager.get_complete_config()
```

## Configuration File Format

Configurations are stored in a JSON or YAML file with a hierarchical structure:

```yaml
agent_platform.server.constants.SystemPaths:
  data_dir: /path/to/data
  log_dir: /path/to/logs

agent_platform.server.constants.SystemConfig:
  db_type: sqlite
  log_level: INFO
```

Each configuration class is stored under a key representing its full module
path plus class name, with field values as nested properties.
"""

from agent_platform.core.configurations.base import (
    Configuration,
    FieldMetadata,
)
from agent_platform.core.configurations.parsers import (
    AstParserMixin,
    BoolParser,
    EnumParser,
    FloatParser,
    IntParser,
    LiteralParser,
    NestedListParser,
    NestedMappingParser,
    PathParser,
    StrParser,
    get_parser_for_field,
    initialize_parsers,
    parse_field_value,
)
from agent_platform.core.configurations.representers import (
    BUILT_IN_REPRESENTERS,
    PathRepresenter,
    get_representer_for_field,
    represent_field_value,
)

__all__ = [
    "BUILT_IN_REPRESENTERS",
    "AstParserMixin",
    "BoolParser",
    "Configuration",
    "EnumParser",
    "FieldMetadata",
    "FloatParser",
    "IntParser",
    "LiteralParser",
    "NestedListParser",
    "NestedMappingParser",
    "PathParser",
    "PathRepresenter",
    "StrParser",
    "get_parser_for_field",
    "get_representer_for_field",
    "initialize_parsers",
    "parse_field_value",
    "represent_field_value",
]
