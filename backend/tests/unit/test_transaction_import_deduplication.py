from app.persistence.repositories.transaction_repository import merchants_likely_match


def test_merchant_matching_tolerates_bank_prefixes_and_store_numbers():
    assert merchants_likely_match("SQ * Coffee Shop 1042", "COFFEE SHOP")
    assert merchants_likely_match("POS PURCHASE STARBUCKS #12891", "Starbucks")
    assert merchants_likely_match("US Dept Education", "Dept Education - Loan")


def test_merchant_matching_does_not_merge_distinct_merchants():
    assert not merchants_likely_match("Whole Foods Market", "Whole Earth Cafe")
    assert not merchants_likely_match("Uber", "Uber Eats")
