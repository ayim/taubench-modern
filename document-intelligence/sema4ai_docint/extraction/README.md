# doc-extraction

## First time setup

Make sure your local virutalenv is set up

```shell
$ uv sync
```

Create a `.env` file with your Sema4.ai API Key. This is the Sema4.ai-controlled key which authorizes you to access Sema4.ai-hosted services like Reducto.

```
SEMA4_REDUCTO_URL=https://backend.sema4ai.dev/reducto
SEMA4_REDUCTO_API_KEY=...
```

## Tests

```shell
$ make test
```

or simply

```shell
$ uv run pytest
```

### New tests

To add new extraction tests, add a new directory beneath `test/test-data/extraction` with a unique name. Inside this directory should be three files with these exact names:

1. `data.pdf`: a PDF which we will run extraction over
2. `schema.json`: a jsonschema object which describes `data.pdf`
3. `expected.json`: a JSON object which contains attributes that should be extracted from `data.pdf`

The framework will automatically run new tests over these file-triples which exist.
