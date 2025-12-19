# BIRD Module

Internal module for BIRD benchmark integration. For usage, see `docs/BIRD_CLI_GUIDE.md`.

## Components

- **`generation.py`**: Generate test threads and golden CSVs from BIRD data
- **`resolver.py`**: Resolve questions from Hugging Face, manage caching

## Programmatic Usage

```python
from pathlib import Path
from agent_platform.quality.bird import BirdDatasetGenerator, BirdDatasetResolver

# Resolve questions from HF
resolver = BirdDatasetResolver(cache_dir=Path("~/.sema4x/quality/bird"))
dataset_info = resolver.resolve_huggingface_questions(
    dataset_name="birdsql/bird_sql_dev_20251106",
    db_id="california_schools",
    db_path="./minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite",
)

# Generate test threads
generator = BirdDatasetGenerator(
    db_path=dataset_info["db_path"],
    questions_json_path=dataset_info["questions_json_path"],
    output_threads_dir=Path("./test-threads/@preinstalled-sql-generation"),
    db_id="california_schools",
)
generated, skipped = generator.generate_test_threads()
```

## Data Sources

| Source     | Location                   | Purpose                |
| ---------- | -------------------------- | ---------------------- |
| Questions  | Hugging Face (`birdsql/*`) | Test prompts, gold SQL |
| SQLite DBs | Google Drive minidev.zip   | Golden CSV generation  |
| PostgreSQL | Docker Compose stack       | Test execution         |
