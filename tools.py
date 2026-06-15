

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Scoring: each keyword in `description` that appears (case-insensitive) in
    a listing's title, description, category, style_tags, colors, or brand
    earns 1 point. Listings with score 0 are excluded.
    """
    listings = load_listings()

    # Step 1: hard filters
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.upper() not in item["size"].upper():
            continue
        candidates.append(item)

    # Step 2: keyword scoring
    keywords = re.findall(r"\w+", description.lower())

    def _score(item: dict) -> int:
        # Build a blob of searchable text from the listing
        blob = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            item.get("brand", ""),
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
        ]).lower()
        return sum(1 for kw in keywords if kw in blob)

    scored = [(item, _score(item)) for item in candidates]
    scored = [(item, score) for item, score in scored if score > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [item for item, _ in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    Uses the Groq LLM. Falls back to general styling advice if wardrobe is empty.
    """
    client = _get_groq_client()
    wardrobe_items = wardrobe.get("items", [])

    item_summary = (
        f"{new_item['title']} — {new_item['description']} "
        f"(style tags: {', '.join(new_item.get('style_tags', []))}; "
        f"colors: {', '.join(new_item.get('colors', []))})"
    )

    if not wardrobe_items:
        prompt = (
            f"I just found this secondhand piece: {item_summary}\n\n"
            "The user doesn't have a wardrobe on file yet. "
            "Give 1–2 general outfit ideas — what types of pieces pair well with it, "
            "what vibe it suits, and how to style it. Keep it conversational and specific."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {w.get('title', w.get('name', 'Unknown item'))} "
            f"({w.get('category', '')}; colors: {', '.join(w.get('colors', []))})"
            for w in wardrobe_items
        )
        prompt = (
            f"I just found this secondhand piece: {item_summary}\n\n"
            f"Here's my current wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific pieces "
            "from my wardrobe above. Be concrete — name the actual wardrobe items by their title. "
            "Keep it conversational and fun."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption (2–4 sentences) for the thrifted find.
    Feels like a real OOTD post — casual, specific, authentic.
    """
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — outfit suggestion was empty or missing."

    client = _get_groq_client()

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok OOTD caption for this thrift find:\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']:.2f}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit idea: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person posting their outfit, not a product description\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the specific vibe of the outfit\n"
        "- Keep it under 4 sentences\n"
        "Return ONLY the caption, no intro text."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,  # higher temp for variety
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()