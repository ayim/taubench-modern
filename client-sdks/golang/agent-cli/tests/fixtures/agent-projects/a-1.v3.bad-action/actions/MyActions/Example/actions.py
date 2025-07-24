from sema4ai.actions import action

@action
def no_docs_for_action_parameter(argument_without_docs: str) -> bool:
    """
    This action is used to check if the action has no docs.

    Returns:
        A boolean value.
    """
    return False
