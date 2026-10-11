# 02 — Data model

## 1. `Job` model (common schema)

Every source normalizes to this.

| Field | Type | Notes |
|---|---|---|
| `source` | str | `greenhouse`, `lever`, `ashby`, `remoteok`… |
| `external_id` | str | ID in the source |
| `company` | str | Human-readable name |
| `title` | str | |
| `location` | str \| None | Original text |
| `remote` | `"remote" \| "hybrid" \| "onsite" \| "unknown"` | Inferred |
| `description` | str | Plain text (HTML cleaned) |
| `url` | str | Apply link |
| `salary_min` / `salary_max` | int \| None | Annual amount in `salary_currency` (hourly/monthly annualized); converted to USD only in the filter, using the configured FX table |
| `salary_currency` | str \| None | Original |
| `posted_at` | datetime \| None | |
| `fetched_at` | datetime | |
| `content_hash` | str | sha256 of title+description (detects changes) |

**Unique key:** `(source, external_id)`.

## 2. Posting statuses

```
new → filtered            (rejected by a hard rule; reason stored)
new → passed → scored → selected → packaged → applied → replied | rejected | closed
                      ↘ below_threshold
passed → score_failed     (retryable)
```

`applied`, `replied`, `rejected`, `closed` are set by the person with `jobhunter mark`.

## 3. SQLite tables

```sql
jobs(
  id INTEGER PRIMARY KEY,
  source TEXT, external_id TEXT, company TEXT, title TEXT,
  location TEXT, remote TEXT, description TEXT, url TEXT,
  salary_min INT, salary_max INT, salary_currency TEXT,
  posted_at TEXT, fetched_at TEXT, last_seen_at TEXT, content_hash TEXT,
  status TEXT, filter_reason TEXT,
  UNIQUE(source, external_id)
);

scores(
  job_id INT REFERENCES jobs(id),
  score INT, reasons TEXT,           -- JSON: pros, cons, gaps
  model TEXT, profile_hash TEXT, prompt_version TEXT,
  created_at TEXT
);

packages(
  job_id INT REFERENCES jobs(id),
  path TEXT, model TEXT, created_at TEXT, verified INT
);

llm_calls(
  id INTEGER PRIMARY KEY,
  stage TEXT, model TEXT, job_id INT,
  tokens_in INT, tokens_out INT, tokens_cache_read INT,
  cost_usd REAL, created_at TEXT
);

fetch_log(
  id INTEGER PRIMARY KEY,
  source TEXT, target TEXT,          -- e.g. greenhouse / stripe
  status TEXT, jobs_found INT, error TEXT, created_at TEXT
);

events(                              -- status-change history
  job_id INT, from_status TEXT, to_status TEXT, note TEXT, created_at TEXT
);
```

### Application tracking (Phase 5, web UI)

```sql
applications(                        -- one row per posting the person applied to
  job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
  stage TEXT NOT NULL,               -- applied | screening | interviewing | offer | accepted | rejected | withdrawn | ghosted
  applied_at TEXT, updated_at TEXT, notes TEXT
);
interviews(
  id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES jobs(id),
  kind TEXT,                         -- recruiter | technical | system_design | hiring_manager | onsite | other
  scheduled_at TEXT, notes TEXT, outcome TEXT   -- pending | passed | failed
);
```

`applications.stage` maps to `jobs.status`: `applied` → `applied`; `screening`/`interviewing`/`offer`/`accepted` → `replied`; `rejected`/`withdrawn`/`ghosted` → `rejected`. Every change is also written to `events`.

## 4. Dedupe rules

1. Same `(source, external_id)` → same posting; if `content_hash` changes, the description is updated and the **score is invalidated** (back to `passed`).
2. Postings that stop appearing in the source for 7 days → `closed`.
3. Same company + same normalized title across different sources → the direct-ATS one is kept, the other is marked `duplicate`.
