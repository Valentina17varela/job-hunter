# FAQ

**Does it apply to jobs for me?** No. It finds, filters, scores and prepares documents. You review and apply yourself. This is a design rule, not a missing feature.

**Why no LinkedIn, Indeed or Glassdoor?** They forbid automated access and block it. Job Hunter only uses public APIs and feeds, and offers *Add a posting* for anything you find elsewhere (paste the text, or the link for pages that do not need a login).

**Does anything run in the background?** No. There is no scheduler, daemon or notification. The UI only listens while `jobhunter ui` is running.

**Where is my data?** In the folder where you ran `jobhunter init`: `config/` (settings, your CV), `data/` (SQLite database, run logs) and `out/` (generated CVs and letters). Nothing is uploaded anywhere. To delete everything, delete that folder (or just `data/jobhunter.db` to forget the postings).

**What is sent to the AI?** The plain text of the CV items you marked, your `scoring.candidate_context` and the posting text. Never your name, email, phone or links: they live in the LaTeX header, which is never sent. With a remote provider that text goes to that provider.

**Can the AI invent things in my CV?** The tailored CV is assembled by code that copies *your* LaTeX; the AI only picks and orders your own bullets. Letter text is checked against your CV (numbers, names, dates) and a package that fails the check is not marked verified.

**Why "Below match score" if the salary is fine?** That label comes from the AI's score (0–100) being under your `scoring.score_threshold`; the salary rule is separate. You can still build a package for any posting by hand.

**Can I use it without a Claude subscription?** Today: an Anthropic API key. OpenAI-compatible servers (Ollama, OpenRouter…) are specified in [specs/20](../specs/20-openai-compatible-backend.md) and not built yet.

**How do I add a job board?** [ADDING_A_SOURCE.md](ADDING_A_SOURCE.md).

**Which LaTeX engine?** `latex.engine: auto` (default) uses tectonic if installed, else `latexmk` from TeX Live.

**Windows?** Through WSL.

**How do I contribute?** [CONTRIBUTING.md](../CONTRIBUTING.md). The plan is in [specs/08-roadmap.md](../specs/08-roadmap.md).
