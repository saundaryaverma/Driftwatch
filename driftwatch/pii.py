"""Find personal data in text. Used by the no_pii check to catch replies that leak it."""
import re

PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "us_phone": re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
}


def luhn_valid(number):
    """Card numbers end in a checksum digit; this filters out random digit runs."""
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mask(value):
    return value[:2] + "*" * max(len(value) - 4, 1) + value[-2:]


def find_pii(text, kinds=None):
    """Return a list of (kind, masked_value) found in text."""
    found = []
    for kind, pattern in PATTERNS.items():
        if kinds and kind not in kinds:
            continue
        for match in pattern.finditer(text):
            value = match.group(0)
            if kind == "credit_card" and not luhn_valid(value):
                continue
            if kind == "us_phone" and any(k == "credit_card" and value in v for k, v in found):
                continue
            found.append((kind, mask(value.strip())))
    return found
