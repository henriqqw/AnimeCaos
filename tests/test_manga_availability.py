"""
Standalone test: verifies that manga with no hosted chapters are correctly
detected and that manga with chapters return True.

Run with:  python -m pytest tests/test_manga_availability.py -v
or simply: python tests/test_manga_availability.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from animecaos.services.manga_service import MangaService


def _search_first(svc: MangaService, query: str) -> dict | None:
    results = svc.search_manga(query)
    return results[0] if results else None


def test_hisoka_no_chapters():
    """Hisoka - Origin Story has 0 hosted chapters despite showing pt-br in metadata."""
    svc = MangaService()
    result = _search_first(svc, "Hunter x Hunter - Hisoka Origin Story")
    assert result is not None, "Search returned no results for Hisoka"
    mid = result["id"]
    print(f"  Hisoka manga_id: {mid}")
    has = svc.has_chapters(mid)
    print(f"  has_chapters: {has}")
    assert has is False, f"Expected False (no chapters) but got {has} for {mid}"
    print("  PASS: Hisoka correctly identified as unavailable")


def test_one_piece_has_chapters():
    """One Piece should have chapters available."""
    svc = MangaService()
    result = _search_first(svc, "One Piece")
    assert result is not None, "Search returned no results for One Piece"
    mid = result["id"]
    print(f"  One Piece manga_id: {mid}")
    has = svc.has_chapters(mid)
    print(f"  has_chapters: {has}")
    assert has is True, f"Expected True but got {has} for {mid}"
    print("  PASS: One Piece correctly identified as available")


def test_naruto_has_chapters():
    """Naruto should have chapters available."""
    svc = MangaService()
    result = _search_first(svc, "Naruto")
    assert result is not None, "Search returned no results for Naruto"
    mid = result["id"]
    print(f"  Naruto manga_id: {mid}")
    has = svc.has_chapters(mid)
    print(f"  has_chapters: {has}")
    assert has is True, f"Expected True but got {has} for {mid}"
    print("  PASS: Naruto correctly identified as available")


if __name__ == "__main__":
    print("=== Manga availability standalone tests ===\n")
    tests = [test_hisoka_no_chapters, test_one_piece_has_chapters, test_naruto_has_chapters]
    passed = 0
    failed = 0
    for t in tests:
        print(f"--- {t.__name__} ---")
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
        print()
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
