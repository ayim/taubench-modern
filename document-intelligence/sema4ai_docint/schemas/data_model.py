from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ClassifiedDocument:
    """
    A document that has been classified into a data model.
    """

    def __init__(self, summary: str, data_model: str):
        self.summary = summary
        self.data_model = data_model

    def __str__(self):
        return f"ClassifiedDocument(document={self.document}, data_model={self.data_model})"


def classify_document(
    unknown_summary: str, known_summaries: list[ClassifiedDocument]
) -> tuple[str, float]:
    """
    Try to classify an unknown document into a known data model.

    Args:
        unknown_summary (str): The summary of the unknown document.
        known_summaries (list[ClassifiedDocument]): List of known summaries.

    Returns:
        The best-matched data model and its similarity score. None if there
    """
    if not known_summaries:
        raise ValueError("No known summaries provided")

    # Vectorize the known summaries
    vectoriser = TfidfVectorizer(token_pattern=r"\S+")
    x_ref = vectoriser.fit_transform([summary.summary for summary in known_summaries])

    # Vectorize the new summary
    vec = vectoriser.transform([unknown_summary])

    # Compute the similarity scores
    sims = cosine_similarity(vec, x_ref)[0]  # array of scores vs refs

    print(sims)

    # Find the best match
    max_val, max_idx = sims.max(), sims.argmax()
    return known_summaries[max_idx].data_model, max_val
