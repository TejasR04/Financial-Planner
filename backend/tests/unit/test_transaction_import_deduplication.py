from app.persistence.repositories.transaction_repository import IMPORT_DATE_TOLERANCE_DAYS, merchants_likely_match


def test_merchant_matching_tolerates_bank_prefixes_and_store_numbers():
    assert merchants_likely_match("SQ * Coffee Shop 1042", "COFFEE SHOP")
    assert merchants_likely_match("POS PURCHASE STARBUCKS #12891", "Starbucks")
    assert merchants_likely_match("US Dept Education", "Dept Education - Loan")
    assert merchants_likely_match(
        "Verizon",
        "VERIZON          PAYMENTREC                 PPD ID: 9783397101",
    )


def test_merchant_matching_does_not_merge_distinct_merchants():
    assert not merchants_likely_match("Whole Foods Market", "Whole Earth Cafe")
    assert not merchants_likely_match("Uber", "Uber Eats")


def test_import_date_tolerance_is_limited_to_three_days():
    assert IMPORT_DATE_TOLERANCE_DAYS == 3
