import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent_platform.quality.formatters import messages_to_str
from agent_platform.quality.models import ThreadResult

console = Console()

# Constants
ERROR_PREVIEW_LENGTH = 50

logger = structlog.get_logger(__name__)


class QualityReporter:
    """Reporter for quality test results."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def report_results(self, results: dict[str, list[ThreadResult]]):
        """Generate a comprehensive report of all test results."""
        self.console.print("\n[bold blue]Quality Test Results[/bold blue]\n")

        if not results:
            self.console.print("[yellow]No test results to display[/yellow]")
            return

        # Overall summary
        total_agents = len(results)
        total_tests = sum(len(agent_results) for agent_results in results.values())
        total_passed = sum(sum(1 for result in agent_results if result.success) for agent_results in results.values())

        summary = Table(title="Test Summary", show_header=False)
        summary.add_column("Metric", style="bold")
        summary.add_column("Value")

        summary.add_row("Agents Tested", str(total_agents))
        summary.add_row("Total Tests", str(total_tests))
        summary.add_row("Tests Passed", f"{total_passed}/{total_tests}")
        summary.add_row(
            "Success Rate",
            f"{(total_passed / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
        )

        self.console.print(summary)
        self.console.print()

        # Per-agent results
        for agent_name, agent_results in results.items():
            self._report_agent_results(agent_name, agent_results)

    def _report_agent_results(self, agent_name: str, results: list[ThreadResult]):
        """Report results for a single agent."""
        if not results:
            self.console.print(f"[yellow]No results for {agent_name}[/yellow]")
            return

        self.console.print(f"\n[bold blue]{agent_name}[/bold blue]")

        # Group results by platform for better organization
        platform_groups: dict[str, list[ThreadResult]] = {}
        for result in results:
            platform_name = result.platform.name
            if platform_name not in platform_groups:
                platform_groups[platform_name] = []
            platform_groups[platform_name].append(result)

        # Report results grouped by platform
        for platform_name, platform_results in platform_groups.items():
            self.console.print(f"\n  [bold cyan]Platform: {platform_name}[/bold cyan]")

            for result in platform_results:
                # Get test case name from the result
                test_case_name = result.test_case.name

                # Add model info if present
                if result.model_id:
                    # Extract just the model name (last part of platform/provider/model)
                    model_name = result.model_id.split("/")[-1]
                    # Use parentheses instead of brackets (Rich Console uses [] for markup)
                    test_case_name = f"{test_case_name} ({model_name})"

                # Status
                if result.error:
                    status = "[red]FAILED[/red]"
                    status_icon = "❌"
                elif result.evaluation_results and all(r.passed for r in result.evaluation_results):
                    status = "[green]PASSED[/green]"
                    status_icon = "✅"
                elif result.evaluation_results:
                    status = "[yellow]PARTIAL[/yellow]"
                    status_icon = "⚠️"
                else:
                    status = "[gray]NO EVAL[/gray]"
                    status_icon = "-"

                # Create result summary
                result_summary = self._create_result_summary(result)

                # Print summary with platform context
                self.console.print(f"    {status_icon} {test_case_name} - {status}")
                if result_summary:
                    self.console.print(f"      {result_summary}")

    def _create_result_summary(self, result: ThreadResult) -> str:
        """Create a summary string for a test result."""
        # Details
        if result.error:
            error_preview = (
                f"{result.error[:ERROR_PREVIEW_LENGTH]}{'...' if len(result.error) > ERROR_PREVIEW_LENGTH else ''}"
            )
            return f"[red]Error: {error_preview}[/red]"
        elif result.evaluation_results:
            failed_evals = [r for r in result.evaluation_results if not r.passed]
            if failed_evals:
                return f"[yellow]{len(failed_evals)} evaluations failed[/yellow]"
            else:
                return f"[green]All {len(result.evaluation_results)} evaluations passed[/green]"
        else:
            return "[gray]No evaluations run[/gray]"

    def report_detailed_results(self, results: dict[str, list[ThreadResult]]):
        """Generate a detailed report with evaluation breakdowns."""
        self.console.print("\n[bold blue]Detailed Quality Test Results[/bold blue]\n")

        for agent_name, agent_results in results.items():
            if not agent_results:
                continue

            self.console.print(f"\n[bold cyan]Agent: {agent_name}[/bold cyan]\n")

            for result in agent_results:
                self._report_detailed_test_result(result)

    def _report_detailed_test_result(self, result: ThreadResult):
        """Report detailed results for a single test."""
        # Test header with platform information
        status_color = "green" if result.success else "red"
        test_title = f"[{status_color}]Test: {result.test_case.name} "
        test_title += f"(Platform: {result.platform.name}"
        if result.model_id:
            model_name = result.model_id.split("/")[-1]
            test_title += f", Model: {model_name}"
        test_title += f")[/{status_color}]"

        # Create panel content
        content = []

        # Description
        if result.test_case.description:
            content.append(f"[dim]Description: {result.test_case.description}[/dim]")

        # Platform and model information
        platform_info = f"[bold]Platform:[/bold] {result.platform.name}"
        if result.model_id:
            platform_info += f" | [bold]Model:[/bold] {result.model_id}"
        content.append(platform_info)

        # Agent messages summary
        if result.agent_messages:
            content.append(f"\n[bold]Agent Response ({len(result.agent_messages)} messages):[/bold]")
            for i, msg in enumerate(result.agent_messages):
                preview_length = 100
                preview = messages_to_str([msg])[:preview_length] + "..."
                content.append(f"  {i + 1}. {preview}")

        # Error if present
        if result.error:
            content.append(f"\n[red bold]Error:[/red bold] {result.error}")

        # Evaluations
        if result.evaluation_results:
            content.append(f"\n[bold]Evaluations ({len(result.evaluation_results)}):[/bold]")
            for eval_result in result.evaluation_results:
                status_icon = "✓" if eval_result.passed else "✗"
                status_color = "green" if eval_result.passed else "red"
                content.append(f"  [{status_color}]{status_icon} {eval_result.evaluation.kind}[/{status_color}]")

                if eval_result.error:
                    content.append(f"    [red]Error: {eval_result.error}[/red]")
                elif hasattr(eval_result.actual_value, "get") and eval_result.actual_value.get("explanation"):
                    content.append(f"    [dim]{eval_result.actual_value['explanation']}[/dim]")

        # Create panel
        panel_content = "\n".join(content)
        border_style = "green" if result.success else "red"

        panel = Panel(panel_content, title=test_title, border_style=border_style, padding=(1, 2))

        self.console.print(panel)

    def report_agent_summary(self, agent_name: str, results: list[ThreadResult]):
        """Report a summary for a specific agent."""
        self.console.print(f"\n[bold blue]Results for Agent: {agent_name}[/bold blue]\n")

        if not results:
            self.console.print("[yellow]No test results available[/yellow]")
            return

        # Quick summary
        passed = sum(1 for r in results if r.success)
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0

        summary_text = f"Tests: {passed}/{total} passed ({success_rate:.1f}%)"
        summary_color = "green" if passed == total else "red" if passed == 0 else "yellow"

        self.console.print(f"[{summary_color}]{summary_text}[/{summary_color}]\n")

        # Detailed breakdown
        self._report_agent_results(agent_name, results)

    def report_platform_summary(self, results: dict[str, list[ThreadResult]]):
        """Generate a platform-focused summary report."""
        self.console.print("\n[bold blue]Platform Summary Report[/bold blue]\n")

        if not results:
            self.console.print("[yellow]No test results to display[/yellow]")
            return

        # Collect all platform results
        platform_stats: dict[str, dict[str, int]] = {}

        for _, agent_results in results.items():
            for result in agent_results:
                platform_name = result.platform.name
                if platform_name not in platform_stats:
                    platform_stats[platform_name] = {"total": 0, "passed": 0, "failed": 0}

                platform_stats[platform_name]["total"] += 1
                if result.success:
                    platform_stats[platform_name]["passed"] += 1
                else:
                    platform_stats[platform_name]["failed"] += 1

        # Create platform summary table
        platform_table = Table(title="Results by Platform")
        platform_table.add_column("Platform", style="bold")
        platform_table.add_column("Total Tests", justify="center")
        platform_table.add_column("Passed", justify="center", style="green")
        platform_table.add_column("Failed", justify="center", style="red")
        platform_table.add_column("Success Rate", justify="center")

        for platform_name, stats in platform_stats.items():
            success_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            success_rate_style = "green" if success_rate == 100 else "red" if success_rate == 0 else "yellow"

            platform_table.add_row(
                platform_name,
                str(stats["total"]),
                str(stats["passed"]),
                str(stats["failed"]),
                f"[{success_rate_style}]{success_rate:.1f}%[/{success_rate_style}]",
            )

        self.console.print(platform_table)
