from sema4ai_docint.extraction.transform.transform import transform_content
from sema4ai_docint.extraction.transform.transform_document_layout import TransformDocumentLayout


class TestTransformDocumentLayout:
    def test_tokens(self):
        # Test path tokenization
        path = "pages[*].blocks[*].text"
        tokens = TransformDocumentLayout.tokens(path)
        assert tokens == ["pages[*]", "blocks[*]", "text"]

    def test_collect(self):
        # Test collecting values from nested structure
        doc = {
            "pages": [
                {"blocks": [{"text": "Hello"}, {"text": "World"}]},
                {"blocks": [{"text": "Test"}]},
            ]
        }

        # Test collecting all text values
        texts = TransformDocumentLayout.collect(doc, ["pages[*]", "blocks[*]", "text"])
        assert texts == ["Hello", "World", "Test"]

        # Test collecting single value
        page = TransformDocumentLayout.collect(doc, ["pages[*]"])
        assert len(page) == 2

    def test_set_path(self):
        # Test setting nested path
        root = {}
        TransformDocumentLayout.set_path(root, "metadata.title", "Test Document")
        assert root["metadata"]["title"] == "Test Document"

    def test_cast(self):
        # Test various type casting scenarios
        assert TransformDocumentLayout.cast("123", "int") == 123
        assert TransformDocumentLayout.cast("1,234.56", "float") == 1234.56
        assert TransformDocumentLayout.cast("$ 1,234.56", "float") == 1234.56
        assert TransformDocumentLayout.cast("yes", "bool")
        assert not TransformDocumentLayout.cast("no", "bool")
        assert TransformDocumentLayout.cast(123, "str") == "123"

    def test_flatten(self):
        # Test flattening nested document structure
        doc = {
            "metadata": {"title": "Test Doc"},
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        {"text": "Hello", "confidence": 0.9},
                        {"text": "World", "confidence": 0.8},
                    ],
                }
            ],
        }

        # Test flattening with relative paths
        extras = {"page_num": "../number", "doc_title": "../../metadata.title"}

        flattened = TransformDocumentLayout.flatten(
            doc, TransformDocumentLayout.tokens("pages[*].blocks[*]"), extras
        )

        # Verify the structure of flattened results
        assert len(flattened) == 2

        # Check first block
        assert flattened[0]["text"] == "Hello"
        assert flattened[0]["confidence"] == 0.9
        assert flattened[0]["page_num"] == 1
        assert flattened[0]["doc_title"] == "Test Doc"

        # Check second block
        assert flattened[1]["text"] == "World"
        assert flattened[1]["confidence"] == 0.8
        assert flattened[1]["page_num"] == 1
        assert flattened[1]["doc_title"] == "Test Doc"

    def test_nested_path_handling(self):
        extracted_content = {
            "outfalls": [
                {
                    "tables": [
                        {
                            "pollutants": [
                                {
                                    "name": "BOD (5-day)",
                                    "sampleValues": {
                                        "sample1": "8.49",
                                        "sample2": "3.56",
                                        "sample3": None,
                                        "sample4": None,
                                    },
                                },
                                {
                                    "name": "CBOD (5-day)",
                                    "sampleValues": {
                                        "sample1": "2.08",
                                        "sample2": "<2.00",
                                        "sample3": None,
                                        "sample4": None,
                                    },
                                },
                            ]
                        }
                    ],
                    "sampleType": "Composite",
                    "outfallNumber": "001",
                },
                {
                    "tables": [
                        {
                            "pollutants": [
                                {
                                    "name": "Total dissolved solids",
                                    "sampleValues": {
                                        "sample1": "950",
                                        "sample2": "800",
                                        "sample3": None,
                                        "sample4": None,
                                    },
                                },
                                {
                                    "mal": "2.5",
                                    "name": "Aluminum, total",
                                    "sampleValues": {
                                        "sample1": "70.2",
                                        "sample2": "61.5",
                                        "sample3": None,
                                        "sample4": None,
                                    },
                                },
                            ]
                        }
                    ],
                    "sampleType": "Grab",
                    "outfallNumber": "001",
                },
            ],
            "dateRange": "5/29/2024-6/6/2024",
            "testingAttachments": [
                {
                    "name": "K SPL Laboratories",
                    "contactInformation": "null",
                    "pollutantsAnalyzed": "null",
                }
            ],
            "samplesWithin12Months": True,
        }

        # Create the translation schema that caused the original error
        translation_schema = {
            "rules": [
                {
                    "source": "dateRange",
                    "target": "dateRange",
                    "mode": None,
                    "transform": None,
                    "extras": {},
                },
                {
                    "source": "samplesWithin12Months",
                    "target": "samplesWithin12Months",
                    "mode": None,
                    "transform": None,
                    "extras": {},
                },
                {
                    "source": "testingAttachments[*]",
                    "target": "testingAttachments",
                    "mode": "flatten",
                    "transform": None,
                    "extras": {
                        "name": "name",
                        "contactInformation": "contactInformation",
                        "pollutantsAnalyzed": "pollutantsAnalyzed",
                    },
                },
                {
                    "source": "outfalls[*]",
                    "target": "outfalls",
                    "mode": "flatten",
                    "transform": None,
                    "extras": {
                        "outfallNumber": "outfallNumber",
                        "sampleType": "sampleType",
                        "tables": "tables",
                    },
                },
                # This rule caused the original TypeError
                {
                    "source": "outfalls[*].tables[*]",
                    "target": "outfalls.tables",
                    "mode": "flatten",
                    "transform": None,
                    "extras": {"pollutants": "pollutants"},
                },
                {
                    "source": "outfalls[*].tables[*].pollutants[*]",
                    "target": "outfalls.tables.pollutants",
                    "mode": "flatten",
                    "transform": None,
                    "extras": {"name": "name", "sampleValues": "sampleValues", "mal": "mal"},
                },
            ]
        }

        transform_client = TransformDocumentLayout()
        result = transform_content(transform_client, extracted_content, translation_schema)

        assert result is not None
        assert "dateRange" in result
        assert "samplesWithin12Months" in result
        assert "testingAttachments" in result
        assert "outfalls" in result

        # Verify the nested structure was properly created
        assert result["dateRange"] == "5/29/2024-6/6/2024"
        assert result["samplesWithin12Months"] is True

        # Verify flattened arrays
        assert isinstance(result["testingAttachments"], list)
        assert len(result["testingAttachments"]) == 1
        assert result["testingAttachments"][0]["name"] == "K SPL Laboratories"

        assert isinstance(result["outfalls"], list)
        assert len(result["outfalls"]) == 2

    def test_set_path_deeply_nested_with_lists(self):
        """
        Test set_path with deeply nested structures containing multiple list levels.
        """
        root = {"level1": [{"level2": [{"id": "a"}, {"id": "b"}]}, {"level2": [{"id": "c"}]}]}

        # Set a deeply nested path that crosses multiple list boundaries
        TransformDocumentLayout.set_path(root, "level1.level2.newField", "test_value")

        # Verify the value was set in all nested list items
        assert root["level1"][0]["level2"][0]["newField"] == "test_value"
        assert root["level1"][0]["level2"][1]["newField"] == "test_value"
        assert root["level1"][1]["level2"][0]["newField"] == "test_value"
