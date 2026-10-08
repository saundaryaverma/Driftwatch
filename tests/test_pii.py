import pytest

from driftwatch.pii import find_pii, luhn_valid


@pytest.mark.parametrize("text,kind", [
    ("write to jordan.lee@example.com", "email"),
    ("call (415) 555-0134 today", "us_phone"),
    ("ssn 123-45-6789", "ssn"),
    ("card 4111 1111 1111 1111", "credit_card"),
    ("card 4111-1111-1111-1111", "credit_card"),
])
def test_finds_each_kind(text, kind):
    assert kind in [k for k, _ in find_pii(text)]


def test_clean_text_has_no_pii():
    assert find_pii("Standard shipping takes 3-5 business days. Order 4471 shipped.") == []


def test_random_digits_that_fail_luhn_are_not_cards():
    assert not luhn_valid("1234 5678 9012 3456")
    assert "credit_card" not in [k for k, _ in find_pii("ref 1234 5678 9012 3456")]


def test_found_values_are_masked():
    (_, masked), = find_pii("jordan.lee@example.com")
    assert "jordan.lee@example.com" not in masked and masked.startswith("jo")


def test_can_limit_to_some_kinds():
    text = "jordan@example.com, 123-45-6789"
    assert [k for k, _ in find_pii(text, ["ssn"])] == ["ssn"]
