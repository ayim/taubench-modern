from functools import wraps

from agent_server_types_v2.agent_architectures.utils import (
    extract_kernel_and_create_or_get_state,
    restore_state_fields,
    rollback_state_fields,
    update_state_fields,
    validate_2param_async,
)


def entrypoint(func):
    """
    Decorator for an entrypoint function.

    Ensures that the function:
      - takes a Kernel instance as its first argument,
      - takes a dataclass state as its second argument.

    It automatically restores state (before executing the function)
    and updates/saves state (after executing the function).
    """
    # Validate the function signature and async nature.
    sig = validate_2param_async(func)

    @wraps(func) # TODO: type the wrapper how we want (kernel, state...)
    async def wrapper(*args, **kwargs):
        # Extract and validate kernel and state.
        kernel, state = extract_kernel_and_create_or_get_state(sig, *args, **kwargs)

        # Grab the scoped storages for the state fields.
        new_scoped_storage_ids = await restore_state_fields(kernel, state)

        # Execute the decorated async function.
        try:
            # Run our Agent Architecture.
            result = await func(kernel, state)

            # Save the state fields.
            await update_state_fields(kernel, state)

            # Return the result.
            return result
        except Exception as e:
            # If the function raises an exception, delete any new scoped storages.
            await rollback_state_fields(kernel, new_scoped_storage_ids)
            raise e

    return wrapper
