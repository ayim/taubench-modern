from sema4ai_docint.schemas import ClassifiedDocument, classify_document


def test_similarity():
    known_summaries = [
        ClassifiedDocument(
            summary=(
                "This document provides local broadcast traffic instructions for "
                "FanDuel advertising spots in Baltimore, listing flight dates, ad "
                "identifiers, creative titles, spot lengths, rotation percentages, "
                "and specific instructions for both regular programming and NFL live "
                "sports broadcasts."
            ),
            data_model="ad_schedules_pdf",
        ),
        ClassifiedDocument(
            summary=(
                "TV broadcast instructions for AstraZeneca's ULTO product, outlining "
                'two 60-second ads ("She IS" and "He IS" CCN Revision Linear + '
                "Addressable), scheduled for air on WNUV, Baltimore, MD from March 17 "
                "to March 23, 2025, with 50% rotation each."
            ),
            data_model="ad_schedules_pdf",
        ),
        ClassifiedDocument(
            summary=(
                'This document is a "Commercial Copy Report" detailing various '
                "parameters for commercial advertisement tracking across multiple "
                "Baltimore TV stations, including agency, advertiser, salesperson, "
                "account types, break types, contract and estimate numbers, and date "
                "range settings. It categorizes commercial copy usage by station, "
                "account type, and detailed account sub-types for reporting and "
                "classification."
            ),
            data_model="ad_schedules_pdf",
        ),
        ClassifiedDocument(
            summary=(
                "This document is a set of weekly television traffic instructions for "
                "WBFF, detailing commercial spots scheduled to air during the week of "
                "March 17, 2025. It lists clients, products, contracts, spot lengths, "
                "rotation percentages, tape IDs, and airing schedules, with notes on "
                "scheduling and contact information for inquiries."
            ),
            data_model="ad_schedules_pdf",
        ),
        ClassifiedDocument(
            summary=(
                "This document contains TV advertising instructions from Comcast for "
                "station WBFF Baltimore, detailing commercial schedules, run dates "
                "(March 12-16, 2025), ad types (subscriber vs. non-subscriber), ad IDs, "
                "titles, rotation percentages, client/product info, and estimate numbers, "
                "for both subscriber and non-subscriber programming."
            ),
            data_model="ad_schedules_pdf",
        ),
    ]

    unknown_summary = (
        "Broadcast traffic instructions for FanDuel (FDUL) advertising campaign (1G25) "
        "in Baltimore market stations (EBBF, EBAL, WBAL, WBFF, WMAR, WNUV) for the "
        "period 1/27/2025-2/2/2025, detailing spot rotation, flight, ad IDs, creative "
        "titles, lengths, and special instructions for regular and live sports "
        "programming."
    )
    best_match, similarity = classify_document(unknown_summary, known_summaries)
    assert best_match == "ad_schedules_pdf"
    assert similarity > 0.5
