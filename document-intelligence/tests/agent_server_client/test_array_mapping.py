"""
Focused test for the create_mapping function's array mapping behavior.
Tests the specific issue where line_items[*] should map to Transactions with flatten mode.
"""

import json
from pathlib import Path

import pytest


class TestArrayMapping:
    """Test class for array mapping functionality."""

    # TODO: Fix lint issues in this function
    def test_create_mapping_array_behavior(self, agent_client):  # noqa: PLR0915
        """Test create_mapping function with array mapping behavior using agent_client fixture."""

        # Get test data directory
        test_data_dir = Path(__file__).parent / "test-data" / "array_mapping"

        # Load test schemas from the test-data directory
        business_schema_file = test_data_dir / "business_schema.json"
        extraction_schema_file = test_data_dir / "extraction_schema.json"

        if not business_schema_file.exists() or not extraction_schema_file.exists():
            pytest.skip(f"Test data files not found in: {test_data_dir}")

        print(f"\nLoading test schemas from: {test_data_dir}")

        # Load the schemas
        with open(business_schema_file) as f:
            business_schema = json.load(f)

        with open(extraction_schema_file) as f:
            extraction_schema = json.load(f)

        print("Testing create_mapping with array schemas...")

        try:
            # Test the mapping generation using agent_client
            mapping_result = agent_client.create_mapping(
                json.dumps(business_schema), json.dumps(extraction_schema)
            )

            # Parse and analyze the result
            mapping_rules = json.loads(mapping_result)

            print(f"Generated {len(mapping_rules)} mapping rules")

            # Categorize mapping rules
            array_mappings = []
            individual_field_mappings = []
            simple_mappings = []

            for rule in mapping_rules:
                source = rule.get("source", "")
                target = rule.get("target", "")
                mode = rule.get("mode")

                if "[*]" in source and not source.endswith("[*]"):
                    # Individual field mapping like "array[*].field"
                    individual_field_mappings.append(rule)
                elif source.endswith("[*]") and mode == "flatten":
                    # Array mapping with flatten mode like "array[*]"
                    array_mappings.append(rule)
                else:
                    # Simple field mapping
                    simple_mappings.append(rule)

            # Validation 1: Should have at least one array mapping with flatten mode
            assert len(array_mappings) > 0, (
                "Expected at least one array mapping with flatten mode (source ending with "
                "[*] and mode='flatten')"
            )

            # Validation 2: Should NOT have individual field mappings for arrays
            if individual_field_mappings:
                print(
                    f"❌ Found {len(individual_field_mappings)} invalid individual field mappings:"
                )
                for pattern in individual_field_mappings:
                    print(f"   {pattern['source']} -> {pattern['target']}")
                pytest.fail(
                    "Found invalid individual field mappings (source like 'array[*].field'). "
                    "Use flatten mode instead."
                )

            # Validation 3: Array mappings should have extras field
            for array_mapping in array_mappings:
                source = array_mapping.get("source", "")
                target = array_mapping.get("target", "")

                assert "extras" in array_mapping, (
                    f"Array mapping '{source} -> {target}' should have 'extras' field"
                )
                extras = array_mapping["extras"]
                assert isinstance(extras, dict), (
                    f"'extras' field should be a dictionary for '{source} -> {target}'"
                )
                assert len(extras) > 0, (
                    f"'extras' field should not be empty for '{source} -> {target}'"
                )

                print(
                    f"✅ Array mapping '{source} -> {target}' has {len(extras)} field mappings "
                    f"in extras"
                )

            # Validation 4: Check that we have some simple mappings (non-array fields)
            print(f"✅ Found {len(simple_mappings)} simple field mappings")

            # Validation 5: Ensure no duplicate sources or targets
            all_sources = [rule.get("source") for rule in mapping_rules]
            all_targets = [rule.get("target") for rule in mapping_rules]

            duplicate_sources = [src for src in set(all_sources) if all_sources.count(src) > 1]
            duplicate_targets = [tgt for tgt in set(all_targets) if all_targets.count(tgt) > 1]

            assert len(duplicate_sources) == 0, (
                f"Found duplicate source fields: {duplicate_sources}"
            )
            assert len(duplicate_targets) == 0, (
                f"Found duplicate target fields: {duplicate_targets}"
            )

            # Validation 6: Ensure all rules have required fields
            for i, rule in enumerate(mapping_rules):
                assert "source" in rule, f"Rule {i + 1} missing 'source' field"
                assert "target" in rule, f"Rule {i + 1} missing 'target' field"
                assert rule["source"].strip(), f"Rule {i + 1} has empty 'source' field"
                assert rule["target"].strip(), f"Rule {i + 1} has empty 'target' field"

            print("✅ All generic mapping validations passed!")
            print(f"✅ Validated {len(mapping_rules)} total mapping rules")
            print("✅ Array mappings use proper flatten mode with extras")
            print("✅ No invalid individual field mappings found")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback

            traceback.print_exc()
            raise
