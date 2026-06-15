
import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns.

    Examples:
        "vintage graphic tee under $30, size M"
        → {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}

        "90s track jacket in size L"
        → {"description": "90s track jacket", "size": "L", "max_price": None}
    """
    # Extract max price: "under $30", "under 30", "less than $40", "$30 or less"
    price_match = re.search(
        r"(?:under|less than|max|below|up to)\s*\$?(\d+(?:\.\d+)?)"
        r"|\$(\d+(?:\.\d+)?)\s*(?:or less|max)",
        query,
        re.IGNORECASE,
    )
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)

    # Extract size: "size M", "in M", "size: XL", standalone S/M/L/XL/XXS/XXL
    size_match = re.search(
        r"\bsize[:\s]+([A-Z]{1,3}(?:/[A-Z]{1,3})?)\b"
        r"|\bin\s+size\s+([A-Z]{1,3})\b"
        r"|\b(XXS|XXL|XS|XL|[SML])\b",
        query,
        re.IGNORECASE,
    )
    size = None
    if size_match:
        size = (size_match.group(1) or size_match.group(2) or size_match.group(3)).upper()

    # Description: strip price/size phrases and leftover filler words
    description = query
    if price_match:
        description = description[:price_match.start()] + description[price_match.end():]
    if size_match:
        description = description[:size_match.start()] + description[size_match.end():]

    # Clean up common connector words left behind
    description = re.sub(
        r"\b(size|in|under|for|a|an|the|,|looking for|find me|i want)\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"\s+", " ", description).strip(" ,.")

    return {
        "description": description or query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop and returns
    the completed session dict.

    Returns:
        session dict — check session["error"] first. If not None, the run
        ended early and outfit_suggestion / fit_card will be None.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        filters = []
        if parsed["size"]:
            filters.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            filters.append(f"under ${parsed['max_price']:.0f}")
        filter_str = " and ".join(filters)
        detail = f" ({filter_str})" if filter_str else ""
        session["error"] = (
            f"No listings found for \"{parsed['description']}\"{detail}. "
            "Try broadening your search — different keywords, a higher price, or no size filter."
        )
        return session

    # Step 4: select top result
    session["selected_item"] = results[0]

    # Step 5: suggest outfit
    outfit = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    session["outfit_suggestion"] = outfit

    # Step 6: create fit card
    fit_card = create_fit_card(
        outfit=outfit,
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # Step 7: return session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")