# FitFindr

FitFindr is an AI-powered secondhand shopping agent. Given a natural language query, it searches a mock dataset of thrift listings, selects the best match, suggests outfit combinations using the user's existing wardrobe, and generates a shareable OOTD caption. If no listings match the query, the agent tells the user exactly what filters were applied and what to try instead — it never silently fails or crashes.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # Pytest tests for all three tools
├── agent.py                   # Planning loop (run_agent, _parse_query)
├── app.py                     # Gradio UI (handle_query + layout)
├── tools.py                   # Three tools: search_listings, suggest_outfit, create_fit_card
├── planning.md                # Design spec and architecture
└── requirements.txt           # Python dependencies
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Then open the localhost URL shown in your terminal.

Run tests:

```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's description, with optional hard filters for size and price.

**Inputs:**

- `description` (str) — keywords describing the item (e.g. `"vintage graphic tee"`)
- `size` (str | None) — size to filter by, case-insensitive substring match (e.g. `"M"` matches `"S/M"`). Pass `None` to skip.
- `max_price` (float | None) — price ceiling, inclusive. Pass `None` to skip.

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given the thrifted item and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations. Falls back to general styling advice if the wardrobe is empty.

**Inputs:**

- `new_item` (dict) — a listing dict from `search_listings`
- `wardrobe` (dict) — wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty.

**Output:** `str` — a non-empty string with outfit suggestions or general styling advice. Never raises.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Calls the Groq LLM to generate a 2–4 sentence Instagram/TikTok-style OOTD caption for the thrifted find. Uses higher temperature so output varies across calls.

**Inputs:**

- `outfit` (str) — the outfit suggestion string from `suggest_outfit`
- `new_item` (dict) — the listing dict for the thrifted item (used for title, price, platform)

**Output:** `str` — a casual, shareable caption that mentions the item name, price, and platform once each. If `outfit` is empty or whitespace-only, returns a descriptive error message string instead of calling the LLM. Never raises.

---

## How the Planning Loop Works

The loop in `run_agent()` is strictly sequential with one conditional branch:

1. **Parse** the user's query with `_parse_query()` — extracts `description`, `size`, and `max_price` using regex. Stores result in `session["parsed"]`.

2. **Search** — calls `search_listings()` with the parsed parameters. Stores results in `session["search_results"]`.

3. **Branch on results:**
   - If `search_results` is empty → set `session["error"]` to a message that names the filters applied and suggests what to try, then **return early**. `suggest_outfit` and `create_fit_card` are never called.
   - If results exist → set `session["selected_item"] = results[0]` and continue.

4. **Suggest outfit** — calls `suggest_outfit(selected_item, wardrobe)`. Stores result in `session["outfit_suggestion"]`.

5. **Create fit card** — calls `create_fit_card(outfit_suggestion, selected_item)`. Stores result in `session["fit_card"]`.

6. **Return** the session dict.

The agent's behavior changes based on what `search_listings` returns — it does not call all three tools unconditionally every time.

---

## State Management

All state lives in a single session dict created fresh by `_new_session()` at the start of each `run_agent()` call. There is no global state.

| Step           | Reads from session                   | Writes to session   |
| -------------- | ------------------------------------ | ------------------- |
| Parse          | `query`                              | `parsed`            |
| Search         | `parsed`                             | `search_results`    |
| Select         | `search_results`                     | `selected_item`     |
| Suggest outfit | `selected_item`, `wardrobe`          | `outfit_suggestion` |
| Fit card       | `outfit_suggestion`, `selected_item` | `fit_card`          |
| Error          | —                                    | `error`             |

Each tool receives its inputs directly as function arguments (not by reading the session dict itself) — the agent extracts the right values from the session and passes them in. This keeps tools independently testable.

---

## Error Handling

### `search_listings` — no results

If no listings match the query after filtering, the function returns `[]`. The agent detects this immediately, builds a message listing exactly which filters were active (e.g. "size M and under $30"), and sets `session["error"]`. It returns the session early without calling the remaining tools.

**Tested example:** `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]` with no exception. The agent responds: _"No listings found for 'designer ballgown' (size XXS and under $5). Try broadening your search — different keywords, a higher price, or no size filter."_

### `suggest_outfit` — empty wardrobe

Before building the LLM prompt, the tool checks whether `wardrobe["items"]` is empty. If so, it sends a different prompt asking for general styling advice (what types of pieces pair well, what vibe the item suits) rather than specific wardrobe pairings. It always returns a non-empty string.

**Tested example:** `suggest_outfit(results[0], get_empty_wardrobe())` returns a useful styling paragraph rather than crashing or returning an empty string.

### `create_fit_card` — empty outfit string

The function checks `outfit.strip()` at the top. If empty or whitespace-only, it immediately returns `"Couldn't generate a fit card — outfit suggestion was empty or missing."` without calling the LLM.

**Tested example:** `create_fit_card("", results[0])` returns the error string above with no exception raised.

---

## Spec Reflection

**One way the spec helped:** Writing out the state management table in `planning.md` before coding made it obvious that tools should receive their inputs as function arguments rather than reading directly from the session dict. That decision made each tool independently testable with `pytest` without needing to construct a full session.

**One way implementation diverged from the spec:** The spec described the planning loop as potentially complex with multiple branches. In practice, the only meaningful branch is the no-results early exit — everything else is unconditional. The loop is simpler than the spec implied, which turned out to be fine because the instructions confirmed that what matters is that behavior _changes based on results_, not that the loop is architecturally elaborate.

---

## AI Usage

Instance 1 — docstrings

I asked Claude to write the docstrings for the three functions in tools.py. I reviewed them and used them as-is since they matched the function signatures.

Instance 2 — error messages

I asked Claude to suggest wording for the no-results error message in run_agent(). I used the suggestion with minor edits to make it more specific about which filters were applied.
