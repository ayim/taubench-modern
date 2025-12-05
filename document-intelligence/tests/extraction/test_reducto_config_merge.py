from sema4ai_docint.extraction.reducto import SyncExtractionClient


class TestReductoConfigMerge:
    """Test cases for Reducto configuration merging logic."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a SyncExtractionClient instance for testing
        self.client = SyncExtractionClient(api_key="test-key")

    def test_extract_opts_no_config(self):
        """Test extract_opts with no extraction_config - should return default config."""
        schema = {
            "type": "object",
            "properties": {
                "totalAmount": {"type": "number"},
                "invoiceNumber": {"type": "string"},
            },
        }
        system_prompt = "Extract invoice data"

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            start_page=1,
            end_page=5,
            extraction_config=None,
        )

        # Verify default structure
        assert result["schema"] == schema
        assert result["system_prompt"] == system_prompt
        assert result["advanced_options"]["page_range"]["start"] == 1
        assert result["advanced_options"]["page_range"]["end"] == 5
        assert result["array_extract"]["enabled"] is False
        assert result["options"]["extraction_mode"] == "ocr"
        assert result["advanced_options"]["ocr_system"] == "highres"

    def test_extract_opts_with_minimal_config(self):
        """Test extract_opts with minimal extraction_config - should merge properly."""
        schema = {"type": "object", "properties": {"totalAmount": {"type": "number"}}}
        system_prompt = "Extract invoice data"

        # Minimal config that only overrides specific settings
        extraction_config = {"advanced_options": {"page_range": {"start": 10, "end": 15}}}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            start_page=1,  # Should be overridden by config
            end_page=5,  # Should be overridden by config
            extraction_config=extraction_config,
        )

        # Verify merged values
        assert result["schema"] == schema
        assert result["system_prompt"] == system_prompt
        assert result["advanced_options"]["page_range"]["start"] == 10  # Overridden
        assert result["advanced_options"]["page_range"]["end"] == 15  # Overridden
        assert result["array_extract"]["enabled"] is False  # Default preserved
        assert result["options"]["extraction_mode"] == "ocr"  # Default preserved

    def test_extract_opts_with_comprehensive_config(self):
        """Test extract_opts with comprehensive extraction_config - should merge all settings."""
        schema = {
            "type": "object",
            "properties": {"lineItems": {"type": "array", "items": {"type": "object"}}},
        }
        system_prompt = "Extract invoice data"

        # Comprehensive config that overrides multiple settings
        extraction_config = {
            "options": {
                "extraction_mode": "ocr",
                "ocr_mode": "fast",
                "table_summary": {"enabled": True},
                "figure_summary": {"enabled": True},
            },
            "advanced_options": {
                "ocr_system": "standard",
                "table_output_format": "ai_json",
                "page_range": {"start": 1, "end": 10},
                "remove_text_formatting": True,
            },
            "experimental_options": {
                "enable_checkboxes": True,
                "enable_equations": True,
                "return_figure_images": True,
            },
            "array_extract": {"enabled": True},
            "timeout": 600,
        }

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            start_page=None,
            end_page=None,
            extraction_config=extraction_config,
        )

        # Verify all overridden values
        assert result["options"]["ocr_mode"] == "fast"
        assert result["options"]["table_summary"]["enabled"] is True
        assert result["options"]["figure_summary"]["enabled"] is True
        assert result["advanced_options"]["ocr_system"] == "standard"
        assert result["advanced_options"]["table_output_format"] == "ai_json"
        assert result["advanced_options"]["page_range"]["start"] == 1
        assert result["advanced_options"]["page_range"]["end"] == 10
        assert result["advanced_options"]["remove_text_formatting"] is True
        assert result["experimental_options"]["enable_checkboxes"] is True
        assert result["experimental_options"]["enable_equations"] is True
        assert result["experimental_options"]["return_figure_images"] is True
        assert result["array_extract"]["enabled"] is True
        assert result["timeout"] == 600

    def test_extract_opts_nested_merge(self):
        """Test that nested objects are merged correctly, not replaced."""
        schema = {"type": "object"}
        system_prompt = "Test"

        # Config that only overrides some nested properties
        extraction_config = {
            "options": {"table_summary": {"enabled": True}},
            "advanced_options": {"page_range": {"start": 5}},
        }

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        # Verify nested merge behavior
        assert result["options"]["table_summary"]["enabled"] is True  # Overridden
        assert result["options"]["figure_summary"]["enabled"] is False  # Default preserved
        assert result["options"]["extraction_mode"] == "ocr"  # Default preserved
        assert result["advanced_options"]["page_range"]["start"] == 5  # Overridden
        assert result["advanced_options"]["page_range"]["end"] is None  # Default preserved
        assert result["advanced_options"]["ocr_system"] == "highres"  # Default preserved

    def test_extract_opts_array_extract_override(self):
        """Test that array_extract can be overridden by extraction_config."""
        schema = {
            "type": "object",
            "properties": {"lineItems": {"type": "array", "items": {"type": "object"}}},
        }
        system_prompt = "Test"

        # Test enabling array_extract via config
        extraction_config = {"array_extract": {"enabled": True}}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        assert result["array_extract"]["enabled"] is True

    def test_extract_opts_array_extract_schema_validation(self):
        """Test that array_extract can be enabled regardless of schema structure."""
        schema = {
            "type": "object",
            "properties": {
                "totalAmount": {"type": "number"}  # No top-level array
            },
        }
        system_prompt = "Test"

        # Try to enable array_extract via config
        extraction_config = {"array_extract": {"enabled": True}}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        # Should be True because extraction_config enables it, regardless of schema
        assert result["array_extract"]["enabled"] is True

    def test_extract_opts_array_extract_schema_validation_with_array(self):
        """Test that array_extract can be enabled when schema has top-level array."""
        schema = {
            "type": "object",
            "properties": {"lineItems": {"type": "array", "items": {"type": "object"}}},
        }
        system_prompt = "Test"

        # Enable array_extract via config
        extraction_config = {"array_extract": {"enabled": True}}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        # Should be True because extraction_config enables it
        assert result["array_extract"]["enabled"] is True

    def test_extract_opts_system_prompt_override(self):
        """Test that system_prompt can be overridden by extraction_config."""
        schema = {"type": "object"}
        system_prompt = "Original prompt"

        extraction_config = {"system_prompt": "Overridden prompt"}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        assert result["system_prompt"] == "Overridden prompt"

    def test_extract_opts_schema_override(self):
        """Test that schema can be overridden by extraction_config."""
        original_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        system_prompt = "Test"

        new_schema = {"type": "object", "properties": {"b": {"type": "number"}}}
        extraction_config = {"schema": new_schema}

        result = self.client.extract_opts(
            schema=original_schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        assert result["schema"] == new_schema

    def test_extract_opts_generate_citations_false(self):
        """Test that generate_citations can be set to False via extraction_config."""
        schema = {"type": "object"}
        system_prompt = "Test"

        extraction_config = {"generate_citations": False}

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        assert result["generate_citations"] is False

    def test_merge_extraction_config_method(self):
        """Test the merge_extraction_config class method directly."""
        default_config = {
            "options": {
                "extraction_mode": "ocr",
                "ocr_mode": "standard",
                "table_summary": {"enabled": False},
            },
            "advanced_options": {
                "ocr_system": "highres",
                "page_range": {"start": None, "end": None},
            },
            "timeout": 300,
        }

        override_config = {
            "options": {"ocr_mode": "fast", "table_summary": {"enabled": True}},
            "advanced_options": {"page_range": {"start": 1, "end": 10}},
            "new_field": "new_value",
        }

        result = SyncExtractionClient.merge_config(default_config, override_config)

        # Verify merged result
        assert result["options"]["extraction_mode"] == "ocr"  # Default preserved
        assert result["options"]["ocr_mode"] == "fast"  # Overridden
        assert result["options"]["table_summary"]["enabled"] is True  # Overridden
        assert result["advanced_options"]["ocr_system"] == "highres"  # Default preserved
        assert result["advanced_options"]["page_range"]["start"] == 1  # Overridden
        assert result["advanced_options"]["page_range"]["end"] == 10  # Overridden
        assert result["timeout"] == 300  # Default preserved
        assert result["new_field"] == "new_value"  # New field added

    def test_merge_extraction_config_none_config(self):
        """Test merge_extraction_config with None config - should return default."""
        default_config = {"options": {"extraction_mode": "ocr"}, "timeout": 300}

        result = SyncExtractionClient.merge_config(default_config, None)

        assert result == default_config

    def test_merge_extraction_config_empty_config(self):
        """Test merge_extraction_config with empty config - should return default."""
        default_config = {"options": {"extraction_mode": "ocr"}, "timeout": 300}

        result = SyncExtractionClient.merge_config(default_config, {})

        assert result == default_config

    def test_merge_extraction_config_deep_nesting(self):
        """Test merge_extraction_config with deeply nested structures."""
        default_config = {
            "level1": {"level2": {"level3": {"value1": "default1", "value2": "default2"}}}
        }

        override_config = {
            "level1": {"level2": {"level3": {"value2": "override2", "value3": "new3"}}}
        }

        result = SyncExtractionClient.merge_config(default_config, override_config)

        assert result["level1"]["level2"]["level3"]["value1"] == "default1"  # Preserved
        assert result["level1"]["level2"]["level3"]["value2"] == "override2"  # Overridden
        assert result["level1"]["level2"]["level3"]["value3"] == "new3"  # Added

    def test_extract_opts_edge_cases(self):
        """Test extract_opts with edge cases and unusual inputs."""
        schema = {"type": "object"}
        system_prompt = "Test"

        # Test with empty strings, None values, etc.
        extraction_config = {
            "options": {"extraction_mode": "", "ocr_mode": None},
            "advanced_options": {"page_range": {"start": 0, "end": -1}},
        }

        result = self.client.extract_opts(
            schema=schema,
            system_prompt=system_prompt,
            extraction_config=extraction_config,
        )

        # Should handle edge cases gracefully
        assert result["options"]["extraction_mode"] == ""
        assert result["options"]["ocr_mode"] is None
        assert result["advanced_options"]["page_range"]["start"] == 0
        assert result["advanced_options"]["page_range"]["end"] == -1

    def test_merge_split_config(self):
        """Test that split_opts merges correctly."""
        overrides = {"experimental_options": {"enable_checkboxes": True}}

        default_opts = self.client.split_opts()
        assert default_opts["experimental_options"]["enable_checkboxes"] is False

        result = self.client.split_opts(config=overrides)
        assert result["experimental_options"]["enable_checkboxes"] is True

    def test_merge_parse_config(self):
        """Test that parse_opts merges correctly."""
        overrides = {
            "experimental_options": {"enable_checkboxes": True},
            "schema": "{}",
            "system_prompt": "Be precise and thorough.",
            "generate_citations": False,
            "array_extract": {
                "enabled": False,
                "mode": "legacy",
                "pages_per_segment": 10,
                "streaming_extract_item_density": 50,
            },
            "use_chunking": False,
            "include_images": False,
            "spreadsheet_agent": False,
        }

        default_opts = self.client.parse_opts()
        assert default_opts["experimental_options"]["enable_checkboxes"] is False

        result = self.client.parse_opts(config=overrides)
        assert result["experimental_options"]["enable_checkboxes"] is True

        # Make sure that options that are only valid for extract, not parse, are not included
        assert "use_chunking" not in result
        assert "array_extract" not in result
        assert "include_images" not in result
        assert "spreadsheet_agent" not in result
        assert "schema" not in result
        assert "system_prompt" not in result
        assert "generate_citations" not in result

    def test_extract_opts_agent_extract(self):
        """Test extract_opts with no extraction_config - should return default config."""
        schema = {
            "type": "object",
            "properties": {
                "totalAmount": {"type": "number"},
                "invoiceNumber": {"type": "string"},
            },
        }
        system_prompt = "Extract invoice data"
        config = {
            "schema": schema,
            "agent_extract": {
                "enabled": True,
            },
            "generate_citations": True,
        }

        result = self.client.extract_opts(schema, system_prompt, extraction_config=config)
        assert result["agent_extract"]["enabled"] is True
        assert result["generate_citations"] is False

        # agent_extract=False should respect citations original value
        config = {
            "agent_extract": {
                "enabled": False,
            },
            "generate_citations": True,
        }
        result = self.client.extract_opts(schema, system_prompt, extraction_config=config)
        assert result["agent_extract"]["enabled"] is False
        assert result["generate_citations"] is True

        # agent_extract omitted should respect citation original value
        config = {
            "generate_citations": True,
        }

        result = self.client.extract_opts(schema, system_prompt, extraction_config=config)
        assert "agent_extract" not in result
        assert result["generate_citations"] is True
