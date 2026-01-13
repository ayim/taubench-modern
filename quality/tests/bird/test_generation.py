import yaml

from agent_platform.quality.bird.generation import unset_schema_from_model


def test_unset_schema_from_model():
    """Test that base_table.schema is set to None for all tables in the semantic model."""
    sdm_yaml = """
name: Community Q&A Analytics
tables:
  - name: badges
    synonyms:
      - user achievement badges
      - earned badge awards
      - badge grants log
    base_table:
      table: badges
      schema: public
      database: null
      data_connection_name: postgres-spar
    dimensions:
      - expr: id
        name: id
        synonyms:
          - badge award id
        data_type: '!int64'
        description: Unique identifier of the badge award record.
        sample_values:
          - 1
          - 2
          - 3
          - 4
          - 5
    """

    semantic_model = yaml.safe_load(sdm_yaml)

    result = unset_schema_from_model(semantic_model)

    # Verify all base_table.schema values are None
    for table in result.get("tables", []):
        base_table = table.get("base_table", {})
        assert base_table.get("schema") is None, f"Expected schema to be None for table {table.get('name')}"
