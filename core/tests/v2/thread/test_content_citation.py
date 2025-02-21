from agent_server_types_v2.thread.content.text import Citation


class TestCitation:
    def test_citation_minimum(self):
        c = Citation(
            document_uri="http://example.com",
            start_char_index=0,
            end_char_index=10,
        )
        assert c.document_uri == "http://example.com"
        assert c.cited_text is None

    def test_citation_with_cited_text(self):
        c = Citation(
            document_uri="file://mydoc.txt",
            start_char_index=5,
            end_char_index=20,
            cited_text="Some snippet",
        )
        assert c.cited_text == "Some snippet"

    def test_citation_to_json_dict(self):
        c = Citation(
            document_uri="doc://xyz",
            start_char_index=2,
            end_char_index=4,
            cited_text="abc",
        )
        jd = c.model_dump()
        assert jd["document_uri"] == "doc://xyz"
        assert jd["start_char_index"] == 2
        assert jd["end_char_index"] == 4
        assert jd["cited_text"] == "abc"
