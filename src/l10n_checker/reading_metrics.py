"""Frozen issue 10 text-coverage diagnostics, separate from defect matching."""

import re
import unicodedata
from difflib import SequenceMatcher

from l10n_checker.tiling import region_candidates


def normalize(text: str, fuzzy=False) -> str:
    text = unicodedata.normalize("NFC", text)
    # The reference excludes icons/bullets; preserve letters, accents, case,
    # punctuation and arithmetic signs. Raw model text remains in the record.
    text = "".join(
        c
        for c in text
        if unicodedata.category(c) not in ("So", "Co") and c not in "•\ufe0f"
    )
    if fuzzy:
        text = text.replace("…", "...")
    return " ".join(text.split())


def span_score(reference: str, observed: str) -> tuple[bool, float]:
    """Exact containment or the best comparable-length token span similarity."""
    expected, seen = normalize(reference), normalize(observed)
    if re.search(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", seen):
        return True, 1.0
    if len(expected) < 8:
        return False, 0.0
    expected, seen = normalize(reference, fuzzy=True), normalize(observed, fuzzy=True)
    words = list(re.finditer(r"\S+", seen))
    best = 0.0
    for i, start in enumerate(words):
        for end in words[i:]:
            candidate = seen[start.start() : end.end()]
            ratio = len(candidate) / len(expected)
            if ratio > 1.25:
                break
            if ratio >= 0.8:
                best = max(
                    best,
                    SequenceMatcher(None, expected, candidate, autojunk=False).ratio(),
                )
    return False, best


def coverage(rows: list[dict], readings: list[dict]) -> dict:
    """Count each reference unit once, even when tiles overlap."""
    matches = []
    for row in rows:
        exact = False
        best = 0.0
        evidence = []
        for index, reading in enumerate(readings):
            same_text_rows = [
                r
                for r in rows
                if normalize(r["text_seen"]) == normalize(row["text_seen"])
            ]
            cells = region_candidates(
                reading["region"], tuple(reading["box"]), (2400, 1080)
            )
            if len(same_text_rows) > 1 and row["region"] not in cells:
                continue
            # Do not let a research button or description containing "Archery"
            # cover the separate tree label. Unique texts otherwise ignore
            # region: mislocalization is a separate diagnostic (D-026).
            nested_in_longer_unit = any(
                normalize(row["text_seen"]) in normalize(other["text_seen"])
                and normalize(other["text_seen"]) != normalize(row["text_seen"])
                and span_score(other["text_seen"], reading["text_seen"])[1] >= 0.90
                for other in rows
            )
            if nested_in_longer_unit:
                continue
            is_exact, score = span_score(row["text_seen"], reading["text_seen"])
            exact = exact or is_exact
            best = max(best, score)
            if is_exact or score >= 0.90:
                evidence.append(index)
        matches.append(
            {
                "reference_id": row["id"],
                "section": row["section"],
                "primary": row["primary_denominator"],
                "exact": exact,
                "fuzzy": best >= 0.90,
                "best_score": round(best, 6),
                "reading_indices": evidence,
            }
        )

    def aggregate(subset):
        count = len(subset)
        exact = sum(item["exact"] for item in subset)
        fuzzy = sum(item["fuzzy"] for item in subset)
        return {
            "reference_count": count,
            "exact_count": exact,
            "fuzzy_count": fuzzy,
            "exact_share": exact / count if count else None,
            "fuzzy_share": fuzzy / count if count else None,
        }

    primary = [m for m in matches if m["primary"]]
    return {
        "primary": aggregate(primary),
        "sections": {
            s: aggregate([m for m in primary if m["section"] == s])
            for s in ("tree", "controls", "description")
        },
        "diagnostic_clipped": aggregate([m for m in matches if not m["primary"]]),
        "matches": matches,
    }


def image_tokens(usage: dict | None) -> int | None:
    if not usage or not usage.get("prompt_tokens_details"):
        return None
    counts = [
        part["token_count"]
        for part in usage["prompt_tokens_details"]
        if part.get("modality", "").upper() == "IMAGE" and "token_count" in part
    ]
    return sum(counts) if counts else None
