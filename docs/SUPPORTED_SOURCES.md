# Supported sources

Generated from the source registry by `scripts/check_docs.py --write`; do not edit by hand. Only public APIs and feeds are used (see [specs/03-sources.md](../specs/03-sources.md)). To add one, follow [ADDING_A_SOURCE.md](ADDING_A_SOURCE.md).

| Source | Kind | What | Terms / API docs | Keys |
|---|---|---|---|---|
| `remotive` | aggregator | Remote jobs worldwide (link back required) | [link](https://remotive.com/api-documentation) | none |
| `remoteok` | aggregator | Remote jobs (link back required; the first feed item is a legal notice) | [link](https://remoteok.com/api) | none |
| `weworkremotely` | aggregator | We Work Remotely RSS feeds, one per category in `sources.wwr_categories` | [link](https://weworkremotely.com/remote-job-rss-feed) | none |
| `arbeitnow` | aggregator | Jobs in Europe, many remote (`sources.arbeitnow_pages` pages) | [link](https://documenter.getpostman.com/view/18545278/UVJbJdKh) | none |
| `jobicy` | aggregator | Remote jobs with structured salary (credit and link back requested) | [link](https://jobicy.com/jobs-rss-feed) | none |
| `ashby` | company board (`ats:` in companies.yaml) | Company job boards on Ashby | [link](https://developers.ashbyhq.com/docs/public-job-posting-api) | none |
| `greenhouse` | company board (`ats:` in companies.yaml) | Company job boards on Greenhouse (boards API) | [link](https://developers.greenhouse.io/job-board.html) | none |
| `lever` | company board (`ats:` in companies.yaml) | Company postings on Lever | [link](https://github.com/lever/postings-api) | none |
| `themuse` | aggregator | Jobs from The Muse, filtered by category, level and remote (optional key) | [link](https://www.themuse.com/developers/api/v2) | `THEMUSE_API_KEY` |
