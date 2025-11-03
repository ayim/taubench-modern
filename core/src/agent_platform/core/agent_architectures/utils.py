from asyncio import iscoroutinefunction
from dataclasses import is_dataclass
from inspect import signature

import structlog

from agent_platform.core.agent_architectures.fields import get_fields_by_scope
from agent_platform.core.kernel import Kernel
from agent_platform.core.storage import ScopedStorage

logger: structlog.BoundLogger = structlog.get_logger(__name__)


def validate_2param_async(func, param_names=("kernel", "state")):
    """
    Validates that the function:
      - has at least the parameters provided in param_names (in order),
      - is an async function.

    Returns the function signature.
    """
    sig = signature(func)
    parameters = list(sig.parameters.values())
    if len(parameters) < len(param_names):
        raise ValueError(
            f"Function must have at least {len(param_names)} parameters: {', '.join(param_names)}",
        )
    for index, expected_name in enumerate(param_names):
        param = parameters[index]
        if param.name != expected_name:
            raise ValueError(
                f"Parameter {index + 1} must be named '{expected_name}', "
                f"found '{param.name}' instead.",
            )
    if not iscoroutinefunction(func):
        raise ValueError("Function must be an async function.")
    return sig


def extract_kernel_and_create_or_get_state(sig, *args, **kwargs):
    """
    Binds arguments according to the signature, applies defaults,
    extracts kernel from the provided arguments, and then either uses the provided
    state object (if present in bound arguments) or creates a fresh state object
    based on the type annotation.

    This function expects both 'kernel' and 'state' to be present in the signature.
    If state is in the bound arguments, it is used; otherwise,
    a new instance is created.

    Validates that:
      - `kernel` is an instance of Kernel,
      - The state parameter has a proper type annotation and it's a dataclass type.
      - If state is provided in arguments, it matches the expected type annotation.

    Returns:
         (kernel, state)
    """
    # Get parameter names (assuming first two are kernel and state)
    kernel_param, state_param = list(sig.parameters)[:2]

    # Handle case where only kernel is provided
    if len(args) == 1 and not kwargs:
        kernel = args[0]
    else:
        # Original binding logic for when both params are provided
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        kernel = bound.arguments[kernel_param]

    if not isinstance(kernel, Kernel):
        raise TypeError("The first argument must be an instance of Kernel.")

    state_annotation = sig.parameters[state_param].annotation
    if state_annotation is sig.empty:
        raise TypeError(
            "The state parameter must have a type annotation for its dataclass type.",
        )
    if not isinstance(state_annotation, type) or not is_dataclass(state_annotation):
        raise TypeError("State parameter annotation must be a dataclass type.")

    # If we have bound arguments and state was provided, validate and use it
    if len(args) > 1 or kwargs:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if state_param in bound.arguments:
            state = bound.arguments[state_param]
            if not isinstance(state, state_annotation):
                raise TypeError(
                    f"Provided state must be an instance of {state_annotation.__name__}",
                )
            return kernel, state

    # Create a fresh state object if none was provided in arguments
    new_state = state_annotation()
    return kernel, new_state


async def restore_state_fields(
    kernel,
    state,
    scopes=("user", "thread", "agent"),
) -> list[str]:
    """
    Iterates over the provided scopes and restores each field from storage
    into the provided state.

    If a given field does not already exist in storage, creates it.
    """
    from agent_platform.server.storage.errors import ScopedStorageNotFoundError

    new_scoped_storage_ids = []
    for scope in scopes:
        for field in get_fields_by_scope(state, scope):
            scoped_storage = ScopedStorage.from_scope_field_value(
                scope=scope,
                field_name=field,
                created_by_user_id=kernel.user.user_id,
                created_by_agent_id=kernel.agent.agent_id,
                created_by_thread_id=kernel.thread.thread_id,
            )
            try:
                rehydrated = await kernel.storage.get_scoped_storage(
                    scoped_storage.storage_id,
                )
                setattr(state, field, rehydrated.storage)
            except (Exception, ScopedStorageNotFoundError) as e:
                if not isinstance(e, ScopedStorageNotFoundError):
                    # If not found something bad may have happened (anyways, log and continue)
                    logger.error(f"Error restoring state field {field}: {e}", exc_info=True)
                scoped_storage.storage = getattr(state, field)
                await kernel.storage.create_scoped_storage(scoped_storage)
                new_scoped_storage_ids.append(scoped_storage.storage_id)

    return new_scoped_storage_ids


async def update_state_fields(kernel, state, scopes=("user", "thread", "agent")):
    """
    Iterates over the provided scopes and updates (saves) each field from the state
    back to storage.
    """
    for scope in scopes:
        for field in get_fields_by_scope(state, scope):
            scoped_storage = ScopedStorage.from_scope_field_value(
                scope=scope,
                field_name=field,
                created_by_user_id=kernel.user.user_id,
                created_by_agent_id=kernel.agent.agent_id,
                created_by_thread_id=kernel.thread.thread_id,
            )
            scoped_storage.storage = getattr(state, field)
            await kernel.storage.update_scoped_storage(scoped_storage)


async def rollback_state_fields(kernel, scoped_storage_ids):
    """
    Removes the scoped storages that were created during the execution of the
    decorated function.
    """
    for scoped_storage_id in scoped_storage_ids:
        # Delete the scoped storage.
        await kernel.storage.delete_scoped_storage(scoped_storage_id)
