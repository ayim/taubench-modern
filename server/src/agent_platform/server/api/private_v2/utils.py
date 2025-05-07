from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.context import AgentServerContext
from agent_platform.core.runbook import Runbook
from agent_platform.core.runs import Run
from agent_platform.core.thread import Thread
from agent_platform.server.kernel import AgentServerKernel


def create_minimal_kernel(ctx: AgentServerContext) -> AgentServerKernel:
    user = ctx.user_context.user
    empty_agent = Agent(
        user_id=user.user_id,
        version="0.0.0",
        name="empty-agent",
        description="empty-agent",
        agent_architecture=AgentArchitecture(name="", version=""),
        platform_configs=[],
        runbook_structured=Runbook(content=[], raw_text=""),
    )
    empty_thread = Thread(
        user_id=user.user_id,
        agent_id=empty_agent.agent_id,
        name="empty-thread",
        messages=[],
    )
    empty_run = Run(
        run_id="00000000-0000-0000-0000-000000000000",
        agent_id=empty_agent.agent_id,
        thread_id=empty_thread.thread_id,
    )
    return AgentServerKernel(
        ctx=ctx,
        thread=empty_thread,
        agent=empty_agent,
        run=empty_run,
    )
