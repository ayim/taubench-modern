from functools import wraps

from opentelemetry.trace import StatusCode

from agent_platform.core.agent_architectures.utils import (
    extract_kernel_and_create_or_get_state,
    restore_state_fields,
    rollback_state_fields,
    update_state_fields,
    validate_2param_async,
)


def step(func):
    """
    Decorator for a step function.

    Ensures that the function:
      - takes a Kernel instance as its first argument,
      - takes a dataclass state as its second argument.

    It automatically restores state (before executing the function)
    and updates/saves state (after executing the function).
    """
    # Validate the function signature and async nature.
    sig = validate_2param_async(func)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract and validate kernel and state.
        kernel, state = extract_kernel_and_create_or_get_state(sig, *args, **kwargs)

        # Extract step name from function
        step_name = func.__name__

        with kernel.ctx.start_span(
            f"agent_step_{step_name}",
            attributes={
                "langsmith.span.kind": "chain",
                "langsmith.trace.name": f"Agent Step: {step_name}",
                "step.name": step_name,
                "agent.id": kernel.agent.agent_id,
                "thread.id": kernel.thread.thread_id,
                "agent.name": kernel.agent.name,
            },
        ) as span:
            # Capture initial state if span exists
            try:
                span.set_attribute("input.value", state.serialize())  # type: ignore
            except Exception:
                pass

            # Restore the state fields.
            new_scoped_storage_ids = await restore_state_fields(kernel, state)

            try:
                # Execute the step.
                result = await func(kernel, state)

                # Record success information if span exists
                try:
                    span.set_attribute("output.value", state.serialize())  # type: ignore

                    # Add result info if available
                    if result is not None:
                        result_summary = str(result)
                        span.set_attribute("step.result", result_summary)
                except Exception:
                    pass

                # Save the state fields.
                await update_state_fields(kernel, state)

                # Return the result.
                return result
            except Exception as e:
                # Record error if span exists
                span.set_attribute("error", str(e))
                span.set_attribute("error.type", type(e).__name__)
                span.set_status(StatusCode.ERROR)

                # If the function raises an exception, delete any new scoped storages.
                await rollback_state_fields(kernel, new_scoped_storage_ids)
                raise e

    return wrapper
