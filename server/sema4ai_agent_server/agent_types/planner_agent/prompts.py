from langchain_core.messages import AnyMessage
from pydantic import Field

from sema4ai_agent_server.agent_types.factory import (
    BaseInputSpec,
    PredefinedChatPromptTemplate,
)
from sema4ai_agent_server.agent_types.tools_agent import ToolsAgentBasePromptTemplate
from sema4ai_agent_server.agent_types.utils import is_claude, is_reasoning
from sema4ai_agent_server.schema import Agent, AgentReasoning

PLAN_DESCRIPTION = """Plans are generally only required for more complex objectives which \
would benefit from multiple rounds of interaction with various tools to complete, especially \
where the expected output from one tool needs to be used as input into future tools. If you \
think you already know how to respond, or the user seems to want to chat (for example, they \
say "hello"), or you think one of the available tools could be used in a single shot, we \
would not need a plan. 

When creating the plan, think about the various steps needed to accomplish the objective and \
what information is needed for each step. Each step is likely interconnected with the previous \
and following steps, so be sure to think about how each step builds on the previous one. These \
plans are relied upon by the rest of the team, so it is very important that they be thorough \
and include all steps needed to accomplish the objective.

If only one step is needed, a plan is not required."""

## Planner related prompts and messages
PLANNER_ROLE = """You are part of a team of agents following the provided runbook. Your \
job is to decide if we need a plan to complete the objective provided by the user, and \
then develop that plan if so."""

# Not currently used, but could be included in instructions for planner if plans keep being problematic
EXAMPLE_THINKER_STEPS = """[
    (
    "To gather relevant news and financial data, we need to perform a web search for the \
latest news on financial markets and economic conditions.",
    "Use the web_search_news function to search for the latest news on financial markets \
and economic conditions. Set the count to 10 to get a comprehensive overview."
    ),
    (
    "We need to analyze the results from the web search to identify trends, risks, and \
opportunities in the market.",
    "Review the results from the web_search_news function to identify \
trends, risks, and opportunities in the market."
    ),
    (
    "To develop an investment strategy for the next quarter, we must analyze the results \
from the web search and identify key areas for investment.",
    "Synthesize the findings from the analysis to develop a comprehensive investment \
strategy for the next quarter. This should include recommendations on asset allocation, specific \
sectors or stocks to invest in, and any risk management strategies."
    )
]"""


class PlannerInputSpec(BaseInputSpec):
    name: str = Field(..., description="The name of the agent team.")
    datetime: str = Field(..., description="The current datetime in ISO 8601 format.")
    knowledge_files: str = Field(
        ..., description="The knowledge files available to the agent."
    )
    runbook: str = Field(..., description="The runbook for the team.")
    messages: list[AnyMessage] = Field(
        ..., description="The messages in the conversation."
    )


class PlannerPromptTemplate(PredefinedChatPromptTemplate):
    """Prompt template for the planner agent to decide if a plan is needed and to develop
    the plan. Invocation of the template uses the PlannerInputSpec.

    Args:
        agent (Agent): Only `reasoning` level is used from the agent object.
    """

    input_spec: type[PlannerInputSpec] = PlannerInputSpec

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        beggining_of_thinking_prompt = f"""
Based on the full conversation that follows, you must think about whether we need a plan to \
respond to the user.{' BE SUCCINCT.' if is_reasoning(agent, AgentReasoning.ENABLED) else ''} \
Explain your thinking about whether a plan is needed.

If a plan is needed,{' succinctly' if is_reasoning(agent, AgentReasoning.ENABLED) else ''} \
explain your approach. When developing the plan,\
{' succinctly' if is_reasoning(agent, AgentReasoning.ENABLED) else ''} think about each step \
and why it is needed. Include your thoughts in the response tool call. 
    """.strip()

        beggining_of_non_thinking_prompt = """
Based on the full conversation that follows, you must decide if we need a plan to respond to the user.
    """.strip()

        step_description = """
Steps must be created as tuples of two strings: \
the first string is the reasoning why the step is needed and the second string is the step itself.
    """.strip()

        prompt = f"""
We use XML tags to help structure our team instructions. Runbooks \
use markdown to format structured content.

Our team name: <team_name>
{{name}}
</team_name>

Current datetime (ISO 8601): <datetime>
{{datetime}}
</datetime>

Your role: <role>
{PLANNER_ROLE}
</role>

What is a plan: <plan_description>
{PLAN_DESCRIPTION}
</plan_description>

Knowledge files you have access to: <knowledge_files>
{{knowledge_files}}
</knowledge_files>

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
{beggining_of_thinking_prompt if is_reasoning(agent) else beggining_of_non_thinking_prompt}

The plan should be specific and each step should help to achieve the objective. The result of \
the final step should be a complete meaningful response to the objective. The entire team is \
relying on you to develop a complete plan for them, you must develop a full plan that will \
accomplish the objective made up of multiple steps. Make sure each step has all the information \
needed, assume every step will be followed.

{step_description if is_reasoning(agent) else ""}
</instructions>
    """.strip()

        return [
            ("system", prompt),
            ("placeholder", "{messages}"),
        ]


# Step Executor Prompts
STEP_EXECUTOR_ROLE = """You are part of a team of agents following the provided runbook. Your \
job is to execute the current step of the plan developed by the planner to complete the objective \
provided by the user."""


STEP_EXECUTOR_TEMPLATE = f"""
We use XML tags to help structure our team instructions. Runbooks \
use markdown to format structured content.

Our team name: <team_name>
{{agent_name}}
</team_name>

Current datetime (ISO 8601): <datetime>
{{current_datetime}}
</datetime>

Your role: <role>
{STEP_EXECUTOR_ROLE}
</role>

Knowledge files you have access to: <knowledge_files>
{{knowledge_files}}
</knowledge_files>

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
The planner will provide you with a snippet of the current team thread, which may include messages \
from the user and other members of your team. The last message in the thread will be the planner's \
directions to you. You must execute the step provided by the planner to the best of your ability. \
You should assume that the overall objective may not be known to you, but you should focus on \
completing the step provided to you.
</instructions>
    """.strip()


# Prompts to override subagent built in prompts
class StepExecutorPromptTemplate(ToolsAgentBasePromptTemplate):
    """Prompt template for the step executor agent to execute the current step of the plan."""

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        return [
            ("system", STEP_EXECUTOR_TEMPLATE),
            ("placeholder", "{messages}"),
            (
                "human" if is_claude(agent.model) else "system",
                "Now execute the step provided above.",
            ),
        ]


class StepReasoningPromptTemplate(ToolsAgentBasePromptTemplate):
    """Prompt template for the step executor agent to provide reasoning for their response."""

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        next_response_prompt = f"""
Think about your next response based on the conversation and instructions the planner provided. \
Then,{' succinctly' if is_reasoning(agent, AgentReasoning.ENABLED) else ''} explain why you are thinking to respond in \
this way. Focus on the most important aspects of your reasoning. ONLY PROVIDE REASONING.
        """.strip()

        return [
            ("system", STEP_EXECUTOR_TEMPLATE),
            ("placeholder", "{messages}"),
            ("human" if is_claude(agent.model) else "system", next_response_prompt),
        ]


# Replanner related prompts and messages
REPLANNER_ROLE = """You are part of a team of agents following the provided runbook. Your \
job is to update the current plan to complete the objective provided by the user."""


class ReplannerInputSpec(BaseInputSpec):
    name: str = Field(..., description="The name of the agent team.")
    datetime: str = Field(..., description="The current datetime in ISO 8601 format.")
    knowledge_files: str = Field(
        ..., description="The knowledge files available to the agent."
    )
    runbook: str = Field(..., description="The runbook for the team.")
    objective: str = Field(..., description="The objective provided by the user.")
    last_step: str = Field(
        ..., description="The last step executed by the step executor."
    )
    remaining_steps: str = Field(..., description="The remaining steps in the plan.")
    messages: list[AnyMessage] = Field(
        ..., description="The messages in the conversation."
    )


class ReplannerPromptTemplate(PredefinedChatPromptTemplate):
    """Prompt template for the replanner agent to update the plan and respond to the user.

    Invocation of the template uses the ReplannerInputSpec.

    Args:
        agent (Agent): Only `reasoning` level is used from the agent object.
    """

    input_spec: type[ReplannerInputSpec] = ReplannerInputSpec

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        reasoning_step = f"""
5. Using the response tool,{' succinctly' if is_reasoning(agent, AgentReasoning.ENABLED) else ''} write out your thoughts for these points \
in the "reasoning" field.
    """.strip()

        main_replanner_prompt = f"""
We use XML tags to help structure our team instructions. Runbooks use markdown to \
format structured content.

Our team name: <team_name>
{{name}}
</team_name>

Current datetime (ISO 8601): <datetime>
{{datetime}}
</datetime>

Your role: <role>
{REPLANNER_ROLE}
</role>

What is a plan: <plan_description>
{PLAN_DESCRIPTION}
</plan_description>

Knowledge files you have access to: <knowledge_files>
{{knowledge_files}}
</knowledge_files>

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
The below objective is the last message from the user. Following that is \
your team's internal thread as the plan was executed. Finally, an additional system message \
will be added to help you compare the last step executed at that point in the thread to \
what was expected to be completed and the remaining steps in the plan.

Review the objective, the last step executed, and the team thread, then perform the \
following in order:

1. Determine if the last step was properly completed. If it was not, consider how to modify the \
step and rest of the plan to ensure the objective is met. Consider how the agent had responded \
and if that indicates there are problems with the way the step was written or with any underlying \
assumption the user made when they provided you the objective.
2. Consider if the objective is accomplished at this point.
3. Consider if the last message in the thread provides a response to the objective.
4. Consider if the remaining steps are appropriate based on your previous analysis.
{reasoning_step if is_reasoning(agent) else ''}

Next:

1. Set the "response_type" field based on the following criteria:
    - If the objective is accomplished and the last message in the thread provides a response to \
the objective, set the response type to "complete-as-is".
    - If the objective is accomplished but the last message in the thread does not provide a \
response to the objective, set the response type to "response-needed".
    - If the work needed to respond to the objective is not done yet, update the plan and set the \
response type to "update".
    - If the plan cannot be completed without more information or after prompting the user for \
some sort of input, set the response type to "edge-case".
2. Update the plan as needed based on your analysis. When doing so, remove steps that have already \
been completed and only add steps to the plan that still NEED to be done. Assume these new steps \
will be followed.
3. Based on your analysis, write a final response or reply to the user to explain any edge cases \
encountered, if any.
</instructions>

Objective: <objective>
{{objective}}
</objective>
        """.strip()

        next_response_prompt = """
Now, compare the last step executed above to the expected step executed \
and remaining steps below and begin your analysis.

Last step executed: <last_step>
{last_step}
</last_step>

Remaining planned steps: <remaining_steps>
{remaining_steps}
</remaining_steps>
        """.strip()

        return [
            ("system", main_replanner_prompt),
            ("placeholder", "{messages}"),
            ("system", next_response_prompt),
        ]
