from pydantic import BaseModel, Field, field_validator


class Column(BaseModel):
    """A column in a database view.

    Attributes:
        name: The name of the column
        type: The data type of the column
    """

    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)

    @field_validator("name", "type")
    @classmethod
    def validate_string_fields(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class View(BaseModel):
    """A database view with its metadata.

    Attributes:
        name: The name of the view
        sql: The SQL query that defines the view
        columns: List of column definitions in the view
    """

    name: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)
    columns: list[Column] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that the view name is not empty and properly formatted."""
        if not v.strip():
            raise ValueError("View name cannot be empty")
        return v.strip()

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        """Validate that the SQL query is not empty."""
        if not v.strip():
            raise ValueError("SQL query cannot be empty")
        return v.strip()

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: list[Column]) -> list[Column]:
        """Validate that the columns list is not empty and contains valid column definitions."""
        if not v:
            raise ValueError("Columns list cannot be empty")
        return v

    def get_column_names(self) -> list[str]:
        """Get a list of column names from the view."""
        return [col.name for col in self.columns]
