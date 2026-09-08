# CPCompass

CPCompass is a deployed Codeforces analytics and training assistant that turns a user's submission history into topic-level weakness analysis and focused practice recommendations.

It combines the Codeforces API, a normalized MySQL backend, transparent recommendation heuristics, curated C2Ladders frequency data, and a custom O(1) LRU cache behind a Streamlit interface.

> **Status:** V1 is deployed on Railway with a persistent MySQL database.

## What CPCompass does

Enter any public Codeforces handle and CPCompass will:

- import and refresh the user's public submission history;
- show rating, solved/attempted counts, submissions, and solve rate;
- estimate weak topics using Bayesian-smoothed success rates;
- recommend unseen problems through three training modes;
- compare official Codeforces ratings with a heuristic era-adjusted difficulty;
- use C2Ladders problem frequency as an external curated quality signal;
- cache recommendation results using a custom dictionary + doubly linked list LRU cache.

The recommendation system is intentionally transparent: it uses inspectable heuristics rather than a black-box model API.

---

## Training modes

### Smart Picks

Targets problems that are useful for the user's current weaknesses while still being appropriately challenging.

The score combines:

```text
55% topic weakness match
35% difficulty fit
10% curated / popularity quality signal
```

Smart Picks target roughly a **40% predicted solve probability** and return up to 15 problems.

### QuickSolve

Targets high-quality problems around:

```text
user rating - 300
```

Useful for fast repetitions, pattern reinforcement, and confidence-building practice.

### DeepThink

Targets stretch problems around:

```text
user rating + 300
```

Designed for slower, deliberate practice where the user is expected to struggle before solving.

---

## Recommendation methodology

### 1. Bayesian-smoothed weakness

Raw topic solve rates can be misleading when a user has attempted only a few problems. CPCompass shrinks each topic toward the user's overall solve rate.

For overall solve rate `r`, topic solved count `s`, and topic attempted count `a`:

```text
smoothed_success = (s + 8r) / (a + 8)
weakness_score  = 100 * (1 - smoothed_success)
```

The prior strength is currently `8`.

### 2. Era-adjusted difficulty

Codeforces rating distributions and contest structures have changed over time, so CPCompass estimates a modern-equivalent training rating.

Problems are grouped by:

```text
contest group + problem index + era
```

The median rating for an era is compared with the median for recent contests (2024+). The difference is:

- clipped to `[-300, 300]`;
- shrunk using `n / (n + 30)` so small samples have less influence;
- applied to the official rating;
- rounded to the nearest 50.

Therefore an era-adjusted rating can be **higher or lower** than the official rating. It is a training heuristic, not a replacement for Codeforces' official difficulty.

### 3. Challenge fit

CPCompass uses an Elo-style heuristic:

```text
p = 1 / (1 + 10^((effective_rating - user_rating) / 400))
```

`p` is used only as a relative challenge estimate. It is **not a calibrated machine-learning probability**.

### 4. Curated quality signal

`classic_import.py` imports public ladder data from C2Ladders and stores each matched problem's frequency in `classic_problems`.

C2 frequency is log-normalized before it contributes to recommendation quality so a few very high-frequency problems do not dominate the ranking.

When C2 data is unavailable for a problem, Codeforces solved count is used as a fallback popularity signal.

---

## Architecture

```text
                       ┌──────────────────────┐
                       │    Codeforces API     │
                       └──────────┬───────────┘
                                  │
                    user.info / user.status
                                  │
                                  v
                         cf_api.py / cf_import.py
                                  │
                                  │
contest.list + problemset.problems│
              │                   │
              v                   v
      problemset_import.py     MySQL
              │            cpcompass database
              │                   │
              └───────────────────┤
                                  │
C2Ladders API -> classic_import.py│
                                  │
                                  v
                           recommender.py
                                  │
                         custom LRU cache
                                  │
                                  v
                            Streamlit UI
                                  │
                                  v
                         Railway deployment
```

The global problem catalog and curated C2 data are imported separately from per-user Codeforces histories.

---

## Database design

| Object | Purpose |
| --- | --- |
| `users` | Unique Codeforces handles |
| `problems` | Problem metadata, rating, contest information, solved count |
| `submissions` | User submissions, verdicts, timestamps, and problem relationships |
| `topics` | Unique Codeforces tags/topics |
| `problem_topics` | Many-to-many relationship between problems and topics |
| `classic_problems` | Curated source membership and C2Ladders frequency |
| `topic_stats` | View for per-user topic attempts, solves, success rate, and wrong submissions |

Foreign keys preserve relationships and unique keys allow importer upserts to be rerun safely.

---

## Custom LRU cache

`lru_cache.py` implements an LRU cache using:

```text
hash map + doubly linked list
```

Expected complexity:

```text
get: O(1)
put: O(1)
eviction: O(1)
```

The cache currently stores up to 10 recommendation results and is protected by an `RLock`.

It is process-local memory, so:

- users hitting the same Railway process can share cached recommendation entries;
- a process restart or redeploy clears the cache;
- MySQL data remains persistent;
- separate app instances would have independent caches.

A distributed cache such as Redis would be a natural future extension if CPCompass were scaled to multiple application instances.

---

## Tech stack

- **Python**
- **Streamlit**
- **MySQL 8**
- **Pandas**
- **mysql-connector-python**
- **Requests**
- **Codeforces API**
- **C2Ladders public ladder data**
- **Railway** for application + MySQL deployment

---

## Running locally

### 1. Clone and install dependencies

```bash
git clone https://github.com/EqualCell/CPCompass.git
cd CPCompass
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Create the MySQL schema

Open MySQL:

```bash
mysql -u root -p
```

Then:

```sql
SOURCE schema.sql;
```

The schema creates the `cpcompass` database, application tables, relationships, and the `topic_stats` view.

### 3. Configure environment variables

Copy `.env.example` to `.env` and configure:

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=cpcompass
```

Do not commit `.env`.

### 4. Import the Codeforces problem catalog

```bash
python problemset_import.py
```

This loads global problem metadata, topics, contest information, ratings, and solved counts.

### 5. Import C2Ladders curated frequency data

Run this after the problem catalog exists:

```bash
python classic_import.py
```

The importer matches C2Ladders entries against Codeforces problems already stored in the database and upserts their frequency values. It is safe to rerun.

### 6. Start the app

```bash
streamlit run app.py
```

Enter a Codeforces handle and press **Enter** or click **Analyze profile**.

You can also import a profile directly from the terminal:

```bash
python cf_import.py
```

---

## Project layout

```text
app.py                Streamlit UI and dashboard
cf_api.py             Shared Codeforces API client
cf_import.py          Per-user profile/submission importer
problemset_import.py  Global Codeforces problem catalog importer
classic_import.py     C2Ladders curated-frequency importer
recommender.py        Weakness analysis and recommendation logic
lru_cache.py          Custom O(1) LRU cache
db.py                 MySQL connection/query helper
schema.sql            Database schema and topic_stats view
requirements.txt      Python dependencies
.env.example          Environment variable template
```

---

## Deployment

The current V1 is deployed on Railway using two services:

```text
CPCompass Streamlit service
        │
        └── Railway private network ──> Railway MySQL service
```

The application reads database credentials from environment variables. Railway's MySQL volume persists data independently of application redeploys.

GitHub pushes to the deployment branch can trigger application rebuilds, while database schema/data changes must be applied separately to the persistent MySQL database.

---

## Current limitations

- Recommendation scores are heuristics rather than calibrated ML predictions.
- Era adjustment depends on historical grouping and available sample sizes.
- C2Ladders frequency is an external curated signal and is not generated by CPCompass itself.
- Global Codeforces and C2 imports are currently manual rather than scheduled.
- Initial profile imports can take time for users with large submission histories.
- The LRU cache is process-local rather than distributed.
- There is currently no authentication or profile ownership system.
- Newly encountered problems can lack complete metadata until the global catalog is refreshed.

---

## Possible future work

- automated daily problemset/C2 synchronization;
- MySQL indexing experiments with `EXPLAIN` and query-performance benchmarks;
- B+ tree / hash-index simulation for database internals exploration;
- distributed caching with Redis for multi-instance deployment;
- stronger ranking evaluation using historical solve outcomes;
- richer training-history and progress visualizations.

---

## Author

Created by **EqualCell**.

- Codeforces: https://codeforces.com/profile/EqualCell
- GitHub: https://github.com/EqualCell

CPCompass is an independent project and is not affiliated with Codeforces or C2Ladders.
