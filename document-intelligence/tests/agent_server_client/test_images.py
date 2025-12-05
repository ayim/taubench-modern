from pathlib import Path

from sema4ai_docint.agent_server_client.images import (
    convert_pdf_path_to_images,
    truncate_images,
)


def test_truncation():
    input_pdf = Path(__file__).parent / "test-data" / "image_truncation.pdf"
    assert input_pdf.exists()

    images = convert_pdf_path_to_images(input_pdf)
    assert len(images) == 3, "did not generate any images"

    # Page sizes on this documentj
    # i = 0, size=290532
    # i = 1, size=357353
    # i = 2, size=319500

    assert len(truncate_images(images, limit=775_000)) == 2
    assert len(truncate_images(images, limit=375_000)) == 1
    assert len(truncate_images(images, limit=1)) == 0
    assert len(truncate_images(images)) == 3
