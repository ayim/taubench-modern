# agent.cli changelog

## Unreleased

- For action build and extract ensure consistent file naming conventions with action server
- Use existing action naming from the agent-spec if it's available when creating or updating the action folder for the agent project

## 1.3.4 - 2025-06-13
- Fixed agent-cli moving remote Action Packages to MyActions & not keep them in the correct organization

## 1.3.3 - 2025-06-11
- Fixed `WorkerConfig` being added to agent metadata when Agent mode is `conversational`

## 1.3.2 - 2025-06-03
- Improved change detection for Action Packages - changes now follow exclusion rules from Action Package `package.yaml` instead of ones from `agent-spec.yaml`
- Add new flag '--ignore-actions' for the validation command to skip validating the action packages

## 1.3.1 - 2025-05-23
- Fixed and simplified `agent delete` command
- Added `mcp_servers` null payload handling

## 1.3.0 - 2025-05-22

- Added MCP Server support in `agent-cli agent update` `agent-cli agent create` the payload now McpServers list next to ActionPackages
  - McpServer item only has `name` and `url` fields

## 1.2.0 - 2025-05-22

- Added file change detection based on modify file timestamp for Action Packages files
- Improved `agent get` command to read Agent Projects concurrently
- Added `--agent-project-settings-path` input parameter to connect Agent Project and deployed Agents based on the ID

## 1.1.6 - 2025-05-20

- Fixed `WorkerConfig` change detection when Agent Server returns it as an empty object
- Fixed changes detection to ignore `Model.Name` property (v2 no longer returns it)

## 1.1.5 - 2025-05-06

- Fixed model name change detection for Azure LLM

## 1.1.4 - 2025-05-06

- Fixed changes detection for Agent metadata

## 1.1.3 - 2025-05-06

- Fixed `--ignore-missing` flag to allow to ignore existing Agent Project directory, but with missing `agent-spec.yaml`

## 1.1.2 - 2025-05-05

- adding `--ignore-missing` flag to `agent get`, allowing to skip missing Agent Projects without throwing error

## 1.1.1 - 2025-04-30

- adding `--agent-id` param allowing to delete deployed Agent from Agent Server without providing Project path

## 1.1.0 - 2025-04-29

- Introduces new main command `agent`
  - `agent` command has four subcommands - `get`, `create`, `update` and `delete` responsible for managing deployed Agents and Agent Projects
- adds `--only-deployed` and `--only-project` flags to `agent delete` command
- adds `changes` field to Agent Projects response

## 1.0.6 - 2025-04-29

- Fixes issue with runbook file not being overwritten upon updating Agent Project
- Fixes issue with creating "version directories" when exporting an Agent Project

## 1.0.5 - 2025-04-22

- `project deploy` subcommand
- `agent-client-go` upgrade to v0.1.2

## 1.0.4 - 2025-04-07

- Logging cleanup for export as a hot-fix
- Fixed package import command backwards compatibility issue with the temporary directory

## 1.0.3 - 2025-04-04 - BROKEN

2025-04-07: Broken import command

- Logging cleanup for export
- In progress implementations:
  - Adding commands "project update", "project delete", "project cleanup" preparing for managing agent projects in the file system.
- Added platform specific smoke-test on GHA

## 1.0.2 - 2025-03-20

- Fixed export failing on `.DS_Store` or any unwanted files in the export structure
  - Improved logic and logging
- Agent CLI no longer logs usage on errors, making it easier to find the errors from support logs.

## 1.0.1 - 2025-03-13

- Release the fixes to `validate` command
- Update the agent template coming from `project new`

## 1.0.0 - 2025-03-10

- Version bump to v1.0.0
- Added developer scripts

## 0.2.4

- Add ability to exclude files from the agent package via `exclude` section in agent-spec.yaml
- Fix for exporting knowledge files with erroneous `file://` prefix
- Add support for `excludes` in agent-spec.yaml to exclude files from agent packaging
- Add new command: "project get" that can return all local and remote agents
- Extend the "project new" command to accept agent as a payload and optial deploy parameter to push the agent to the agent-server

## 0.2.3

- Macos ARM support

## 0.2.2

- Fix: The output paths in agent package metadata in linux format

## 0.2.1

- x-operation-kind backwards compatibility for older packages.

## 0.0.29

- Fixed issue with `.git` folder getting into the Agent Package (Agent built in Git project root folder failing)

## 0.0.19

- Fixed the agent-spec.yaml action paths Windows problem in: `export`, `extract`, `metadata`
- Added error log idenfifiers for: `export`, `extract`, `metadata`

## 0.0.18

- Fixed `agent-cli package build` action paths problem in Windows machines.
- Added logging on `agent-cli package build`
