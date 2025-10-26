import time
import uuid
from typing import TypedDict

from sema4ai.actions import ActionError, Response, action  # type: ignore


class CustomerData(TypedDict):
    name: str
    email: str
    phone: str


contact_details: dict[str, CustomerData] = {
    "1": {"name": "John Doe", "email": "john.doe@example.com", "phone": "1234567890"},
    "2": {"name": "Jane Doe", "email": "jane.doe@example.com", "phone": "1234567890"},
}


@action
def add_contact(name: str, email: str, phone: str) -> Response[str]:
    """
    Adds a new contact to the CRM.

    Args:
        name: The name of the contact.
        email: The email address of the contact.
        phone: The phone number of the contact.

    Returns:
        True if the contact was added successfully.
    """
    contact_id = str(uuid.uuid4())
    contact_details[contact_id] = {"name": name, "email": email, "phone": phone}
    return Response(result=contact_id)


@action
def calculate(expression: str) -> Response[str]:
    """
    Performs basic mathematical calculations.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5").

    Returns:
        The result of the mathematical calculation.
    """
    try:
        # Simple safe evaluation for basic math operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return Response(
                error="Invalid characters in expression. Only numbers and +, -, *, /, (, ) are allowed."  # noqa: E501
            )

        result = eval(expression)
        return Response(result=f"The result of {expression} is {result}")
    except Exception as e:
        return Response(error=f"Error evaluating expression: {e!s}")


@action
def sleep_action(duration_seconds: float = 1.0) -> Response[str]:
    """
    A test action that sleeps for a specified duration.
    Useful for testing async action behavior.

    Args:
        duration_seconds: The number of seconds to sleep (default: 1.0).

    Returns:
        A message indicating the action completed after the specified duration.
    """
    time.sleep(duration_seconds)
    return Response(result=f"Action completed after sleeping for {duration_seconds} seconds")


@action
def sleep_then_error_action(sleep_seconds: float = 2.0) -> Response[str]:
    """
    A test action that sleeps for a specified duration and then raises an error.
    Useful for testing async action error handling - the sleep forces async mode,
    then the error tests our enhanced error handling logic.

    Args:
        sleep_seconds: The number of seconds to sleep before erroring (default: 2.0).

    Returns:
        Always raises an ActionError after sleeping.
    """
    time.sleep(sleep_seconds)
    raise ActionError(f"This is an error after sleeping for {sleep_seconds} seconds")
    return Response(error="This should not reach here")


@action
def raise_unexpected_action_error() -> str:
    """
    A test action that raises an unexpected ActionError.

    Returns:
        Always raises an ActionError.
    """
    raise ActionError("UNEXPECTED ACTION ERROR IS RAISED")
    return ""


@action
def raise_unexpected_value_error() -> str:
    """
    A test action that raises an unexpected ValueError.

    Returns:
        Always raises a ValueError.
    """
    raise ValueError("UNEXPECTED VALUE ERROR IS RAISED")
    return ""


@action
def update_contact_email(contact_id: str, new_email: str) -> Response[str]:
    """
    Updates the email address of an existing contact.

    Args:
        contact_id: The ID of the contact to update.
        new_email: The new email address for the contact.

    Returns:
        True if the email was updated successfully.
    """
    if contact_id in contact_details:
        contact_details[contact_id]["email"] = new_email
        print(f"Contact {contact_id} email updated to {new_email}")
        return Response(result=f"Contact {contact_id} email updated to {new_email}")
    else:
        print(f"Contact {contact_id} not found")
        return Response(error=f"Contact {contact_id} not found")


@action
def always_error_action_action_response(
    message: str = "This action always errors for testing",
) -> Response[str]:
    """
    A test action that always returns an error.

    Args:
        message: Optional custom error message to return.

    Returns:
        A Response with the error field populated.
    """
    return Response(error=message)


@action
def always_error_action_internal_error() -> str:
    """
    A test action that always errors out internally.
    """
    raise ValueError("This is an error")
    # unreachable, but returning a string
    # to satisfy the type checker
    return "Unreachable"


@action
def list_contacts() -> dict:
    """
    Lists all contacts in the CRM.

    Returns:
        A dictionary with the contact IDs as keys and the contact details as values.
    """
    return contact_details


@action
def delete_contact(contact_id: str) -> bool:
    """
    Deletes a contact from the CRM.

    Args:
        contact_id: The ID of the contact to delete.

    Returns:
        True if the contact was deleted successfully.
    """
    if contact_id in contact_details:
        del contact_details[contact_id]
        print(f"Contact {contact_id} deleted")
        return True
    else:
        print(f"Contact {contact_id} not found")
        return False


@action
def get_contact_details(contact_id: str) -> str:
    """
    Retrieves the details of a contact.

    Args:
        contact_id: The ID of the contact to retrieve.

    Returns:
        A string with the contact's details.
    """
    if contact_id in contact_details:
        contact = contact_details[contact_id]
        details = f"Contact {contact_id}: {contact['name']}, {contact['email']}, {contact['phone']}"
        print(details)
        return details
    else:
        print(f"Contact {contact_id} not found")
        return "Contact not found"


if __name__ == "__main__":
    print(get_contact_details("1"))
