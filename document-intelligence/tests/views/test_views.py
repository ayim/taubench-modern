import pytest

from sema4ai_docint.views import SchemaField
from sema4ai_docint.views.views import transform_business_schema


class TestTransformBusinessSchema:
    """Tests for the transform_business_schema function."""

    def _assert_field(
        self,
        actual_fields: list[SchemaField],
        expected_name: str,
        expected_path: str,
        expected_format: str | None = None,
    ) -> SchemaField:
        found_fields = [f for f in actual_fields if f.name == expected_name]
        assert len(found_fields) == 1, (
            f"Expected 1 field with name {expected_name}, but got fields: {found_fields}"
        )

        actual = found_fields[0]
        assert actual.path == expected_path
        if expected_format:
            assert actual.format is not None
            assert actual.format.type == expected_format
        else:
            assert actual.format is None
        return actual

    def test_transform_simple_schema(self):
        """Test transforming a simple schema with basic types."""
        input_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "active": {"type": "boolean"},
            },
        }

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 3
        self._assert_field(result.fields, "NAME", "name", "string")
        self._assert_field(result.fields, "AGE", "age", "number")
        self._assert_field(result.fields, "ACTIVE", "active", "boolean")

    def test_transform_nested_schema(self):
        """Test transforming a schema with nested objects."""
        input_schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {
                                "street": {"type": "string"},
                                "city": {"type": "string"},
                            },
                        },
                    },
                }
            },
        }

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 3
        self._assert_field(result.fields, "USER_NAME", "user.name", "string")
        self._assert_field(result.fields, "USER_ADDRESS_STREET", "user.address.street", "string")
        self._assert_field(result.fields, "USER_ADDRESS_CITY", "user.address.city", "string")

    def test_transform_array_schema(self):
        """Test transforming a schema with arrays."""
        input_schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "quantity": {"type": "number"},
                        },
                    },
                }
            },
        }

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 2
        self._assert_field(result.fields, "ITEMS_ID", "items[].id", "string")
        self._assert_field(result.fields, "ITEMS_QUANTITY", "items[].quantity", "number")

    def test_transform_enum_schema(self):
        """Test transforming a schema with enum values."""
        input_schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "inactive", "pending"]}},
        }

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 1
        self._assert_field(result.fields, "STATUS", "status", "string")
        # Validate the enum
        assert result.fields[0].format.attributes == {"enum": ["active", "inactive", "pending"]}

    def test_transform_complex_schema(self):
        """Test transforming a complex schema with nested arrays and objects."""
        input_schema = {
            "type": "object",
            "properties": {
                "orders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product": {"type": "string"},
                                        "quantity": {"type": "number"},
                                    },
                                },
                            },
                        },
                    },
                }
            },
        }

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 3
        self._assert_field(result.fields, "ORDERS_ID", "orders[].id", "string")
        self._assert_field(
            result.fields, "ORDERS_ITEMS_PRODUCT", "orders[].items[].product", "string"
        )
        self._assert_field(
            result.fields,
            "ORDERS_ITEMS_QUANTITY",
            "orders[].items[].quantity",
            "number",
        )

    def test_transform_empty_schema(self):
        """Test transforming an empty schema."""
        input_schema = {"type": "object", "properties": {}}

        result = transform_business_schema(input_schema)

        assert len(result.fields) == 0

    def test_transform_missing_type(self):
        """Expect that we have a top-level 'type' property."""
        input_schema = {}

        with pytest.raises(ValueError, match="must have a type"):
            transform_business_schema(input_schema)

    def test_transform_schema_not_object(self):
        """Expect that our schema describes a type=object"""
        input_schema = {
            "type": "array",
            "items": {"type": "object", "properties": {"name": {"type": "string"}}},
        }

        with pytest.raises(ValueError, match="must be an object"):
            transform_business_schema(input_schema)

    def test_transform_missing_properties(self):
        """Test transforming an invalid schema."""
        input_schema = {
            "type": "object"
            # Missing properties
        }

        with pytest.raises(ValueError, match="must have properties"):
            transform_business_schema(input_schema)

    def test_transform_real_world_schema(self):
        """Test transforming a real-world schema example."""
        input_schema = {
            "type": "object",
            "required": [
                "totalInvoiceAmount",
                "dueDate",
                "invoiceNumber",
                "transactions",
            ],
            "properties": {
                "dueDate": {"type": "string"},
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "tradeDate",
                            "pipeline",
                            "meter",
                            "volume",
                            "tradeId",
                            "pricePerUnit",
                            "type",
                            "totalAmount",
                        ],
                        "properties": {
                            "type": {"enum": ["buy", "sell"], "type": "string"},
                            "meter": {"type": "string"},
                            "volume": {"type": "number"},
                            "tradeId": {"type": "string"},
                            "pipeline": {"type": "string"},
                            "tradeDate": {"type": "string"},
                            "totalAmount": {"type": "number"},
                            "pricePerUnit": {"type": "number"},
                        },
                    },
                },
                "invoiceNumber": {"type": "string"},
                "totalInvoiceAmount": {"type": "number"},
            },
        }

        result = transform_business_schema(input_schema)

        # Check root level fields
        self._assert_field(result.fields, "DUEDATE", "dueDate", "string")
        self._assert_field(result.fields, "INVOICENUMBER", "invoiceNumber", "string")
        self._assert_field(result.fields, "TOTALINVOICEAMOUNT", "totalInvoiceAmount", "number")

        # Check transaction fields
        tt = self._assert_field(result.fields, "TRANSACTIONS_TYPE", "transactions[].type", "string")
        assert tt.format.attributes == {"enum": ["buy", "sell"]}

        self._assert_field(result.fields, "TRANSACTIONS_METER", "transactions[].meter", "string")
        self._assert_field(result.fields, "TRANSACTIONS_VOLUME", "transactions[].volume", "number")
        self._assert_field(
            result.fields, "TRANSACTIONS_TRADEID", "transactions[].tradeId", "string"
        )
        self._assert_field(
            result.fields, "TRANSACTIONS_PIPELINE", "transactions[].pipeline", "string"
        )
        self._assert_field(
            result.fields,
            "TRANSACTIONS_TRADEDATE",
            "transactions[].tradeDate",
            "string",
        )
        self._assert_field(
            result.fields,
            "TRANSACTIONS_TOTALAMOUNT",
            "transactions[].totalAmount",
            "number",
        )
        self._assert_field(
            result.fields,
            "TRANSACTIONS_PRICEPERUNIT",
            "transactions[].pricePerUnit",
            "number",
        )
