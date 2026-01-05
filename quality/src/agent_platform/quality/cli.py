from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlencode, urlparse

import click
import httpx
import structlog
import yaml
from dotenv import load_dotenv

from agent_platform.quality.bird import BirdDatasetGenerator, BirdDatasetResolver
from agent_platform.quality.models import ThreadResult
from agent_platform.quality.oauth import OAuthRedirectServer
from agent_platform.quality.reporter import QualityReporter
from agent_platform.quality.runner import QualityTestRunner
from agent_platform.quality.simulator import Simulator, Trace

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@dataclass
class OAuthProviderConfig:
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str


@dataclass
class Context:
    # TODO it is used if there is an already running agent server
    # since we now can run as executable we should also verify
    # if the running server has been started with the right executable
    agent_server_url: str
    agents_dir: Path
    threads_dir: Path
    oauth: dict[str, OAuthProviderConfig]
    verbose: bool
    quality_folder: Path
    is_in_github_actions: bool


def setup_logging(verbose: bool = False):
    """Setup structured logging."""
    # Clear any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    if verbose:
        # JSON structured logging for verbose mode
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.format_exc_info,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        handler = logging.StreamHandler()
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
            )
        )

        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)
    else:
        # Simple logging for normal mode
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.format_exc_info,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        handler = logging.StreamHandler()
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(),
            )
        )

        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)


@click.group()
@click.option(
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Sema4ai home folder",
)
@click.option(
    "--server-url",
    default="http://localhost:8000",
    envvar="AGENT_SERVER_URL",
    help="Agent server URL",
)
@click.option(
    "--test-threads-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("quality/test-threads"),
    help="Directory containing test thread YAML files",
)
@click.option(
    "--test-agents-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("quality/test-agents"),
    help="Directory containing agent ZIP packages",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--show-env", is_flag=True, help="Show loaded .env file location")
@click.pass_context
def cli(
    ctx,
    home_folder: Path,
    server_url: str,
    test_threads_dir: Path,
    test_agents_dir: Path,
    verbose: bool,
    show_env: bool,
):
    """Quality testing CLI for agent platform."""
    if ctx.invoked_subcommand == "init":
        return

    setup_logging(verbose)

    if verbose or show_env:
        load_env_file(verbose=True)
    else:
        load_env_file(verbose=False)

    home_folder = home_folder if home_folder is not None else Path.home() / ".sema4x"
    quality_folder = home_folder / "quality"

    if not quality_folder.exists():
        raise ValueError(f"Cannot find quality folder in {home_folder}. Did you run 'init'?")

    def load_config():
        config_file = quality_folder / "config.yaml"

        with open(config_file) as f:
            return yaml.safe_load(f)

    config = load_config()

    ctx.obj = Context(
        agent_server_url=server_url,
        quality_folder=quality_folder,
        agents_dir=test_agents_dir,
        threads_dir=test_threads_dir,
        oauth={
            provider: OAuthProviderConfig(
                client_id=data["client_id"],
                client_secret=data["client_secret"],
                auth_url=data["auth_url"],
                token_url=data["token_url"],
                redirect_uri=data["redirect_uri"],
            )
            for provider, data in config["oauth"].items()
        },
        verbose=verbose,
        is_in_github_actions=os.getenv("GITHUB_ACTIONS") == "true",
    )


@cli.command()
@click.option(
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Home folder for Sema4ai",
)
async def init(home_folder):
    """Prepare the environment."""
    if home_folder is None:
        user_home_folder = Path.home()
        home_folder = user_home_folder / ".sema4x"

    quality_folder = home_folder / "quality"
    quality_folder.mkdir(parents=True, exist_ok=False)

    default_config = {
        "oauth": {},
    }
    config_file = quality_folder / "config.yaml"
    if not config_file.exists():
        with open(config_file, "w") as file:
            yaml.dump(default_config, file, default_flow_style=False)

    click.echo(f"✅ Quality tool inititialized at {quality_folder}")


@cli.command()
@click.pass_obj
async def check_server(ctx: Context):
    """Check if the agent server is available."""
    server_url = ctx.agent_server_url

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{server_url}/api/v2/health", timeout=5.0)
            if response.status_code == HTTPStatus.OK:
                click.echo(f"✅ Agent server is available at {server_url}")
                return True
            else:
                click.echo(f"❌ Agent server returned status {response.status_code}")
                return False
    except Exception as e:
        click.echo(f"❌ Failed to connect to agent server: {e}")
        return False


@cli.command()
@click.pass_obj
def list_agents(ctx: Context):
    """List available agent packages."""

    runner = QualityTestRunner(
        datadir=ctx.quality_folder,
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        agent_server_version=None,
    )

    agents = runner.discover_agents()

    if not agents:
        click.echo("No agent packages found.")
        return

    click.echo(f"Found {len(agents)} agent packages:")
    for agent in agents:
        click.echo(f"  • {agent.name} ({agent.zip_path})")


@cli.command()
@click.argument("agent_name", required=False)
@click.pass_obj
def list_tests(ctx: Context, agent_name: str | None):
    """List available test cases, optionally filtered by agent."""
    runner = QualityTestRunner(
        datadir=ctx.quality_folder,
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        agent_server_version=None,
    )

    test_cases = runner.discover_test_cases(agent_name)

    if not test_cases:
        if agent_name:
            click.echo(f"No test cases found for agent: {agent_name}")
        else:
            click.echo("No test cases found.")
        return

    if agent_name:
        click.echo(f"Found {len(test_cases)} test cases for agent {agent_name}:")
    else:
        click.echo(f"Found {len(test_cases)} test cases:")

    for test_case in test_cases:
        click.echo(f"  • {test_case.name} ({test_case.file_path})")
        if test_case.evaluations:
            click.echo(f"    Evaluations: {len(test_case.evaluations)}")
            for evaluation in test_case.evaluations:
                click.echo(f"      - {evaluation.kind}")


@cli.command()
@click.option("--detailed", is_flag=True, help="Show detailed evaluation results")
@click.option("--platform-summary", is_flag=True, help="Show platform-focused summary")
@click.option(
    "--max-concurrency",
    default=10,
    type=int,
    help="Maximum number of concurrent test executions across all agents",
)
@click.option(
    "--selected-agents",
    default="",
    type=str,
    help="List of agents to run tests for (if not provided, all agents will be run)",
)
@click.option(
    "--agent-server-version",
    required=False,
    type=str,
    help="Agent server version. If none is provided, the version on the current branch is used",
)
@click.option(
    "--agent-arch",
    required=False,
    type=str,
    help=(
        "Override the agent architecture plugin name for testing, e.g. 'agent_platform.architectures.experimental_1'"
    ),
)
@click.option(
    "--platform",
    required=False,
    type=str,
    help="Run tests only for this target platform (e.g. 'groq', 'azure').",
)
@click.option(
    "--tests",
    required=False,
    default="",
    type=str,
    help="Comma-separated list of test thread names to run (matches YAML 'name').",
)
@click.option(
    "--difficulty",
    required=False,
    type=str,
    help="Filter tests by difficulty (BIRD: simple, moderate, challenging).",
)
@click.option(
    "--export-results",
    "export_results_path",
    default=None,
    is_flag=False,
    flag_value="",  # Empty string when used as flag without value
    help="Export results to stable JSON. Optionally specify output path, otherwise uses default location.",
)
@click.pass_obj
async def run(
    ctx: Context,
    detailed: bool,
    platform_summary: bool,
    max_concurrency: int,
    selected_agents: str,
    agent_server_version: str | None,
    agent_arch: str | None,
    platform: str | None,
    tests: str,
    difficulty: str | None,
    export_results_path: str | None,
):
    """Run quality tests for agents."""
    # Capture the command that was run for export metadata
    command_args = " ".join(sys.argv)

    # Handle export_results_path:
    # - None: don't export (flag not used)
    # - "" (empty): export with default path (flag used without value)
    # - "/path/to/file": export to specific path
    export_path: Path | None = None
    if export_results_path == "":
        # Flag used without value - generate default path
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        export_path = ctx.quality_folder / "quality_results" / f"results_{timestamp}.json"
    elif export_results_path is not None:
        # Specific path provided
        export_path = Path(export_results_path)

    runner = QualityTestRunner(
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        datadir=ctx.quality_folder,
        agent_server_version=agent_server_version,
        is_in_github_actions=ctx.is_in_github_actions,
        agent_architecture_name_override=agent_arch,
        export_results_path=export_path,
        command_args=command_args,
    )

    reporter = QualityReporter()

    try:
        filters_desc = []
        if platform:
            filters_desc.append(f"platform={platform}")
        if difficulty:
            filters_desc.append(f"difficulty={difficulty}")
        filters_str = f", {', '.join(filters_desc)}" if filters_desc else ""

        click.echo(f"🚀 Running tests for all agents (max {max_concurrency} concurrent tests{filters_str})")
        tests_filter = [test.strip() for test in tests.split(",") if test.strip()]
        all_results = await runner.run_tests_for_all_agents_fully_parallel(
            selected_agents=[selected.strip() for selected in selected_agents.split(",") if selected.strip()],
            max_concurrency=max_concurrency,
            platform_filter=platform,
            tests_filter=tests_filter if tests_filter else None,
            difficulty_filter=difficulty,
        )

        # Report results
        if detailed:
            reporter.report_detailed_results(all_results)
        elif platform_summary:
            reporter.report_platform_summary(all_results)
        else:
            reporter.report_results(all_results)

        results_dir = runner.results_manager.get_results_dir()
        click.echo(f"💾 Results automatically saved to {results_dir}")

        def any_failures(results: dict[str, list[ThreadResult]]) -> bool:
            """Return True if at least one thread list is empty or if at least one failed."""
            return any(
                not thread_list or any(not thread.success for thread in thread_list) for thread_list in results.values()
            )

        if any_failures(all_results):
            click.echo("❌ Some tests failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error running test suite: {e}")
        if ctx.verbose:
            import traceback

            traceback.print_exc()
        raise click.Abort() from None


@cli.command()
@click.argument("old_results", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("new_results", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def compare(old_results: Path, new_results: Path):
    """Compare two test run results and show differences.

    Arguments:
        OLD_RESULTS: Path to the older results JSON file
        NEW_RESULTS: Path to the newer results JSON file

    Example:
        quality-test compare results_2026-01-04_10-00-00.json results_2026-01-04_14-00-00.json
    """
    from agent_platform.quality.compare import (
        ResultsComparator,
        format_comparison_line,
        load_results,
    )

    try:
        # Load both result files
        click.echo(f"Loading old results from: {old_results}")
        old = load_results(old_results)

        click.echo(f"Loading new results from: {new_results}")
        new = load_results(new_results)

        # Create comparator
        comparator = ResultsComparator(old, new)

        # Print summaries
        click.echo("\n" + "=" * 80)
        click.echo("OLD: " + comparator.get_summary_line(old))
        click.echo("NEW: " + comparator.get_summary_line(new))
        click.echo("=" * 80)

        # Compare tests
        comparisons = comparator.compare()

        # Count changes
        changed = [c for c in comparisons if c.status_changed and c.old_status and c.new_status]
        improved = [c for c in changed if c.improved]
        regressed = [c for c in changed if c.regressed]
        other_changes = [c for c in changed if not c.improved and not c.regressed]

        if not changed:
            click.echo("\n✨ No test status changes detected!")
        else:
            click.echo(f"\n📊 Test Changes: {len(changed)} total")

            if improved:
                click.echo(f"\n✅ Improved ({len(improved)}):")
                for comp in improved:
                    click.echo(format_comparison_line(comp))

            if regressed:
                click.echo(f"\n❌ Regressed ({len(regressed)}):")
                for comp in regressed:
                    click.echo(format_comparison_line(comp))

            if other_changes:
                click.echo(f"\n🔄 Other Changes ({len(other_changes)}):")
                for comp in other_changes:
                    click.echo(format_comparison_line(comp))

        # Report tests only in one run
        only_in_old = comparator.get_only_in_old()
        only_in_new = comparator.get_only_in_new()

        if only_in_old:
            click.echo(f"\n🗑️  Tests only in OLD ({len(only_in_old)}):")
            for key in only_in_old:
                click.echo(f"  - {key}")

        if only_in_new:
            click.echo(f"\n✨ Tests only in NEW ({len(only_in_new)}):")
            for key in only_in_new:
                click.echo(f"  - {key}")

        # Exit with error if there were regressions
        if regressed:
            click.echo("\n❌ Test regressions detected!", err=True)
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(f"❌ Error: Could not find file: {e}", err=True)
        raise click.Abort() from None
    except json.JSONDecodeError as e:
        click.echo(f"❌ Error: Invalid JSON in results file: {e}", err=True)
        raise click.Abort() from None
    except Exception as e:
        click.echo(f"❌ Error comparing results: {e}", err=True)
        import traceback

        traceback.print_exc()
        raise click.Abort() from None


@cli.command()
@click.pass_obj
async def oauth(ctx: Context):
    """Obtain access token for oauth connections used in tests."""

    # TODO rename or create a new class: this sounds more like a "manager" than the runner itself
    runner = QualityTestRunner(
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        datadir=ctx.quality_folder,
        agent_server_version=None,
    )

    oauth_connections = await runner.get_oauth_connections()

    for provider, scopes in oauth_connections.items():
        scope_names = list(scopes.keys())
        uses = scopes.values()
        provider_actions = [item["action"] for use in uses for item in use]
        scope = " ".join(scope_names)

        if provider not in ctx.oauth:
            raise click.UsageError(f"👤 Provider '{provider}' not found in config. Required in 🔧 {provider_actions}")

        cfg = ctx.oauth[provider]
        auth_params = {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "scope": scope,
        }
        auth_url = f"{cfg.auth_url}?{urlencode(auth_params)}"

        click.echo("OAuth Authorization Required for:\n")
        click.echo(f"👤 Provider:\t '{provider}'")
        click.echo(f"🔧 Actions:\t '{provider_actions}'")
        click.echo(f"🌐 Scopes:\t '{scope}'")
        click.echo(f"\nOpen this URL in your browser to authorize:\n{auth_url}")

        parsed_url = urlparse(cfg.redirect_uri)
        redirect_host = parsed_url.hostname
        redirect_port = parsed_url.port
        if redirect_host is None or redirect_port is None:
            raise click.UsageError(f"Cannot parse redirect uri {cfg.redirect_uri}.")

        # TODO keep the server up until all the oauth connections are not processed
        server = OAuthRedirectServer(host=redirect_host, port=redirect_port)
        print("Waiting for OAuth authorization...")

        auth_code = server.wait_for_code(timeout=180)

        click.echo(f"Received authorization code: {auth_code}")

        token_data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": cfg.redirect_uri,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
        }

        try:
            with httpx.Client() as client:
                response = client.post(cfg.token_url, data=token_data)
                response.raise_for_status()
                credentials = response.json()
        except httpx.HTTPStatusError as e:
            click.echo(f"HTTP error: {e.response.status_code} - {e.response.text}", err=True)
            return
        except httpx.RequestError as e:
            click.echo(f"Request failed: {e}", err=True)
            return

        click.echo("Updating OAuth Credentials")
        await runner.oauth.update_oauth_credentials(provider=provider, credentials=credentials)


@cli.command()
@click.option(
    "--trace-file",
    required=True,
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Simulate the agent environment using an existing conversation",
)
@click.option(
    "--agent-server-version",
    required=False,
    type=str,
)
@click.option(
    "--platform",
    required=False,
    type=str,
)
@click.option(
    "--agent-name",
    required=False,
    type=str,
)
@click.option("--assert-all-consumed", is_flag=True)
@click.pass_obj
async def replay(
    ctx: Context,
    trace_file: Path,
    agent_server_version: str | None,
    platform: str | None,
    agent_name: str | None,
    assert_all_consumed: bool,
):
    trace = Trace.from_file(trace_file)

    try:
        click.echo("🚀 Replaying conversation")
        click.echo("-" * 40)
        click.echo(f"{click.style('Name:', fg='green')} {trace.environment.name}")
        click.echo(f"{click.style('Agent Name:', fg='green')} {trace.environment.agent_name}")
        click.echo(f"{click.style('Agent Server Version:', fg='green')} {trace.environment.agent_server_version}")
        click.echo(f"{click.style('Platform:', fg='green')} {trace.environment.platform}")
        click.echo("-" * 40)

        agent_server_version = (
            agent_server_version if agent_server_version is not None else trace.environment.agent_server_version
        )

        simulator = Simulator(
            test_threads_dir=ctx.threads_dir,
            test_agents_dir=ctx.agents_dir,
            agent_server_version=agent_server_version,
            datadir=ctx.quality_folder,
            server_url=ctx.agent_server_url,
        )

        # TODO allow to override trace environment
        result = await simulator.replay_trace(
            golden_trace=trace,
            assert_all_consumed=assert_all_consumed,
            agent_server_version=agent_server_version,
            platform=platform,
            agent_name=agent_name,
        )

        click.echo(f"💾 Results automatically saved to {simulator.result_manager.current_run_dir}")

        if result.error is not None:
            click.echo(f"❌ Replayed failed: {result.error}", err=True)
            sys.exit(1)

        click.echo("✅ Trace replayed successfully")

    except Exception as e:
        click.echo(f"Error running reply: {e}")
        if ctx.verbose:
            import traceback

            traceback.print_exc()
        raise click.Abort() from None


@cli.group()
def bird():
    """BIRD benchmark dataset management commands.

    BIRD benchmark stores data in two places:
      - Questions/SQL metadata: Hugging Face (birdsql/*)
      - Database files (.sqlite): Google Drive (manual download)

    Database files must be downloaded from:
      https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view
    """
    pass


@bird.command(name="docker")
@click.argument("action", type=click.Choice(["up", "down", "ps", "logs"]))
@click.option("--wait/--no-wait", default=True, help="Wait for healthy status after 'up' (default: True)")
@click.option(
    "--sql-file",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Path to BIRD_dev.sql (overrides BIRD_DEV_SQL_PATH env var)",
)
@click.option(
    "-v",
    "--volumes",
    is_flag=True,
    help="Remove volumes when using 'down' (destructive - deletes all data)",
)
def bird_docker(action: str, wait: bool, sql_file: Path | None, volumes: bool):
    """Manage BIRD Docker Compose stack.

    Actions:
      up    - Start the BIRD PostgreSQL stack (waits for healthy by default)
      down  - Stop and remove the stack
      ps    - Show stack status
      logs  - Show stack logs

    Examples:
      quality-test bird docker up                           # Start and wait for healthy
      quality-test bird docker up --sql-file /path/to/file  # Specify SQL file
      quality-test bird docker up --no-wait                 # Start without waiting
      quality-test bird docker down                         # Stop stack (keeps data)
      quality-test bird docker down -v                      # Stop and remove volumes
      quality-test bird docker ps                           # Check status
      quality-test bird docker logs                         # View logs
    """
    import os
    import subprocess

    monorepo_root = find_monorepo_root()
    compose_file = monorepo_root / "quality" / "docker" / "bird-compose.yml"

    if not compose_file.exists():
        click.echo(f"❌ Compose file not found: {compose_file}", err=True)
        raise click.Abort()

    # Prepare environment for subprocess
    env = os.environ.copy()
    if sql_file:
        env["BIRD_DEV_SQL_PATH"] = str(sql_file.resolve())

    try:
        if action == "up":
            click.echo("🚀 Starting BIRD PostgreSQL stack...")
            click.echo(f"   Compose file: {compose_file}")
            if sql_file:
                click.echo(f"   SQL file: {sql_file}")
            click.echo("   This may take ~5 minutes on first run to load 955MB of data")

            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d"],
                check=True,
                env=env,
            )

            if wait:
                import sys
                import time

                click.echo("\n⏳ Waiting for database to be healthy (50+ tables loaded)...")
                max_wait = 600  # 10 minutes
                poll_interval = 3
                elapsed = 0

                while elapsed < max_wait:
                    result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            "bird-quality-postgres",
                            "--format={{.State.Health.Status}}",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    status = result.stdout.strip()

                    if status == "healthy":
                        click.echo("✅ BIRD PostgreSQL stack is healthy and ready!")
                        break
                    elif status == "unhealthy":
                        click.echo("❌ Container is unhealthy. Check logs with: bird docker logs", err=True)
                        raise click.Abort()
                    else:
                        # starting or no status yet - show spinner-style progress
                        mins, secs = divmod(elapsed, 60)
                        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
                        click.echo(f"\r   Status: {status or 'starting'}... ({time_str} elapsed)  ", nl=False)
                        sys.stdout.flush()
                        time.sleep(poll_interval)
                        elapsed += poll_interval

                # Clear the progress line
                click.echo("\r" + " " * 60 + "\r", nl=False)
                if elapsed >= max_wait:
                    click.echo(f"❌ Timeout after {max_wait}s waiting for healthy status", err=True)
                    subprocess.run(["docker", "compose", "-f", str(compose_file), "ps"], check=False)
                    raise click.Abort()
            else:
                click.echo("✅ BIRD PostgreSQL stack started (use 'bird docker ps' to check health)")

        elif action == "down":
            if volumes:
                click.echo("🛑 Stopping BIRD PostgreSQL stack and removing volumes...")
                click.echo("⚠️  This will delete all data - you'll need to reload on next start")
            else:
                click.echo("🛑 Stopping BIRD PostgreSQL stack...")

            cmd = ["docker", "compose", "-f", str(compose_file), "down"]
            if volumes:
                cmd.append("-v")

            subprocess.run(cmd, check=True, env=env)
            click.echo("✅ Stack stopped" + (" and volumes removed" if volumes else ""))

        elif action == "ps":
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "ps"],
                check=True,
                env=env,
            )

        elif action == "logs":
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "logs", "-f"],
                check=True,
                env=env,
            )

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Docker compose command failed: {e}", err=True)
        raise click.Abort() from None
    except FileNotFoundError:
        click.echo("❌ Docker or docker compose not found. Please install Docker.", err=True)
        raise click.Abort() from None


@bird.command(name="list-dbs")
@click.option(
    "--hf-dataset",
    type=str,
    default="birdsql/bird_sql_dev_20251106",
    help="Hugging Face dataset name (default: birdsql/bird_sql_dev_20251106)",
)
@click.option(
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Sema4ai home folder for cache (default: ~/.sema4x)",
)
def bird_list_dbs(
    hf_dataset: str,
    home_folder: Path | None,
):
    """List available database IDs in a BIRD Hugging Face dataset.

    Example:

      quality-test bird list-dbs --hf-dataset birdsql/bird_sql_dev_20251106
    """
    try:
        home_folder = home_folder if home_folder is not None else Path.home() / ".sema4x"
        bird_cache_dir = home_folder / "quality" / "bird"
        resolver = BirdDatasetResolver(cache_dir=bird_cache_dir)

        click.echo(f"🔍 Listing available database IDs in {hf_dataset}...")
        db_ids = resolver.list_available_db_ids(hf_dataset)

        click.echo(f"\n✅ Found {len(db_ids)} databases:")
        for db_id in db_ids:
            click.echo(f"   • {db_id}")

        click.echo("\nTo import a database, you need:")
        click.echo("  1. Download the database files from Google Drive:")
        click.echo("     https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view")
        click.echo("  2. Run the import command with the --db-path pointing to your .sqlite file")

    except Exception as e:
        click.echo(f"❌ Error listing databases: {e}", err=True)
        raise click.Abort() from None


@bird.command(name="import")
@click.option(
    "--hf-dataset",
    type=str,
    default="birdsql/bird_sql_dev_20251106",
    help="Hugging Face dataset for questions (default: birdsql/bird_sql_dev_20251106)",
)
@click.option(
    "--db-path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to SQLite file OR dev_databases directory (imports all if directory)",
)
@click.option(
    "--questions-json",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Local path to BIRD questions JSON file (alternative to --hf-dataset)",
)
@click.option(
    "--db-id",
    type=str,
    help="Database ID to import (optional if --db-path is a directory to import all)",
)
@click.option(
    "--test-prefix",
    type=str,
    help="Prefix for test directory names (default: 'bird-{db_id}')",
)
@click.option(
    "--sdm-name",
    type=str,
    help="Name for SDM reference (default: 'bird_{db_id}')",
)
@click.option(
    "--output-threads-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for test threads (default: quality/test-threads/@preinstalled-sql-generation)",
)
@click.option(
    "--force-download",
    is_flag=True,
    help="Force re-download questions from Hugging Face even if cached",
)
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    help="Skip test directories that already exist (default: skip)",
)
@click.option(
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Sema4ai home folder for cache (default: ~/.sema4x)",
)
@click.option(
    "--generate-sdm",
    is_flag=True,
    help="Generate SDM using agent server (requires server and BIRD docker running)",
)
@click.option(
    "--agent-id",
    type=str,
    help="Agent ID for SDM generation (default: uses @preinstalled-sql-generation agent)",
)
@click.pass_obj
def bird_import(
    ctx: Context,
    hf_dataset: str | None,
    db_path: Path,
    questions_json: Path | None,
    db_id: str | None,
    test_prefix: str | None,
    sdm_name: str | None,
    output_threads_dir: Path | None,
    force_download: bool,
    skip_existing: bool,
    home_folder: Path | None,
    generate_sdm: bool,
    agent_id: str | None,
):
    """Import BIRD benchmark dataset and generate test threads with golden CSVs.

    This command downloads latest questions from Hugging Face and generates golden
    CSVs by executing SQLite gold SQL.

    Examples:

      # Import ALL databases from dev_databases directory
      quality-test bird import \\
        --db-path ~/.sema4x/quality/bird-data/minidev/MINIDEV/dev_databases

      # Import a single database
      quality-test bird import \\
        --db-path .../dev_databases/california_schools/california_schools.sqlite \\
        --db-id california_schools

    For more info: docs/BIRD_CLI_GUIDE.md
    """
    try:
        # Validate input options
        if hf_dataset and questions_json:
            raise click.UsageError(
                "Cannot specify both --hf-dataset and --questions-json. Choose one source for questions."
            )

        if not hf_dataset and not questions_json:
            raise click.UsageError("Must specify either --hf-dataset OR --questions-json for the questions source")

        # Discover databases to import
        databases_to_import: list[tuple[Path, str]] = []

        if db_path.is_dir():
            # Directory mode: discover all databases
            click.echo(f"📂 Discovering databases in {db_path}...")
            for subdir in sorted(db_path.iterdir()):
                if subdir.is_dir():
                    # Look for .sqlite file with same name as directory
                    sqlite_file = subdir / f"{subdir.name}.sqlite"
                    if sqlite_file.exists():
                        databases_to_import.append((sqlite_file, subdir.name))
                        click.echo(f"   Found: {subdir.name}")

            if not databases_to_import:
                raise click.UsageError(f"No databases found in {db_path}. Expected subdirectories with .sqlite files.")

            click.echo(f"\n🎯 Will import {len(databases_to_import)} databases")
        else:
            # Single file mode
            if not db_id:
                # Try to derive db_id from filename
                db_id = db_path.stem
                click.echo(f"   Inferred db_id: {db_id}")
            databases_to_import.append((db_path, db_id))

        # Set defaults
        home_folder = home_folder if home_folder is not None else Path.home() / ".sema4x"
        monorepo_root = find_monorepo_root()
        output_threads_dir = output_threads_dir or (
            monorepo_root / "quality" / "test-threads" / "@preinstalled-sql-generation"
        )
        bird_cache_dir = home_folder / "quality" / "bird"
        resolver = BirdDatasetResolver(cache_dir=bird_cache_dir)

        total_generated = 0
        total_skipped = 0

        for sqlite_path, current_db_id in databases_to_import:
            current_test_prefix = test_prefix or f"bird-{current_db_id.replace('_', '-')}"
            current_sdm_name = sdm_name or f"bird_{current_db_id}"

            click.echo(f"\n{'=' * 60}")
            click.echo(f"📦 Importing: {current_db_id}")
            click.echo(f"{'=' * 60}")

            # Resolve dataset source
            click.echo("🔍 Resolving BIRD dataset source...")
            if hf_dataset:
                click.echo(f"   Questions: Hugging Face ({hf_dataset})")
                click.echo(f"   SQLite DB: {sqlite_path}")
                dataset_info = resolver.resolve_huggingface_questions(
                    dataset_name=hf_dataset,
                    db_id=current_db_id,
                    db_path=sqlite_path,
                    force_download=force_download,
                )
            else:
                click.echo("   Source: Local files")
                dataset_info = resolver.resolve_local(
                    db_path=sqlite_path,
                    questions_json_path=questions_json,  # type: ignore
                    db_id=current_db_id,
                )

            click.echo(f"   Database: {dataset_info['db_path']}")
            click.echo(f"   Questions: {dataset_info['questions_json_path']}")

            # Initialize generator
            generator = BirdDatasetGenerator(
                db_path=dataset_info["db_path"],
                questions_json_path=dataset_info["questions_json_path"],
                output_threads_dir=output_threads_dir,
                db_id=current_db_id,
                test_name_prefix=current_test_prefix,
                sdm_name=current_sdm_name,
            )

            # Generate test threads with golden CSVs
            click.echo("\n📝 Generating test threads and golden CSVs...")
            generated, skipped = generator.generate_test_threads(skip_existing=skip_existing)
            total_generated += generated
            total_skipped += skipped

            # Generate SDM if requested
            if generate_sdm:
                from agent_platform.quality.bird.generation import generate_bird_sdm

                # Determine agent ID using metadata search (same as runner.py)
                if not agent_id:
                    click.echo("\n🔍 Looking up @preinstalled-sql-generation agent...")
                    import httpx

                    try:
                        search_url = f"{ctx.agent_server_url}/api/v2/agents/search/by-metadata"
                        params = {"visibility": "hidden", "feature": "sql-generation"}
                        with httpx.Client(timeout=30.0) as client:
                            response = client.get(search_url, params=params)
                            response.raise_for_status()
                            agents_data = response.json() or []

                        if agents_data and isinstance(agents_data, list) and len(agents_data) > 0:
                            agent_id = agents_data[0].get("id")

                        if not agent_id:
                            click.echo("❌ Could not find @preinstalled-sql-generation agent", err=True)
                            click.echo("   Please specify --agent-id or deploy the agent", err=True)
                            raise click.Abort()
                        click.echo(f"   ✓ Found agent: {agent_id}")
                    except httpx.HTTPError as e:
                        click.echo(f"❌ Failed to connect to agent server: {e}", err=True)
                        click.echo(f"   Ensure agent server is running at {ctx.agent_server_url}", err=True)
                        raise click.Abort() from None

                # Determine context directory and output directory
                db_description_dir = sqlite_path.parent / "database_description"
                sdm_output_dir = monorepo_root / "quality" / "test-data" / "sdms" / current_sdm_name

                # Generate SDM
                asyncio.run(
                    generate_bird_sdm(
                        server_url=ctx.agent_server_url,
                        db_id=current_db_id,
                        context_dir=db_description_dir,
                        output_dir=sdm_output_dir,
                        agent_id=agent_id,
                    )
                )

        click.echo(f"\n{'=' * 60}")
        click.echo("✅ BIRD dataset import complete!")
        click.echo(f"{'=' * 60}")
        click.echo(f"   Databases imported: {len(databases_to_import)}")
        click.echo(f"   Test threads: {output_threads_dir}")
        click.echo(f"   Generated: {total_generated} tests")
        if total_skipped > 0:
            click.echo(f"   Skipped: {total_skipped} tests (already exist)")
        if generate_sdm:
            sdms_dir = monorepo_root / "quality" / "test-data" / "sdms"
            click.echo(f"   SDMs: {sdms_dir}/bird_*")
        click.echo("\n💡 To run tests, ensure BIRD compose stack is running:")
        click.echo("   quality-test bird docker up")

    except Exception as e:
        click.echo(f"❌ Error importing BIRD dataset: {e}", err=True)
        raise click.Abort() from None


# Async wrapper for Click commands
def async_command(f):
    """Decorator to make Click commands async-compatible."""

    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


# Apply async wrapper to async commands
check_server.callback = async_command(check_server.callback)
run.callback = async_command(run.callback)
oauth.callback = async_command(oauth.callback)
init.callback = async_command(init.callback)
replay.callback = async_command(replay.callback)
# Note: bird_import is synchronous, no async wrapper needed


def find_monorepo_root() -> Path:
    """Find the monorepo root by looking for markers like .git directory."""
    current = Path.cwd()

    # Walk up the directory tree looking for the monorepo root
    while current != current.parent:
        # Check for common monorepo markers
        if (current / ".git").is_dir() or (current / "pyproject.toml").is_file():
            # Additional check: ensure this is the agent-platform monorepo
            # by looking for the quality directory
            if (current / "quality").is_dir():
                return current
        current = current.parent

    # Fallback to current working directory
    return Path.cwd()


def load_env_file(verbose: bool = False):
    """Load .env file from the monorepo root if it exists."""
    monorepo_root = find_monorepo_root()
    env_file = monorepo_root / ".env"

    # First, if it exists, load the .env file in the quality directory
    quality_env_file = monorepo_root / "quality" / ".env"
    if quality_env_file.is_file():
        load_dotenv(quality_env_file)
        if verbose:
            click.echo(f"📄 Loaded environment variables from: {quality_env_file}")

    # Then, it _must_ exist, load the .env file in the monorepo root
    if env_file.is_file():
        load_dotenv(env_file)
        if verbose:
            click.echo(f"📄 Loaded environment variables from: {env_file}")
        return str(env_file)
    else:
        # .env file is required for operation
        click.echo(f"❌ Error: Required .env file not found at: {env_file}", err=True)
        click.echo(
            "💡 Please create a .env file in the monorepo root using `make new-empty-env`",
            err=True,
        )
        raise click.ClickException(f"Required .env file not found at: {env_file}")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
