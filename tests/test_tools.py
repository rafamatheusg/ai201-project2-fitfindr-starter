
import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    """Happy path: a common query should return at least one result."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    """Failure mode: impossible query returns [] without raising."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned items must be at or below max_price."""
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    """All returned items must contain the requested size (case-insensitive)."""
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "M" in item["size"].upper()


def test_search_returns_list_on_no_keyword_match():
    """Gibberish description with no keyword overlap returns [] without raising."""
    results = search_listings("xyzzy qwerty zork", size=None, max_price=None)
    assert results == []


def test_search_sorted_by_relevance():
    """Results should be sorted best-match first (first item scores >= last item)."""
    results = search_listings("vintage jacket", size=None, max_price=200)
    if len(results) >= 2:
        # Re-score the first and last items to verify ordering
        import re
        keywords = re.findall(r"\w+", "vintage jacket")

        def score(item):
            blob = " ".join([
                item.get("title", ""), item.get("description", ""),
                item.get("category", ""), item.get("brand", ""),
                " ".join(item.get("style_tags", [])),
                " ".join(item.get("colors", [])),
            ]).lower()
            return sum(1 for kw in keywords if kw in blob)

        assert score(results[0]) >= score(results[-1])


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    """Happy path: returns a non-empty string when wardrobe has items."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one listing to test suggest_outfit"
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0


def test_suggest_outfit_empty_wardrobe():
    """Failure mode: empty wardrobe returns general styling advice, not an error."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one listing to test suggest_outfit"
    outfit = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0  # must return something useful, not empty


def test_suggest_outfit_does_not_raise_on_empty_wardrobe():
    """Empty wardrobe must never raise an exception."""
    results = search_listings("jacket", size=None, max_price=200)
    if not results:
        pytest.skip("No listings available for this test")
    try:
        suggest_outfit(results[0], get_empty_wardrobe())
    except Exception as e:
        pytest.fail(f"suggest_outfit raised an exception on empty wardrobe: {e}")


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_happy_path():
    """Happy path: returns a non-empty caption string."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one listing to test create_fit_card"
    outfit = "Pair with baggy jeans and chunky sneakers for a 90s vibe."
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0


def test_create_fit_card_empty_outfit_string():
    """Failure mode: empty outfit returns an error message string, not an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one listing to test create_fit_card"
    card = create_fit_card("", results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0  # should return a descriptive error message


def test_create_fit_card_whitespace_outfit_string():
    """Failure mode: whitespace-only outfit also returns an error string, not an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one listing to test create_fit_card"
    card = create_fit_card("   ", results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0


def test_create_fit_card_does_not_raise_on_empty_outfit():
    """Empty outfit must never raise an exception."""
    results = search_listings("jacket", size=None, max_price=200)
    if not results:
        pytest.skip("No listings available for this test")
    try:
        create_fit_card("", results[0])
    except Exception as e:
        pytest.fail(f"create_fit_card raised an exception on empty outfit: {e}")


def test_create_fit_card_varies_output():
    """
    Fit card should produce different output for different items/outfits.
    Tests that the output isn't hardcoded.
    """
    results = search_listings("vintage tee", size=None, max_price=200)
    if len(results) < 2:
        pytest.skip("Need at least 2 listings to compare outputs")
    outfit = "Pair with baggy jeans and sneakers."
    card1 = create_fit_card(outfit, results[0])
    card2 = create_fit_card(outfit, results[1])
    # Different items should produce different captions
    assert card1 != card2