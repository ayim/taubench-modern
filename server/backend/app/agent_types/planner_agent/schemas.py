import operator
import os
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage, get_buffer_string
from langchain_core.pydantic_v1 import BaseModel, Field

from app.agent_types.tools_agent import AgentState

STEP_FORMAT_SEPARATOR = " - "

RESPONSE_STEP_DESCRIPTIONS = {
    "with_reasoning": """The steps to follow in the future. Respond as a list of tuples with each tuple \
containing only two strings. The first part is your thinking about why the step is needed. \
The second part is the step itself and any additional details you think are important for \
your team members to know when performing the step. It is critically important that these \
steps are not repeats of the steps already taken.""",
    "without_reasoning": """The steps to follow in the future. Include any additional details you \
think are important for your team members to know when performing the step. It is critically \
important that these steps are not repeats of the steps already taken.""",
}

ResponseType = Literal[
    "complete-as-is",
    "response-needed",
    "update",
    "edge-case",
]


class PlanStep(BaseModel):
    """A step in a plan."""

    step: str = Field(..., description="The step to take.")

    def formatted(self) -> str:
        return f"{STEP_FORMAT_SEPARATOR}{self.step}"


class PlanStepWithThought(PlanStep):
    """A step in a plan with a thought."""

    reasoning: str = Field(
        ...,
        description="Thinking about what the step should be, why it's in the plan and what it will accomplish.",
    )

    def formatted(self) -> str:
        return f"{STEP_FORMAT_SEPARATOR}_(Reasoning: {self.reasoning})_ {self.step}"


class PastStep(BaseModel):
    """A completed step in a plan."""

    original_step: PlanStep = Field(..., description="The original step.")
    outcome: list[AnyMessage] = Field(
        ..., description="The thread produced by executing the step."
    )

    def as_buffer_string(self) -> str:
        """Returns the outcome as a buffer string."""
        return get_buffer_string(self.outcome)


class Plan(BaseModel):
    """The plan to be executed."""

    objective: str = Field(..., description="The objective of the plan.")
    steps: list[PlanStep] = Field(
        default_factory=list,
        description="The steps in the plan. In order of planned execution.",
    )

    def formatted(self, with_objective: bool = True) -> str:
        list_str = f"{os.linesep.join(step.formatted() for step in self.steps)}"
        if with_objective:
            return f"Plan for objective '{self.objective}':\n{list_str}"
        else:
            return list_str

    def steps_as_string(self) -> str:
        """Returns the steps as a string.

        Example:

            ['Step 1', 'Step 2', 'Step 3']
        """
        return str(self.steps_as_list())

    def steps_as_list(self) -> list[str]:
        """Returns the steps as a list.

        The return should exactly match how the LLM created the steps via
        the response models.
        """
        return [step.step for step in self.steps]


class PlanWithThought(Plan):
    """The plan to be executed with a thought."""

    thought: str = Field(
        ...,
        description="Thinking about what the plan should be, why it's needed, and what it will accomplish.",
    )
    steps: list[PlanStepWithThought] = Field(
        default_factory=list,
        description="The steps in the plan. In order of planned execution.",
    )

    def steps_as_list(self) -> list[tuple[str, str]]:
        """Returns the steps as a list.

        The return should exactly match how the LLM created the steps via
        the response models.
        """
        return [(step.reasoning, step.step) for step in self.steps]


class ExecutedPlan(BaseModel):
    """A set of past steps and related thoughts based on an original plan."""

    original_plan: Plan = Field(
        ..., description="The original plan prior to any execution."
    )
    past_steps: list[PastStep] = Field(..., description="The steps that were executed.")


class ExecutedPlanWithThought(ExecutedPlan):
    """A set of past steps and related thoughts based on an original plan with a thought."""

    thought: str | None = Field(
        None,
        description="Thinking about the plan and its execution, including differences between the original plan and what was done.",
    )
    past_steps: list[PastStep] = Field(..., description="The steps that were executed.")


class CompletedPlan(ExecutedPlan):
    """A set of past steps and related thoughts based on an original plan."""

    output: str | None = Field(None, description="The output of the plan.")


class CompletedPlanWithThought(CompletedPlan, ExecutedPlanWithThought):
    """A set of past steps and related thoughts based on an original plan with a thought."""


# The overall state
class PlanExecuteAgentState(AgentState):
    """The state of the agent executing a plan."""

    objective: str | None = Field(
        None, description="The objective of the plan parsed from the recent user input"
    )
    plan_needed: bool | None = Field(
        False, description="Whether the offramper decided if a plan was needed."
    )

    original_plan: Plan | None = Field(
        None, description="The original plan for the current run."
    )
    current_plan: Plan | None = Field(
        None, description="The current plan with remaining steps."
    )
    executed_plan: ExecutedPlan | None = Field(
        None, description="The executed plan so far."
    )

    completed_plans: Annotated[list[CompletedPlan], operator.add]

    response_type: ResponseType | None = Field(
        None, description="The type of response from the replanner."
    )
    response: str | None = Field(None, description="The response to the user.")


# Initial offramp reponse
class InitialThinkingPlanningResponse(BaseModel):
    """Your initial planning response. You should include your thinking as to why or why not a
    plan is needed as well as the actual plan if one is needed. If you do not think you can
    create a plan with the context provided, you can request more context via the appropriate field.
    """

    reasoning: str = Field(
        ...,
        description="Your thinking as to why or why not a plan is needed to accomplish the objective. "
        "If needed, explain why a plan is needed and what it will accomplish. If not needed, explain why.",
    )
    plan_needed_response: Literal["plan", "no-plan", "full-context-needed"] = Field(
        description="Whether a plan is needed to accomplish the objective or if you need the full "
        "context of the conversation to decide and develop the plan."
    )
    steps: list[tuple] | None = Field(
        None,
        description=RESPONSE_STEP_DESCRIPTIONS["with_reasoning"],
    )


class InitialPlanningResponse(BaseModel):
    """Your initial planning response, including the plan if needed. If you do not think you can
    create a plan with the context provided, you can request more context via the appropriate field.
    """

    plan_needed_response: Literal["plan", "no-plan", "full-context-needed"] = Field(
        description="Whether a plan is needed to accomplish the objective or if you need the full "
        "context of the conversation to decide and develop the plan."
    )
    steps: list[str] | None = Field(
        None,
        description=RESPONSE_STEP_DESCRIPTIONS["without_reasoning"],
    )


### Step Executor Responses
# Step executor responses are not currently used but would be used if the step executor
# was rewritten to no longer use the tools agent as a subagent.
class StepExecutorThinkerResponse(BaseModel):
    """Thinking about what the step was versus what was done, as well
    as your response to the team thread based on the step you just executed.
    """

    reasoning: str = Field(
        ...,
        description="Thinking about what the step was versus what was done",
    )
    response: str = Field(
        ...,
        description="Your response to the team thread based on the step you just executed.",
    )


class StepExecutorResponse(BaseModel):
    """Your response to the team thread based on the step you just executed."""

    response: str = Field(
        ...,
        description="Your response to the team thread based on the step you just executed.",
    )


class StepReflectionResponse(BaseModel):
    """Your reflection on the step the team just executed."""

    thought: str = Field(
        ...,
        description="Thinking about what the step was, what was done, and what that means for the plan.",
    )


# Replanner responses
class ReplannerThinkerResponse(BaseModel):
    """Your thinking on the current plan and whether it needs to be updated, and how to update
    it if needed. If you think the plan is impossible to complete, you should explain why and
    provide a warning to the user.
    """

    reasoning: str = Field(
        ...,
        description="Your thinking on the current plan and whether it needs to be updated, if it "
        "is complete, or if it is impossible to complete. If you are updating the plan with new steps, "
        "explain why the additional steps are necessary.",
    )
    response_type: ResponseType = Field(
        ...,
        description="The type of response you are providing.",
    )
    response: str | None = Field(
        None,
        description="Only use this parameter if response_type is 'response-needed'. "
        "If the last message in the thread was not sufficient to respond to the "
        "objective, create and provide a response here, otherwise ignore.",
    )
    new_steps: list[tuple] | None = Field(
        None,
        description="Only use this parameter if the response_type is 'update'. "
        + RESPONSE_STEP_DESCRIPTIONS["with_reasoning"],
    )
    edge_case_reply: str | None = Field(
        None,
        description="Only use this parameter if the response_type is 'edge-case'. "
        "The reply to the user explaining the edge case.",
    )


class ReplannerResponse(BaseModel):
    """Whether the current plan is complete or needs to be updated."""

    response_type: ResponseType = Field(
        ...,
        description="The type of response you are providing.",
    )
    response: str | None = Field(
        None,
        description="Only use this parameter if response_type is 'response-needed'. "
        "If the last message in the thread was not sufficient to respond to the "
        "objective, create and provide a response here, otherwise ignore.",
    )
    new_steps: list[str] | None = Field(
        None,
        description="Only use this parameter if response_type is 'update'. "
        + RESPONSE_STEP_DESCRIPTIONS["without_reasoning"],
    )
    edge_case_reply: str | None = Field(
        None,
        description="Only use this parameter if the response_type is 'edge-case'. "
        "The reply to the user explaining the edge case.",
    )
