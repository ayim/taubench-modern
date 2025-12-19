# BIRD Benchmark CLI Guide

This guide explains how to import and run BIRD benchmark tests using the quality CLI.

## Architecture

**BIRD benchmark uses a split architecture:**

| Component     | Source                                                                                             | Purpose                              |
| ------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Questions/SQL | [Hugging Face](https://huggingface.co/birdsql/datasets)                                            | Latest questions, gold SQL, evidence |
| SQLite DBs    | [Google Drive minidev.zip](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view) | Generate golden CSV files            |
| PostgreSQL    | Docker Compose stack                                                                               | Test execution (persistent)          |

## Quick Start

### 1. Install Dependencies

```bash
make sync # from repo root
```

### 2. Download BIRD Data

Download [minidev.zip](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view) and extract:

```bash
mkdir -p ~/.sema4x/quality/bird-data
cd ~/.sema4x/quality/bird-data
unzip ~/Downloads/minidev.zip
```

You should have:

```
~/.sema4x/quality/bird-data/minidev/
├── MINIDEV/
│   └── dev_databases/          # SQLite DBs (11 databases)
└── MINIDEV_postgresql/
    └── BIRD_dev.sql            # PostgreSQL dump (955MB)
```

### 3. Start PostgreSQL Stack

```bash
# First time: ~5 min (waits automatically for 50+ tables to load)
# Use --sql-file to specify a different SQL file path if needed
quality-test bird docker up

# Subsequent starts: instant (data persisted)
quality-test bird docker up
```

### 4. Import Tests

If tests do not exist for a given database, you can import them using the `quality-test bird import` command.

```bash
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite \
  --db-id california_schools
```

> [!NOTE]
> You can pass a different dataset ID to download from Hugging Face by passing the `--hf-dataset` flag.

### 5. Create SDMs

Before running tests, you need to create an SDM for the database. There are two ways to do this:

#### Option A: Automatic Generation (Recommended)

Use the `--generate-sdm` flag with `bird import` to automatically generate an SDM using the agent server:

```bash
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite \
  --db-id california_schools \
  --generate-sdm
```

This will:

- Create a data connection to the BIRD PostgreSQL database
- Inspect tables and columns automatically
- Use CSV context files from `database_description/` as business context
- Generate an enhanced SDM using the LLM (via `@preinstalled-sql-generation` agent)
- Save `sdm.yml` and `config.yml` to `test-data/sdms/bird_{db_id}/`

**Prerequisites:**

- BIRD docker stack running (`quality-test bird docker up`)
- Agent server running with `@preinstalled-sql-generation` agent deployed

#### Option B: Manual Generation

Use SPAR UI or Studio to generate an SDM. Connect to the BIRD database and reference the Excel/CSV files in the `database_description/` folder for business context.

Save the new SDM in `test-data/sdms/` directory similar to the existing california_schools folder.

### 6. Run Tests

The `--tests` flag supports exact match or prefix match. The `--difficulty` flag filters by BIRD difficulty level:

```bash
quality-test run --tests=bird-california-schools-001  # Single test (exact)
quality-test run --tests=bird-california-schools      # All california_schools tests (prefix)
quality-test run --tests=bird-                        # All BIRD tests (prefix)

# Filter by difficulty (simple, moderate, challenging)
quality-test run --tests=bird- --difficulty=simple
quality-test run --tests=bird- --difficulty=moderate
quality-test run --tests=bird- --difficulty=challenging
```

---

## Command Reference

### `quality-test bird docker`

Manage the BIRD PostgreSQL stack.

```bash
quality-test bird docker {up|down|ps|logs} [OPTIONS]
```

| Action | Description                                |
| ------ | ------------------------------------------ |
| `up`   | Start stack (waits for healthy by default) |
| `down` | Stop stack (keeps data)                    |
| `ps`   | Show status                                |
| `logs` | Show logs                                  |

**Options:**

| Option             | Description                                                 |
| ------------------ | ----------------------------------------------------------- |
| `--sql-file PATH`  | Path to `BIRD_dev.sql` (or set `BIRD_DEV_SQL_PATH` env var) |
| `--wait/--no-wait` | Wait for healthy after `up` (default: wait)                 |
| `-v, --volumes`    | Remove volumes on `down` (destructive)                      |

**Examples:**

```bash
quality-test bird docker up                    # Start and wait for healthy
quality-test bird docker up --no-wait          # Start without waiting
quality-test bird docker ps                    # Check status
quality-test bird docker down                  # Stop (keeps data)
quality-test bird docker down -v               # Stop and delete all data
```

### `quality-test bird list-dbs`

List available database IDs in a Hugging Face dataset.

```bash
quality-test bird list-dbs [OPTIONS]
```

**Options:**

| Option          | Default                         | Description          |
| --------------- | ------------------------------- | -------------------- |
| `--hf-dataset`  | `birdsql/bird_sql_dev_20251106` | Hugging Face dataset |
| `--home-folder` | `~/.sema4x`                     | Cache directory      |

**Example output:**

```text
✅ Found 11 databases:
   • california_schools
   • card_games
   • financial
   • ...
```

### `quality-test bird import`

Import BIRD benchmark dataset and generate test threads with golden CSVs.

```bash
quality-test bird import [OPTIONS]
```

**Required:**

| Option           | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| `--db-path PATH` | Path to SQLite file OR `dev_databases` directory (imports all) |

**Optional:**

| Option                               | Default                                     | Description                                  |
| ------------------------------------ | ------------------------------------------- | -------------------------------------------- |
| `--db-id TEXT`                       | (auto)                                      | Database ID (required for single file)       |
| `--hf-dataset TEXT`                  | `birdsql/bird_sql_dev_20251106`             | Hugging Face dataset for questions           |
| `--questions-json PATH`              | (none)                                      | Local questions JSON (alt to HF)             |
| `--test-prefix`                      | `bird-{db_id}`                              | Prefix for test directories                  |
| `--sdm-name`                         | `bird_{db_id}`                              | SDM reference name                           |
| `--output-threads-dir`               | `test-threads/@preinstalled-sql-generation` | Output directory                             |
| `--force-download`                   | False                                       | Re-download from HF even if cached           |
| `--skip-existing/--no-skip-existing` | True                                        | Skip existing test directories               |
| `--generate-sdm`                     | False                                       | Auto-generate SDM using agent server         |
| `--agent-id`                         | (auto-detect)                               | Agent ID for SDM generation (if not default) |

**Examples:**

```bash
# Import ALL databases at once (discovers subdirectories with .sqlite files)
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases

# Import a single database
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite \
  --db-id california_schools

# Force regenerate existing tests
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite \
  --db-id california_schools \
  --no-skip-existing

# Import with automatic SDM generation
quality-test bird import \
  --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite \
  --db-id california_schools \
  --generate-sdm
```

---

## Output Structure

Import generates:

```text
quality/test-threads/@preinstalled-sql-generation/
├── bird-california-schools-001/
│   ├── thread.yml
│   └── golden_27.csv
├── bird-california-schools-002/
│   ├── thread.yml
│   └── golden_28.csv
└── ...
```

SDM packages are pre-configured in `test-data/sdms/` with `config.yml` pointing to the compose stack.

---

## Environment Variables

| Variable            | Default     | Description            |
| ------------------- | ----------- | ---------------------- |
| `BIRD_DEV_SQL_PATH` | (none)      | Path to `BIRD_dev.sql` |
| `BIRD_PG_PORT`      | `5433`      | PostgreSQL port        |
| `BIRD_PG_HOST`      | `localhost` | PostgreSQL host        |
| `BIRD_PG_DATABASE`  | `bird`      | Database name          |
| `BIRD_PG_USER`      | `postgres`  | Username               |
| `BIRD_PG_PASSWORD`  | `postgres`  | Password               |

---

## Caching

Questions from Hugging Face are cached at:

```text
~/.sema4x/quality/bird/{dataset_name}/{db_id}/questions.json
```

Use `--force-download` to refresh.

---

## Future: SDM Generation

The minidev folder contains metadata useful for SDM generation:

- **Column descriptions**: `dev_databases/{db}/database_description/*.csv`
- **Schema metadata**: `dev_tables.json` (tables, columns, foreign keys)

These can be used to automate SDM YAML generation in the future.

---

## Troubleshooting

| Error                          | Solution                                 |
| ------------------------------ | ---------------------------------------- |
| "datasets library is required" | `uv pip install -e ".[bird]"`            |
| "BIRD_DEV_SQL_PATH not set"    | Use `--sql-file` or set env var          |
| Port 5433 in use               | Set `BIRD_PG_PORT` to another port       |
| "No questions found for db_id" | Run `bird list-dbs` to see available IDs |
| Slow first startup             | Normal - loading 955MB takes ~5 min      |

---

## References

- [BIRD Benchmark](https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/bird)
- [Hugging Face Datasets](https://huggingface.co/birdsql/datasets)
- [Database Files (Google Drive)](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view)
