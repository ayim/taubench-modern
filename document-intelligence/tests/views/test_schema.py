"""
Tests for the schema classes and transformation functions.
"""

import pytest

from sema4ai_docint.views import BusinessSchema, DataFormat, SchemaField, StandardTypes


class TestSchemaClasses:
    """Tests for the schema classes."""

    def test_data_format_creation(self):
        """Test that a DataFormat can be created with valid data."""
        # Basic format with just a type
        format1 = DataFormat(type="string")
        assert format1.type == "string"
        assert format1.attributes is None

        # Format with attributes
        format2 = DataFormat(type="string", attributes={"length": 50})
        assert format2.type == "string"
        assert format2.attributes == {"length": 50}

    def test_data_format_validation(self):
        """Test that DataFormat validates required fields."""
        # Missing type
        with pytest.raises(ValueError, match="Type is required"):
            DataFormat(type="")

        # Invalid type
        with pytest.raises(ValueError, match="Invalid type"):
            DataFormat(type="invalid_type")

    def test_data_format_from_dict(self):
        """Test creating a DataFormat from a dictionary."""
        # From string
        format1 = DataFormat.from_dict("string")
        assert format1.type == "string"
        assert format1.attributes is None

        # From dict with just type
        format2 = DataFormat.from_dict({"type": "number"})
        assert format2.type == "number"
        assert format2.attributes is None

        # From dict with type and attributes
        format3 = DataFormat.from_dict({"type": "string", "attributes": {"length": 100}})
        assert format3.type == "string"
        assert format3.attributes == {"length": 100}

    def test_data_format_to_dict(self):
        """Test converting a DataFormat to a dictionary."""
        # Format without attributes
        format1 = DataFormat(type="string")
        assert format1.to_dict() == {"type": "string"}

        # Format with attributes
        format2 = DataFormat(type="number", attributes={"precision": 10, "scale": 2})
        assert format2.to_dict() == {
            "type": "number",
            "attributes": {"precision": 10, "scale": 2},
        }

    def test_schema_field_creation(self):
        """Test that a SchemaField can be created with valid data."""
        # Create format
        format_data = DataFormat(type="string", attributes={"length": 50})

        # Create field with format
        field = SchemaField(path="customer.name", name="CUSTOMER_NAME", format=format_data)

        assert field.path == "customer.name"
        assert field.name == "CUSTOMER_NAME"
        assert field.format.type == "string"
        assert field.format.attributes == {"length": 50}

    def test_schema_field_validation(self):
        """Test that SchemaField validates required fields."""
        format_data = DataFormat(type="string")

        # Missing path
        with pytest.raises(ValueError, match="Path is required"):
            SchemaField(path="", name="FIELD", format=format_data)

        # Missing name
        with pytest.raises(ValueError, match="Name is required"):
            SchemaField(path="field", name="", format=format_data)

    def test_schema_field_from_dict(self):
        """Test that a SchemaField can be created from a dictionary."""
        # With format as a dictionary
        field1 = SchemaField.from_dict(
            {
                "path": "customer.name",
                "name": "CUSTOMER_NAME",
                "format": {"type": "string", "attributes": {"length": 50}},
            }
        )

        assert field1.path == "customer.name"
        assert field1.name == "CUSTOMER_NAME"
        assert field1.format.type == "string"
        assert field1.format.attributes == {"length": 50}

        # With format as string shorthand
        field2 = SchemaField.from_dict(
            {"path": "customer.active", "name": "IS_ACTIVE", "format": "boolean"}
        )

        assert field2.path == "customer.active"
        assert field2.name == "IS_ACTIVE"
        assert field2.format.type == "boolean"
        assert field2.format.attributes is None

        # Missing format should raise an error
        with pytest.raises(ValueError, match="Format is required"):
            SchemaField.from_dict({"path": "customer.id", "name": "CUSTOMER_ID"})

    def test_schema_field_to_dict(self):
        """Test that a SchemaField can be converted to a dictionary."""
        format_data = DataFormat(type="string", attributes={"length": 50})
        field = SchemaField(path="customer.name", name="CUSTOMER_NAME", format=format_data)

        data = field.to_dict()

        assert data == {
            "path": "customer.name",
            "name": "CUSTOMER_NAME",
            "format": {"type": "string", "attributes": {"length": 50}},
        }

    def test_business_schema_creation(self):
        """Test that a BusinessSchema can be created."""
        schema = BusinessSchema(
            fields=[
                SchemaField(path="field1", name="FIELD1", format=DataFormat(type="string")),
                SchemaField(path="field2", name="FIELD2", format=DataFormat(type="number")),
            ]
        )

        assert len(schema.fields) == 2
        assert schema.fields[0].path == "field1"
        assert schema.fields[1].path == "field2"

    def test_business_schema_from_dict(self):
        """Test that a BusinessSchema can be created from a dictionary with format."""
        data = [
            {"path": "field1", "name": "FIELD1", "format": "string"},
            {
                "path": "field2",
                "name": "FIELD2",
                "format": {"type": "number", "attributes": {"precision": 10}},
            },
        ]

        schema = BusinessSchema.from_dict(data)

        assert len(schema.fields) == 2
        assert schema.fields[0].path == "field1"
        assert schema.fields[0].name == "FIELD1"
        assert schema.fields[0].format.type == "string"
        assert schema.fields[0].format.attributes is None

        assert schema.fields[1].path == "field2"
        assert schema.fields[1].name == "FIELD2"
        assert schema.fields[1].format.type == "number"
        assert schema.fields[1].format.attributes == {"precision": 10}

    def test_business_schema_to_dict(self):
        """Test that a BusinessSchema can be converted to a dictionary."""
        schema = BusinessSchema(
            fields=[
                SchemaField(path="field1", name="FIELD1", format=DataFormat(type="string")),
                SchemaField(
                    path="field2",
                    name="FIELD2",
                    format=DataFormat(type="number", attributes={"precision": 10}),
                ),
            ]
        )

        data = schema.to_dict()

        assert len(data) == 2
        assert data[0] == {
            "path": "field1",
            "name": "FIELD1",
            "format": {"type": "string"},
        }
        assert data[1] == {
            "path": "field2",
            "name": "FIELD2",
            "format": {"type": "number", "attributes": {"precision": 10}},
        }

    def test_all_standard_types_supported(self):
        """Test that all standard types are supported."""
        # Create a field with each standard type
        fields = []
        for type_name in [
            StandardTypes.STRING,
            StandardTypes.NUMBER,
            StandardTypes.INTEGER,
            StandardTypes.BOOLEAN,
            StandardTypes.DATE,
            StandardTypes.DATETIME,
        ]:
            fields.append(
                SchemaField(
                    path=f"field.{type_name}",
                    name=f"FIELD_{type_name.upper()}",
                    format=DataFormat(type=type_name),
                )
            )

        # Should not raise any validation errors
        schema = BusinessSchema(fields=fields)
        assert len(schema.fields) == 6
