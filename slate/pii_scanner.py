"""
PII Scanner for SLATE Project Boards

Prevents personal identifiable information from being exposed in public project boards.
Scans issue/PR titles, descriptions, and comments before adding to projects.
"""

import re
import sys
from typing import NamedTuple

# PII detection patterns
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"),
    "phone_intl": re.compile(r"\b\+[0-9]{1,3}[-.\s]?[0-9]{6,14}\b"),
    "ssn": re.compile(r"\b[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4}\b"),
    "credit_card": re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
    "ip_address": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api|key|token|secret|password|bearer)[-_]?[A-Za-z0-9]{16,}\b", re.IGNORECASE),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"),
    "home_address": re.compile(r"\b\d{1,5}\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|way|place|pl)\b", re.IGNORECASE),
    "date_of_birth": re.compile(r"\b(?:dob|birth\s*date|date\s*of\s*birth)[:\s]+[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}\b", re.IGNORECASE),
}

# Allowlist patterns (things that look like PII but aren't)
ALLOWLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b127\.0\.0\.1\b"),  # localhost
    re.compile(r"\b0\.0\.0\.0\b"),  # any interface
    re.compile(r"\b192\.168\.\d+\.\d+\b"),  # private IP
    re.compile(r"\b10\.\d+\.\d+\.\d+\b"),  # private IP
    re.compile(r"\b172\.(?:1[6-9]|2[0-9]|3[01])\.\d+\.\d+\b"),  # private IP
    re.compile(r"\bexample\.com\b"),  # example domain
    re.compile(r"\btest@test\.com\b"),  # test email
    re.compile(r"\buser@example\.com\b"),  # example email
    re.compile(r"\bnoreply@anthropic\.com\b"),  # Claude co-author
    re.compile(r"\bnoreply@github\.com\b"),  # GitHub noreply
]


class PIIMatch(NamedTuple):
    """Represents a PII match found in text."""
    pii_type: str
    value: str
    start: int
    end: int


def is_allowlisted(text: str, match: re.Match) -> bool:
    """Check if a match is in the allowlist."""
    matched_text = match.group()
    for pattern in ALLOWLIST_PATTERNS:
        if pattern.search(matched_text):
            return True
    return False


def scan_text(text: str) -> list[PIIMatch]:
    """
    Scan text for PII patterns.

    Args:
        text: The text to scan

    Returns:
        List of PII matches found
    """
    if not text:
        return []

    matches: list[PIIMatch] = []

    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            if not is_allowlisted(text, match):
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end()
                ))

    return matches


def redact_text(text: str) -> tuple[str, list[PIIMatch]]:
    """
    Redact PII from text.

    Args:
        text: The text to redact

    Returns:
        Tuple of (redacted text, list of matches)
    """
    if not text:
        return text, []

    matches = scan_text(text)
    if not matches:
        return text, []

    # Sort by position (reverse) to replace from end
    sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)

    redacted = text
    for match in sorted_matches:
        redaction = f"[REDACTED:{match.pii_type.upper()}]"
        redacted = redacted[:match.start] + redaction + redacted[match.end:]

    return redacted, matches


def scan_github_content(title: str, body: str | None = None) -> dict:
    """
    Scan GitHub issue/PR content for PII.

    Args:
        title: Issue/PR title
        body: Issue/PR body/description

    Returns:
        Dict with scan results
    """
    results = {
        "has_pii": False,
        "title_pii": [],
        "body_pii": [],
        "redacted_title": title,
        "redacted_body": body,
        "blocked": False,
        "message": ""
    }

    # Scan title
    title_matches = scan_text(title)
    if title_matches:
        results["has_pii"] = True
        results["title_pii"] = [{"type": m.pii_type, "value": "[hidden]"} for m in title_matches]
        results["redacted_title"], _ = redact_text(title)

    # Scan body
    if body:
        body_matches = scan_text(body)
        if body_matches:
            results["has_pii"] = True
            results["body_pii"] = [{"type": m.pii_type, "value": "[hidden]"} for m in body_matches]
            results["redacted_body"], _ = redact_text(body)

    # Determine if blocked
    critical_types = {"ssn", "credit_card", "private_key", "aws_key"}
    all_matches = title_matches + (scan_text(body) if body else [])

    for match in all_matches:
        if match.pii_type in critical_types:
            results["blocked"] = True
            results["message"] = f"Critical PII detected ({match.pii_type}). Item blocked from public project."
            break

    if results["has_pii"] and not results["blocked"]:
        results["message"] = "PII detected. Content will be redacted before adding to public project."

    return results


def main():
    """CLI interface for PII scanner."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="SLATE PII Scanner")
    parser.add_argument("--text", help="Text to scan")
    parser.add_argument("--title", help="Issue/PR title")
    parser.add_argument("--body", help="Issue/PR body")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--test", action="store_true", help="Run self-test")

    args = parser.parse_args()

    if args.test:
        # Self-test with sample PII
        test_cases = [
            ("Clean title", "This is a clean issue"),
            ("Email", "Contact me at user@example.com"),
            ("Phone", "Call me at 555-123-4567"),
            ("SSN", "My SSN is 123-45-6789"),
            ("API Key", "Use api_key_abc123def456ghi789"),
            ("GitHub Token", "Token: ghp_abcdefghijklmnopqrstuvwxyz123456"),
            ("Private IP (allowed)", "Server at 192.168.1.100"),
        ]

        print("PII Scanner Self-Test")
        print("=" * 50)
        for name, text in test_cases:
            matches = scan_text(text)
            status = "DETECTED" if matches else "CLEAN"
            types = ", ".join(m.pii_type for m in matches) if matches else "-"
            print(f"{name:25} | {status:10} | {types}")
        return 0

    if args.title:
        results = scan_github_content(args.title, args.body)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if results["has_pii"]:
                print(f"PII DETECTED: {results['message']}")
                if results["blocked"]:
                    return 1
            else:
                print("No PII detected")
        return 1 if results["blocked"] else 0

    if args.text:
        matches = scan_text(args.text)
        if args.json:
            print(json.dumps([{"type": m.pii_type, "start": m.start, "end": m.end} for m in matches]))
        else:
            if matches:
                print(f"Found {len(matches)} PII match(es):")
                for m in matches:
                    print(f"  - {m.pii_type}: position {m.start}-{m.end}")
            else:
                print("No PII detected")
        return 1 if matches else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
