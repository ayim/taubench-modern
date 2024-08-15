from langchain_core.prompts import ChatPromptTemplate

PLAN_DESCRIPTION = """Plans are generally only required for more complex objectives which \
would benefit from multiple rounds of interaction with various tools to complete, especially \
where the expected output from one tool needs to be used as input into future tools. If you \
think you already know how to respond, or the user seems to want to chat (for example, they \
say "hello"), or you think one of the available tools could be used in a single shot, we \
would not need a plan. When creating the plan, think about the various steps needed to \
accomplish the objective and what information is needed for each step. Each step is \
likely interconnected with the previous and following steps, so be sure to think about \
how each step builds on the previous one. If only one step is needed, a \
plan is not required."""

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


def planner_template(instructions: str) -> str:
    return f"""We use XML tags to help structure our team instructions. Runbooks \
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

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
{instructions}
</instructions>"""


PLANNER_PROMPTS: dict[int, ChatPromptTemplate] = {
    0: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                planner_template(
                    """Based on the full conversation that follows, you must decide \
if we need a plan to respond to the user.

If a plan is required, develop a step by step plan for the team. This plan should involve \
individual tasks that, when executed, will yield a meaninful response to the objective. \
The steps should be specific and each step should help to achieve the objective. The result \
of the final step should be a complete meaningful response to the objective. Make \
sure each step has all the information needed, assume every step will be followed."""
                ),
            ),
            ("placeholder", "{messages}"),
        ]
    ),
    1: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                planner_template(
                    """Based on the full conversation that follows, you must \
think about whether we need a plan to respond to the user. BE SUCCINCT. \
Succinctly explain your thinking about whether a plan is needed.

If a plan is needed, succinctly explain your approach. When developing the plan, succinctly think about \
each step and why it is needed. Include your thoughts in the response tool call. The plan should \
be specific and each step should help to achieve the objective. The result of the final step should \
be a complete meaningful response to the objective. Make sure each step has all the information \
needed, assume every step will be followed. Steps must be created as tuples of two strings: \
the first string is the reasoning why the step is needed and the second string is the step itself."""
                ),
            ),
            ("placeholder", "{messages}"),
        ]
    ),
    2: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                planner_template(
                    """Based on the full conversation that follows, you must \
think about whether we need a plan to respond to the user. \
Explain your thinking about whether a plan is needed.

If a plan is needed, explain your approach. When developing the plan, think about \
each step, why it is needed, and what information is needed by the assigned team member to \
complete it. Include your thoughts in the response tool call. The plan should \
be specific and each step should help to achieve the objective. The result of the final step should \
be a complete meaningful response to the objective. Make sure each step has all the information \
needed, assume every step will be followed. Steps must be created as tuples of two strings: \
the first string is the reasoning why the step is needed and the second string is the step itself."""
                ),
            ),
            ("placeholder", "{messages}"),
        ]
    ),
}

# Step Executor Prompts
STEP_EXECUTOR_ROLE = """You are part of a team of agents following the provided runbook. Your \
job is to execute the current step of the plan developed by the planner to complete the objective \
provided by the user."""


def step_executor_template() -> str:
    return f"""We use XML tags to help structure our team instructions. Runbooks \
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

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
The planner will provide you with a snippet of the current team thread, which may include messages \
from the user and other members of your team. The last message in this thread will be the step you \
need to execute.
</instructions>"""


# Prompts to override subagent built in prompts
STEP_EXECUTOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", step_executor_template()),
        ("placeholder", "{messages}"),
        ("system", "Now execute the step provided above."),
    ]
)
STEP_REASONING_PROMPTS = {
    1: ChatPromptTemplate.from_messages(
        [
            ("system", step_executor_template()),
            ("placeholder", "{messages}"),
            (
                "system",
                "Think about your next response based on the conversation so far and succinctly "
                "explain why you are thinking to respond in this way. Focus on the most important aspects "
                "of your reasoning. ONLY PROVIDE REASONING.",
            ),
        ]
    ),
    2: ChatPromptTemplate.from_messages(
        [
            ("system", step_executor_template()),
            ("placeholder", "{messages}"),
            (
                "system",
                "Think about your next response based on the conversation so far and explain "
                "why you are thinking to respond in this way. If you are thinking about calling tools, "
                "also explain what parameters you are thinking of using and why. ONLY PROVIDE REASONING.",
            ),
        ]
    ),
}
STEP_RETRY_REASONING_PROMPTS = {
    1: ChatPromptTemplate.from_messages(
        [
            ("system", step_executor_template()),
            ("placeholder", "{messages}"),
            (
                "system",
                "You provided a tool call with your thinking, which is not allowed at this time. "
                "Please provide your thoughts without tool calls. You should succinctly explain why you are "
                "thinking to call the tool.",
            ),
        ]
    ),
    2: ChatPromptTemplate.from_messages(
        [
            ("system", step_executor_template()),
            ("placeholder", "{messages}"),
            (
                "system",
                "You provided a tool call with your thinking, which is not allowed at this time. "
                "Please provide your thoughts without tool calls. You should explain why you are thinking "
                "to call the tool and which parameters you are thinking of using.",
            ),
        ]
    ),
}


# Replanner related prompts and messages
REPLANNER_ROLE = """You are part of a team of agents following the provided runbook. Your \
job is to update the current plan to complete the objective provided by the user."""


def replanner_template(instructions: str) -> str:
    return f"""We use XML tags to help structure our team instructions. Runbooks \
use markdown to format structured content.

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

Our runbook: <runbook>
{{runbook}}
</runbook>

Your immediate instructions: <instructions>
{instructions}
</instructions>"""


REPLANNER_PROMPTS: dict[int, ChatPromptTemplate] = {
    0: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                replanner_template(
                    """The below objective is the last message from the user. Following that is \
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

Next:

5. Set the "response_type" field based on the following criteria:
    - If the objective is accomplished and the last message in the thread provides a response to \
the objective, set the response type to "complete-as-is".
    - If the objective is accomplished but the last message in the thread does not provide a \
response to the objective, set the response type to "response-needed".
    - If the work needed to respond to the objective is not done yet, update the plan and set the \
response type to "update".
    - If the plan cannot be completed without more information or after prompting the user for \
some sort of input, set the response type to "edge-case".
6. Update the plan as needed based on your analysis. When doing so, remove steps that have already \
been completed and only add steps to the plan that still NEED to be done. Assume these new steps \
will be followed.
8. Based on your analysis, write a final response or reply to the user to explain any edge cases \
encountered, if any.

Objective: <objective>
{objective}
</objective>"""
                ),
            ),
            ("placeholder", "{messages}"),
            (
                "system",
                """Now, compare the last step executed above to the expected step executed \
and remaining steps below and begin your analysis.

Last step executed: <last_step>
{last_step}
</last_step>

Remaining planned steps: <remaining_steps>
{remaining_steps}
</remaining_steps>""",
            ),
        ]
    ),
    1: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                replanner_template(
                    """The below objective is the last message from the user. Following that is \
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
5. Using the response tool, succinctly write out your thoughts for these points in the "reasoning" field.

Next:

6. Set the "response_type" field based on the following criteria:
    - If the objective is accomplished and the last message in the thread provides a response to \
the objective, set the response type to "complete-as-is".
    - If the objective is accomplished but the last message in the thread does not provide a \
response to the objective, set the response type to "response-needed".
    - If the work needed to respond to the objective is not done yet, update the plan and set the \
response type to "update".
    - If the plan cannot be completed without more information or after prompting the user for \
some sort of input, set the response type to "edge-case".
7. Update the plan as needed based on your analysis. When doing so, remove steps that have already \
been completed and only add steps to the plan that still NEED to be done. Assume these new steps \
will be followed. Be sure to follow the correct format by creating a tuple of two strings for \
each step: the first string is the reasoning why the step is needed and the second string is \
the step itself.
8. Based on your analysis, write a final response or reply to the user to explain any edge cases \
encountered, if any.

Objective: <objective>
{objective}
</objective>"""
                ),
            ),
            ("placeholder", "{messages}"),
            (
                "system",
                """Now, compare the last step executed above to the expected step executed \
and remaining steps below and begin your analysis.
             
Last step executed: <last_step>
{last_step}
</last_step>

Remaining planned steps: <remaining_steps>
{remaining_steps}
</remaining_steps>""",
            ),
        ]
    ),
    2: ChatPromptTemplate.from_messages(
        [
            (
                "system",
                replanner_template(
                    """The below objective is the last message from the user. Following that is \
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
5. Using the response tool, write out your thoughts for these points in the "reasoning" field.

Next:

6. Set the "response_type" field based on the following criteria:
    - If the objective is accomplished and the last message in the thread provides a response to \
the objective, set the response type to "complete-as-is".
    - If the objective is accomplished but the last message in the thread does not provide a \
response to the objective, set the response type to "response-needed".
    - If the work needed to respond to the objective is not done yet, update the plan and set the \
response type to "update".
    - If the plan cannot be completed without more information or after prompting the user for \
some sort of input, set the response type to "edge-case".
7. Update the plan as needed based on your analysis. When doing so, remove steps that have already \
been completed and only add steps to the plan that still NEED to be done. Assume these new steps \
will be followed. Be sure to follow the correct format by creating a tuple of two strings for \
each step: the first string is the reasoning why the step is needed and the second string is \
the step itself.
8. Based on your analysis, write a final response or reply to the user to explain any edge cases \
encountered, if any.

Objective: <objective>
{objective}
</objective>"""
                ),
            ),
            ("placeholder", "{messages}"),
            (
                "system",
                """Now, compare the last step executed above to the expected step executed \
and remaining steps below and begin your analysis.
             
Last step executed: <last_step>
{last_step}
</last_step>

Remaining planned steps: <remaining_steps>
{remaining_steps}
</remaining_steps>""",
            ),
        ]
    ),
}
