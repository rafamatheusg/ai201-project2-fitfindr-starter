# FitFindr — planning.md

---

## Tools

### Tool 1: search_listings

**What it does:**
Loads all mock listings, applies hard filters (price ceiling, size), then scores each remaining listing by keyword overlap with the user's description. Returns the top matches sorted by relevance score.

**Input parameters:**

- `description` (str): Keywords describing the item (e.g., "vintage graphic tee")
- `size` (str | None): Size string to filter by; case-insensitive substring match (e.g., "M" matches "S/M"). None = no filter.
- `max_price` (float | None): Price ceiling, inclusive. None = no filter.

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict has: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` if nothing matches — never raises.

**What happens if it fails or returns nothing:**
The agent checks for an empty list immediately after calling this tool. If empty, it sets `session["error"]` to a user-friendly message explaining what filters were applied and suggesting they broaden the search, then returns the session early without calling the remaining tools.

---

### Tool 2: suggest_outfit

**What it does:**
Calls the Groq LLM to suggest 1–2 complete outfits combining the thrifted item with pieces from the user's wardrobe. Falls back to general styling advice when the wardrobe is empty.

**Input parameters:**

- `new_item` (dict): The selected listing dict (the item the user is considering).
- `wardrobe` (dict): Wardrobe dict with an `items` key containing a list of wardrobe item dicts. May have an empty `items` list.

**What it returns:**
A non-empty string with outfit suggestions. If the wardrobe is empty, the string contains general styling advice instead of specific wardrobe pairings.

**What happens if it fails or returns nothing:**
If the LLM returns an empty response (rare), the agent stores an empty string in `session["outfit_suggestion"]`. `create_fit_card` guards against this and returns an error string rather than raising.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM at higher temperature to generate a 2–4 sentence Instagram/TikTok-style OOTD caption for the thrifted find. The caption mentions the item name, price, and platform naturally.

**Input parameters:**

- `outfit` (str): The outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict): The listing dict for the thrifted item (used for title, price, platform).

**What it returns:**
A 2–4 sentence string suitable as a social media caption.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, the function returns a descriptive error string immediately without calling the LLM. It never raises an exception.

---

## Planning Loop

The loop is strictly sequential — each step's output feeds directly into the next:

1. Parse query → extract `description`, `size`, `max_price`
2. Call `search_listings` → if empty list, set error and return early
3. Pick `results[0]` as `selected_item` (highest relevance score)
4. Call `suggest_outfit(selected_item, wardrobe)`
5. Call `create_fit_card(outfit_suggestion, selected_item)`
6. Return session

There's no branching beyond the no-results early exit. The agent doesn't re-rank or retry tools.

---

## State Management

All state lives in the session dict initialized by `_new_session()`. Each step reads from and writes to this dict:

| Step     | Reads                                                      | Writes                         |
| -------- | ---------------------------------------------------------- | ------------------------------ |
| Parse    | `session["query"]`                                         | `session["parsed"]`            |
| Search   | `session["parsed"]`                                        | `session["search_results"]`    |
| Select   | `session["search_results"]`                                | `session["selected_item"]`     |
| Outfit   | `session["selected_item"]`, `session["wardrobe"]`          | `session["outfit_suggestion"]` |
| Fit card | `session["outfit_suggestion"]`, `session["selected_item"]` | `session["fit_card"]`          |

No global state. Every `run_agent()` call gets a fresh session dict.

---

## Error Handling

| Tool            | Failure mode                          | Agent response                                                                                                                                                         |
| --------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| search_listings | No results match the query            | Set `session["error"]` with a message listing which filters were applied and suggesting broader search terms; return session immediately without calling further tools |
| suggest_outfit  | Wardrobe is empty                     | Detect `wardrobe["items"] == []` before calling LLM; switch to a general-styling prompt instead of a wardrobe-pairing prompt                                           |
| create_fit_card | Outfit input is missing or incomplete | Guard at the top of the function: if `outfit.strip()` is empty, return a descriptive error string and skip the LLM call entirely                                       |

---

## Architecture

```
User query (natural language)
        │
        ▼
┌─────────────────────────────────┐
│          run_agent()            │
│                                 │
│  1. _new_session(query, wardrobe)│
│  2. _parse_query(query)         │
│     → parsed {desc, size, price}│
│                                 │
│  3. search_listings(...)        │──► empty? → set error, return early
│     → search_results            │
│     → selected_item = [0]       │
│                                 │
│  4. suggest_outfit(             │
│       selected_item, wardrobe)  │◄── wardrobe empty? → general advice
│     → outfit_suggestion         │
│                                 │
│  5. create_fit_card(            │
│       outfit_suggestion,        │◄── outfit empty? → error string
│       selected_item)            │
│     → fit_card                  │
│                                 │
│  6. return session              │
└─────────────────────────────────┘
        │
        ▼
  session dict:
    error            ← None on success
    selected_item    ← top listing
    outfit_suggestion
    fit_card         ← OOTD caption
```

---

## AI Tool Plan

Instance 1 — docstrings

I asked Claude to write the docstrings for the three functions in tools.py. I reviewed them and used them as-is since they matched the function signatures.

Instance 2 — error messages

I asked Claude to suggest wording for the no-results error message in run_agent(). I used the suggestion with minor edits to make it more specific about which filters were applied.

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** `_parse_query()` extracts:

- `description` = "vintage graphic tee"
- `size` = None (no size mentioned)
- `max_price` = 30.0

**Step 2:** `search_listings("vintage graphic tee", size=None, max_price=30.0)` loads all 40 listings, removes any over $30, then scores the rest by how many of ["vintage", "graphic", "tee"] appear in their text fields. Returns sorted results — a vintage band tee at $24 lands at the top.

**Step 3:** `selected_item = results[0]` — the vintage band tee.

**Step 4:** `suggest_outfit(selected_item, example_wardrobe)` builds a prompt listing the user's wardrobe items (baggy jeans, chunky sneakers, etc.) and asks the LLM to suggest two specific outfits. The LLM responds with something like: "Pair the Nirvana tee with your baggy light-wash jeans and platform Docs for a classic 90s grunge look. For a softer take, tuck it into the plaid midi skirt with white chunky sneakers and a thin gold chain."

**Step 5:** `create_fit_card(outfit, selected_item)` sends the outfit text and item metadata to the LLM at temperature 0.9. The LLM generates a caption: "thrifted this Nirvana tee for $24 off Depop and honestly it was meant to be 🖤 styled it baggy-tucked into my fave light-wash jeans with chunky sneakers — full 90s energy without trying. vintage always wins."

**Final output to user:**

- **Listing panel**: formatted card showing title, price, platform, condition, colors, tags, and description
- **Outfit panel**: the two outfit suggestions from Step 4
- **Fit card panel**: the OOTD caption from Step 5
