"""Stable merchant patterns for user-created transaction rules."""
from __future__ import annotations

import re


_REFERENCE_LABEL = re.compile(
    r"\b(?:transaction|confirmation|reference|trace|check)\s*(?:number|num|no)?\s*#?\s*:?\s*[a-z0-9-]+.*$",
    re.IGNORECASE,
)
_MASKED_ACCOUNT = re.compile(r"(?:\.{2,}|\*{2,}|x{2,})\s*\d{2,}\b", re.IGNORECASE)
_DATE_TOKEN = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_DYNAMIC_TOKEN = re.compile(r"\b(?=[a-z0-9-]{8,}\b)(?=[a-z0-9-]*\d)[a-z0-9-]+\b", re.IGNORECASE)


def normalize_merchant_rule(value: str, *, collapse_transfers: bool = True) -> str:
    normalized = " ".join(value.lower().replace("_", " ").split())
    # Account suffixes and transaction numbers change on every bank transfer;
    # direction/account labels should not create separate rules either.
    if collapse_transfers and normalized.startswith("online transfer"):
        return "online transfer"
    normalized = _REFERENCE_LABEL.sub("", normalized)
    normalized = _MASKED_ACCOUNT.sub("", normalized)
    normalized = _DATE_TOKEN.sub("", normalized)
    normalized = _DYNAMIC_TOKEN.sub("", normalized)
    normalized = re.sub(r"\b(?:ppd|web)\s+id\s*:?", "", normalized)
    normalized = re.sub(r"[^a-z0-9'&.-]+", " ", normalized)
    return " ".join(normalized.strip(" .-").split())


def merchant_matches_rule(merchant: str, rule_pattern: str, *, collapse_transfers: bool = True) -> bool:
    merchant_words = set(re.findall(r"[a-z0-9]+", merchant.lower().replace("_", " ")))
    rule_words = re.findall(r"[a-z0-9]+", normalize_merchant_rule(rule_pattern, collapse_transfers=collapse_transfers))
    return bool(rule_words) and all(word in merchant_words for word in rule_words)
