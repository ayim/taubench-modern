from pathlib import Path

from PIL import Image

_QUALITY = 85


def truncate_images(images: list[Image.Image], limit: int = 50 * 1024 * 1024) -> list[Image.Image]:
    # Haven't figured out why, but our limit calculation seems to be off by 15% to what openai says
    limit = int(limit * 0.85)

    rolling_sum = 0
    for i, img in enumerate(images):
        rolling_sum += get_image_size_bytes(img)
        if rolling_sum > limit:
            # If we exceed the limit, return the current list, minus the current element
            return images[:i]

    return images


def get_image_size_bytes(image: Image.Image) -> int:
    """
    Approximate the size of an image, encoded as JPEG
    """
    from io import BytesIO

    buffer = BytesIO()

    # TODO a little wasteful in that `to_jpeg` is also computing this.
    image.save(buffer, format="JPEG", quality=_QUALITY)
    return len(buffer.getvalue())


def to_jpeg(img: Image.Image) -> str:
    from base64 import b64encode
    from io import BytesIO

    buffer = BytesIO()

    img.save(buffer, format="JPEG", quality=_QUALITY)
    return b64encode(buffer.getvalue()).decode("utf-8")


def convert_pdf_bytes_to_images(
    pdf_bytes: bytes, dpi: int = 185, start_page: int | None = None, end_page: int | None = None
) -> list[Image.Image]:
    """
    Rasterize PDF bytes into a list of PIL Images using PyMuPDF.

    Args:
        pdf_bytes: Raw bytes of the PDF document
        dpi: Target rendering DPI (72dpi base). Defaults to 200 to approximate previous quality
        start_page: Optional starting page number (1-indexed) for page range extraction
        end_page: Optional ending page number (1-indexed) for page range extraction

    Returns:
        List of PIL Image instances, one per rendered page
    """
    import fitz  # type: ignore  # PyMuPDF

    scale = float(dpi) / 72.0
    images: list[Image.Image] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page_count = len(doc)

        # Determine page range
        start_idx = (start_page - 1) if start_page is not None else 0
        end_idx = end_page if end_page is not None else page_count

        # Ensure we don't exceed document bounds
        start_idx = max(0, min(start_idx, page_count - 1))
        end_idx = min(end_idx, page_count)

        for page_index in range(start_idx, end_idx):
            page = doc.load_page(page_index)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)

    return images


def convert_pdf_path_to_images(
    pdf_path: Path, dpi: int = 185, start_page: int | None = None, end_page: int | None = None
) -> list[Image.Image]:
    """
    Convenience wrapper to rasterize a PDF from a filesystem path.
    """
    pdf_bytes = pdf_path.read_bytes()
    return convert_pdf_bytes_to_images(pdf_bytes, dpi=dpi, start_page=start_page, end_page=end_page)
