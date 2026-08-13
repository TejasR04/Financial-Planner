from app.domain.merchant_rules import merchant_matches_rule, normalize_merchant_rule


def test_online_transfer_rules_drop_account_and_transaction_identifiers():
    assert normalize_merchant_rule(
        "Online Transfer from SAV ...5175 transaction#: 28224240080"
    ) == "online transfer"
    assert merchant_matches_rule(
        "Online Transfer to CHK ...1351 transaction#: 99999999999 08/10",
        "Online Transfer from SAV ...5175 transaction#: 28224240080",
    )


def test_dynamic_reference_ids_are_removed_without_dropping_counterparty():
    assert normalize_merchant_rule(
        "ZELLE PAYMENT FROM JULIA YOON 30349766605"
    ) == "zelle payment from julia yoon"
    assert merchant_matches_rule(
        "ZELLE PAYMENT FROM JULIA YOON 99999999999",
        "ZELLE PAYMENT FROM JULIA YOON 30349766605",
    )


def test_rule_words_can_match_across_removed_bank_metadata():
    assert merchant_matches_rule(
        "VERIZON PAYMENTREC 5580590290001 WEB ID: 9783397101",
        "verizon web id: 9783397101",
    )
