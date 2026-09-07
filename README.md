# CPCompass

CPCompass is a Codeforces training dashboard that turns submission history into topic analytics and focused practice recommendations. It combines a relational data pipeline, transparent scoring heuristics, and a custom LRU cache in a Streamlit application.

## Why it exists

Choosing the next practice problem can be harder than finding a problem list. CPCompass connects past attempts, topic-level success, historical rating patterns, and problem popularity to suggest useful next steps. Its scoring rules are inspectable rather than hidden behind a model API.

## Features

- Load or refresh an arbitrary public Codeforces profile from the UI.
- Switch between previously loaded profiles.
- Inspect attempted problems, solved problems, submission totals, and topic performance.
- Identify weaknesses using Bayesian-smoothed topic success rates.
- Compare official ratings with heuristic era-adjusted ratings.
- **Smart Picks:** combine topic weakness, challenge fit, and a quality signal.
- **QuickSolve:** practice near the training rating minus 300.
- **DeepThink:** stretch near the training rating plus 300.
- Inspect hit/miss statistics for a custom dictionary + doubly linked list LRU cache.

## Architecture

```text
Codeforces API
  |-- user.info / user.status --> cf_api.py --> cf_import.py --|
  |-- contest.list / problemset.problems --> problemset_import.py
                                                            |
                                                            v
                                                     MySQL cpcompass
                                                     tables + topic_stats
                                                            |
                                             db.py query/connection helper
                                                            |
                                            recommender.py --> LRU cache
                                                            |
                                                     app.py / Streamlit
```

The profile importer is also usable from the terminal. Importing its module does not prompt for input or start an import. The frontend never runs the global problemset import.

## Tech stack and tested environment

- Python **3.14.3**, tested on Windows
- MySQL **8.0.46**; schema targets MySQL 8.0+
- Streamlit **1.63.0**
- Pandas **3.0.5**
- mysql-connector-python **26.7.0**
- Requests **2.34.2**
- python-dotenv **1.2.3**

`requirements.txt` pins the runtime packages to the verified local environment. Other Python/package combinations have not been validated. MySQL must be installed and running separately.

## Setup

Run the following from the repository root after cloning it.

### 1. Create a virtual environment and install dependencies

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell activation is unavailable, use `venv\Scripts\python.exe` in place of `python`, and launch with `venv\Scripts\python.exe -m streamlit run app.py`.

macOS/Linux equivalent commands (not part of the tested environment):

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Create the MySQL schema

Start MySQL and open its client with an account permitted to create the database, tables, and view:

```text
mysql -u root -p
```

Enter the password at the prompt, then run from the MySQL client:

```sql
SOURCE schema.sql;
```

For shells supporting input redirection, the equivalent is:

```bash
mysql -u root -p < schema.sql
```

The schema creates `cpcompass`, six tables, and `topic_stats`. It contains no account creation, credentials, sample profiles, or database drops. `IF NOT EXISTS` preserves existing tables; it does not migrate incompatible old schemas or add missing indexes to existing tables. The view is replaced when the script is run.

For a custom database name, update the `CREATE DATABASE` and `USE` statements before initial setup and use the same name in `.env`. For a remote server, include the appropriate `-h` option in the client command.

### 3. Configure the environment

Copy the example:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux: `cp .env.example .env`.

Edit `.env` locally:

```dotenv
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=cpcompass
```

Set `MYSQL_PASSWORD` to the password for your MySQL account. No password is supplied by the application. Host, user, and database default to the values shown; an explicitly configured empty password is passed through as-is. Existing shell environment variables take precedence over `.env`.

Use a dedicated MySQL account for shared deployments rather than the local `root` default. Runtime operations need SELECT/INSERT/UPDATE on the application tables and SELECT on the view. Keep `.env` out of Git; `.env.example` contains no credentials.

### 4. Populate the global problemset

```bash
python problemset_import.py
```

This imports contest metadata, rated/unrated problems, topic links, and solved counts. It is required for a useful recommendation catalog and era/popularity information. Rerun it periodically to refresh the catalog; it is not automatically scheduled.

### 5. Start the dashboard

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit. Enter a **Codeforces Handle**, press **Load / Refresh Profile**, and wait for **Profile ready**. Use **Previously Loaded Profiles** to switch users. To refresh a selected profile, enter that handle in the input and press the same button.

The importer validates the handle before database writes, reuses existing problems/topics, and commits a profile refresh atomically. Repeated imports do not duplicate rows and update existing verdicts. The displayed imported count includes both new and existing submissions processed.

Optional terminal profile import:

```bash
python cf_import.py
```

## Database design

| Object | Purpose |
| --- | --- |
| `users` | Unique Codeforces handles with internal IDs |
| `problems` | Unique platform/external IDs, difficulty and contest metadata, solved counts |
| `submissions` | Codeforces submission IDs, user/problem foreign keys, verdicts and timestamps |
| `topics` | Unique topic names |
| `problem_topics` | Many-to-many problem/topic links |
| `classic_problems` | Optional curated membership and source provenance |
| `topic_stats` | View of distinct attempted/solved problems, success rate and wrong-submission totals per user/topic |

Foreign keys enforce relationships. Unique keys make importer upserts idempotent. Submission indexes support per-user analytics and solved-problem exclusion. New submission timestamps are stored as UTC without a timezone suffix.

## How recommendations work

For overall success rate `r`, topic solved count `s`, and topic attempt count `a`:

```text
r = overall_solved / overall_attempted (or 0.5 with no attempts)
smoothed_success = (s + 8*r) / (a + 8)
weakness = 100 * (1 - smoothed_success)
```

Era adjustment compares median ratings within the same contest group and problem index against a 2024-and-later baseline. Median differences are clipped to [-300, 300], shrunk by `n/(n+30)`, subtracted from the official rating, and rounded to the nearest 50. This is a historical normalization heuristic, not a measurement of true difficulty.

The challenge estimate is `p = 1 / (1 + 10**((effective_rating - training_rating)/400))`. It is an Elo-style heuristic, **not a calibrated ML solve-probability model**. Smart Picks target `p = 0.40`, combining weakness match (55%), difficulty fit (35%), and classic/popularity score (10%). At most two matching topic weaknesses contribute; up to 15 Smart Picks are returned.

QuickSolve targets `training_rating - 300`; DeepThink targets `training_rating + 300`. Both use a +/-150 window, combine distance fit with the quality signal, prioritize curated membership when present, and return up to five problems. QuickSolve is not clamped to 800; low-rated profiles may have no problems in its window.

Solved problems and problems without ratings/topics are excluded. If the user is unrated or the rating request fails, 1200 is used as a fallback training rating and the UI explicitly explains that fallback.

### Classic problems

No curated list is bundled. A fresh schema leaves `classic_problems` empty; popularity/solved counts provide the fallback quality signal. Curated-list ingestion is an optional future extension. Existing manually curated rows remain supported, including their `source` field. This project does not scrape third-party classic lists.

## Custom LRU cache

`lru_cache.py` implements a hashmap/dictionary plus a doubly linked list, with expected O(1) `get` and `put` and least-recently-used eviction. An `RLock` protects cache operations.

The 10-entry cache lives in the recommender process. It stores the training rating and recommendation/weakness DataFrames. Keys include user ID, rating, rating-fallback status, and database aggregates covering submissions, verdicts, problems, and classic counts. A frontend refresh bypasses lookup. Rating fallback explanations travel with the weakness DataFrame metadata, preserving the five-value recommendation return interface.

Streamlit sessions within one process share entries and metrics. Separate processes have separate caches. Restarting clears entries and counters; MySQL data persists. Explicit bypasses do not count as cache hits or misses. The rate lookup and version queries still run before a normal cache hit.

## Project layout

```text
app.py                Streamlit UI
cf_api.py             Shared profile/rating API client
cf_import.py          Reusable profile importer and CLI
problemset_import.py  Global problemset/metadata importer
recommender.py        Recommendation rules and cache integration
lru_cache.py          Custom LRU implementation
db.py                 Shared MySQL configuration and DataFrame query helper
schema.sql            Reproducible MySQL schema
requirements.txt      Tested runtime dependency versions
.env.example          Credential-free configuration template
```

## Limitations and future work

- Cache aggregates do not detect every in-place metadata/tag/classic-list edit. Restart Streamlit after a global catalog update to ensure fresh recommendations. Authoritative database revision tracking is future work.
- Initial profile imports fetch the full public history and can take time. API outages or rate limits may require retrying. The global importer currently uses direct requests rather than the shared profile client.
- Newly encountered profile problems may lack era/popularity metadata until a global import supplies it.
- There is no authentication or per-viewer profile ownership. Shared deployment needs access controls; the profile list and cache metrics are process/database-wide.
- Handle renames, nonstandard/Gym problem links, historical timestamp normalization, and concurrent-import retries need further work.
- The global importer commits in batches; a failed run can leave a partially refreshed catalog and can be rerun.
- There is no scheduled synchronization, curated-list ingestion, or calibrated prediction model.
- Restart Streamlit after changing imported module interfaces during development.
