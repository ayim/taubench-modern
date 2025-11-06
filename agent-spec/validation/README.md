## Spec Validation

Spec validation is used to validate that the agent spec is correct
and the examples in the repo actually match the spec.

## Installation and running the tests

1. `cd /spec_validation`
2. Run: `./developer/develop.sh` / `developer\develop.bat`
   - You can re-use previously built dev. env or get a clean one.
   - Dependencies in [develop.yaml](./developer/develop.yaml)
   - Sets you terminal to the dev. env.
3. Run `uv sync`
4. Run `pytest`

## Change in agent-spec content

1. Update the spec JSON change to [agent-package-specification-v2.1.json](../docs/v2.1/agent-package-specification-v2.1.json) and [validatespecv2_1.go](../cli/cmd/validatespecv2_1.go)
2. Run `pytest --force-regen` to regenerate templates
