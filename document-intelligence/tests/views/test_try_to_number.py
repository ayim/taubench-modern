from decimal import Decimal

import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123", Decimal("123")),
        ("123.45", Decimal("123.45")),
        ("123,456.78", Decimal("123456.78")),
        ("-123,456.789", Decimal("-123456.789")),
        ("$123,456.7890", None),  # a dollar sign is not a number
        ("", None),
        ("-$1234.34", None),
        ("HeyBob", None),  # cannot convert a string to a number
        ("123,45", None),  # we expect US-style numbers.
    ],
)
def test_try_to_number(setup_db, value, expected):
    conn = setup_db

    with conn.cursor() as cursor:
        cursor.execute(f"SELECT try_to_number('{value}') as n")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == expected
