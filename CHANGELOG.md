# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0](https://github.com/ayim/taubench-modern/compare/v0.3.0...v0.4.0) (2026-02-27)


### Features

* add auto-discovery for community-contributed experimental domains ([#160](https://github.com/ayim/taubench-modern/issues/160)) ([c2139e8](https://github.com/ayim/taubench-modern/commit/c2139e8840af55148e17e18b6938b3f6a0aaacc6))


### Bug Fixes

* Move raw_content_blocks/raw_output_items to AssistantMessage only ([1eaff8c](https://github.com/ayim/taubench-modern/commit/1eaff8cc43f5812e531f23120837de596522a324))
* update leaderboard submission validation and clarify submission types ([#155](https://github.com/ayim/taubench-modern/issues/155)) ([917227c](https://github.com/ayim/taubench-modern/commit/917227cedf029f1a659e339a860c738a530fd20e))
* Use litellm model_cost registry for Bedrock cost fallback ([09d8696](https://github.com/ayim/taubench-modern/commit/09d86963b1bc7f5937c2253f76b86d2a2eff5552))

## [0.3.0](https://github.com/ayim/taubench-modern/compare/v0.2.0...v0.3.0) (2026-01-26)


### Features

* Add direct boto3 Bedrock support for Claude extended thinking ([a500120](https://github.com/ayim/taubench-modern/commit/a5001201f35e06f22ac823e282025018cfbee10f))
* Add raw payload retention for Anthropic extended thinking and OpenAI Responses API ([3e2352e](https://github.com/ayim/taubench-modern/commit/3e2352e8b074b254d59cb878d9d2fad37e2ef41d))
* Add token statistics to agent metrics display ([f5db10e](https://github.com/ayim/taubench-modern/commit/f5db10ee49babc217ad923e53fa95c7c57c0ac39))
* **experiment:** Add hyperparam sweep experimental code ([#77](https://github.com/ayim/taubench-modern/issues/77)) ([558e6cd](https://github.com/ayim/taubench-modern/commit/558e6cd066d7bf05db587fa2dc1509765c7d03bc))
* **gym:** add Gymnasium-compatible interface for RL training ([0ed2fd8](https://github.com/ayim/taubench-modern/commit/0ed2fd8d830a20657d89ae9c2efcc94838aa7129))
* Load dotenv early in CLI and improve LLM utils ([fc1d84d](https://github.com/ayim/taubench-modern/commit/fc1d84d61d496168334471ec894d618e507fb4fe))


### Bug Fixes

* add missing gymnasium dependency ([#91](https://github.com/ayim/taubench-modern/issues/91)) ([a969a0c](https://github.com/ayim/taubench-modern/commit/a969a0c0a29bc47ba8580107932f5298ee636045))
* Allow thinking config via llm_args instead of hardcoded flag ([a34cec2](https://github.com/ayim/taubench-modern/commit/a34cec291516b8ca0b9fa0d58b36b67069e85af4))
* communicate_info fixed to nl_assertions in Mock domain tasks ([#66](https://github.com/ayim/taubench-modern/issues/66)) ([702ee77](https://github.com/ayim/taubench-modern/commit/702ee77e497d89e9d8942ab7206c1a465b12e503))
* Improve pass^k calculation to handle all k values up to max trials ([54ad921](https://github.com/ayim/taubench-modern/commit/54ad9219bf003fcefc33c83f14c170e5bef033b3))
* Remove config.py from gitignore (required for imports) ([e991fb2](https://github.com/ayim/taubench-modern/commit/e991fb2bbc862889afc7a923ed2d084c41364408))


### Dependencies

* Update litellm and add boto3 for Claude/Bedrock support ([3a95cd0](https://github.com/ayim/taubench-modern/commit/3a95cd063d880e8f182b3c874deb0f307ac63461))

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.2.1] - 2025-11-07
### Added
- Gymnasium-compatible interface for RL training with `AgentGymEnv` and `UserGymEnv`
- Train/test task splits for all domains
- Interactive play mode (`tau2 play`) supporting both agent and user roles
- Possibility to strictly enforce communication protocol rules (e.g., no mixed messages with text and tool calls)

## [0.2.0] - 2025-10-06

### Added
- Web-based leaderboard system with interactive submission management
- GitHub Pages deployment for leaderboard with automated CI/CD
- Comprehensive submission validation and verification system
- Model comparison interface with performance metrics visualization
- Trajectory visualization in web interface
- Mobile-responsive leaderboard design
- Logo assets and branding for multiple LLM providers
- Live leaderboard deployment at tau-bench.com

### Changed
- Enhanced submission manifest structure
- Improved image handling and asset management
- Updated deployment workflow for better reliability

### Fixed
- Mobile view responsiveness issues
- Missing submissions from manifest
- Image path resolution for GitHub Pages deployment
- Base URL handling for subdirectory deployment

## [0.1.3] - 2025-08-26

### Fixed
- LLM arguments parsing and handling
- Removed default natural language assertion checks that were causing issues

## [0.1.2] - 2025-07-17

### Added
- `tau2 check-data` CLI command for verifying data directory setup
- Support for `TAU2_DATA_DIR` environment variable for non-editable installs
- Fallback to local source when data directory is not set
- `--num-tasks` CLI flag for limiting task count

### Changed
- Made `pip install -e .` the default installation method
- Improved task name display in CLI
- Enhanced data directory configuration flexibility

### Fixed
- Installation issues with data directory discovery
- Task filtering and display problems

## [0.1.1] - 2025-06-12

### Fixed
- Domain viewer CLI functionality
- `tau2 domain` command execution issues

## [0.1.0] - 2025-06-12

### Added
- Initial release of τ²-bench framework
- Support for multiple domains: mock, airline, retail, telecom
- Command-line interface with `tau2` command
- Agent evaluation system with LLM integration via LiteLLM
- User simulator for realistic conversation scenarios
- Environment system with domain-specific tools and policies
- Orchestration system for managing agent-user-environment interactions
- Comprehensive test suite
- Domain-specific documentation and API endpoints
- Experimental features: no-user mode, oracle-plan mode, workflow policies
- Support for ablation studies
- Interactive environment CLI for testing and debugging
- Caching system for LLM calls (Redis-based)
- Multi-trial evaluation with concurrent execution support

### Technical Details
- Python 3.10+ support
- FastAPI-based web services
- Pydantic data models
- Rich CLI with tabulated output
- Comprehensive logging with Loguru
- Performance metrics and visualization
- Configurable LLM backends
- Semantic versioning adoption

## Links
- [Repository](https://github.com/sierra-research/tau2-bench)
- [Leaderboard](https://tau-bench.com)
- [Paper](https://arxiv.org/abs/2506.07982)
- [Blog Post](https://sierra.ai/blog/benchmarking-agents-in-collaborative-real-world-scenarios)
