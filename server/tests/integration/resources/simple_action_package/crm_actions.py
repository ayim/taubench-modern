import uuid
from typing import TypedDict

from sema4ai.actions import Response, action  # type: ignore


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
