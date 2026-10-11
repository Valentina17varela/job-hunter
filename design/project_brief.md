Product Requirements Document (PRD) & Project Brief: JobHunter

Product Name: JobHunter Copilot
Version: v0.4.2 (Desktop Local Daemon)
Document Status: Ready for Engineering & Design Alignment
Target Architecture: Local-first daemon (127.0.0.1:8080) driven by Python CLI (uv run jobhunter) and companion web dashboard.



1. Executive Summary & Vision

JobHunter is an open-source, local-first personal job search copilot engineered for senior knowledge workers and developers. Rather than relying on generic mass-application scrapers that harm candidate reputation, JobHunter acts as an autonomous pipeline agent that:





Crawls and harvests engineering postings across target boards (Greenhouse, Lever, Ashby, Workable, Hacker News).



Performs deep LLM semantic matching against the candidate’s master profile (alex_cv_master.tex).



Compiles verified, ATS-optimized, 1-page LaTeX CVs, custom cover letters, and personalized recruiter outreach messages.



Manages the full recruitment lifecycle via an interactive Kanban pipeline and streaming terminal interface.



2. Core Problem Statement





High-volume noise in modern job search: Traditional boards present hundreds of irrelevant listings; manual filtering is exhausting and prone to candidate fatigue.



Generic resumes fail ATS filters: Sending one static PDF to 50 companies yields low callback rates, while manually tailoring LaTeX files for every posting takes 45–60 minutes per job.



Fragmented tracking: Spreadsheets and third-party SaaS tools lose context, leak personal data, and fail to link directly with local source-code artifacts and real-time CLI commands.



3. Brand Identity & Visual Language





Brand Mascot / Logo:
A modern, user-friendly tech eagle looking directly forward wearing sleek dark sunglasses (JobHunter Eagle Mascot).  





Symbolism: Combines the eagle's precision hunting vision (spotting high-affinity roles) with a cool, approachable copilot personality.



Recommended Color Architecture:  





Dominant Base: Clean, crisp daylight white (#ffffff / #f8fafc) for maximum readability, trust, and document focus.



Primary Brand Accent: Electric Tech Blue (#0284c7 / #2563eb) conveying stability, professionalism, and confidence.



Affinity & Success Indicator: Emerald Green (#10b981) for high-match scores (≥88%), approved quality gates, and passed interview rounds.



Destructive / Alert Accent: Controlled Red (#ef4444) strictly reserved for hard exclusions, failed compilations, or worker kills.



4. Key Functional Areas & User Journeys

4.1 Home — Guided 3-Step Orchestration





3-Step Core Loop:





Discovery & Harvest: Ingestion from public boards into structured local SQLite cache.



LLM Affinity Scoring: Cosine embedding calculation combined with LLM reasoning against candidate criteria.



Package Compilation: Automated XeLaTeX / Tectonic generation of tailored candidate dossiers.



High-Level KPIs: Discovered postings, average affinity score, active pipeline nodes, offers under review.



Priority Triage Queue: Action-oriented recommendations (e.g. "Dispatch tailored Stripe dossier", "Prepare for Figma Round 3").



Yield Funnel & Interview Milestones: Conversion breakdown from scraped leads to formal offer.



Live Terminal Dock: Embedded interactive PTY terminal streaming real-time stdout logs.

4.2 Job Matches — AI Evaluation & Customization





Tab Filtering: Best Matches (≥88%), All Evaluated, Applied, Filtered Out.



Rich Post Cards: Compensation bands, remote status, crawl timestamps, stack overlap tags, and synthesized AI rationale.



One-Click Actions: Build Package [B], I Applied [A], Hide.



Manual Package Builder Drawer: Allows forcing tailored compilation for any role with custom LLM prompt steering.

4.3 Applications Pipeline — Interview Kanban & Debrief





Lifecycle Columns: Ready to Apply → Applied / Submitted → Recruiter Screen → System Design / Deep Dive → Offer.



Interactive Inspection Drawer:





Complete interview loop verification with feedback logs and meeting links.



Attached submission artifacts (cv_v2.pdf, cover_letter.pdf).



Target salary compensation bands and auto-saved Markdown debrief notes (~/.jobhunter/notes).

4.4 Documents & Packages — LaTeX & Artifact Management





Artifact Bundle Composition: Tailored LaTeX CV (.tex + compiled .pdf), targeted cover letter, and 1-click recruiter cold pitch snippet.



Strict Automated Quality Gates:





Fact Integrity: 100% validated against master CV without hallucinations.



Page Budget: Hard 1.0-page budget constraint.



ATS Affinity: Keyword density and vector similarity score.



Compiler Health: 0 XeLaTeX errors / 0 warnings.



Split-Screen PDF Inspector: Live rendered PDF preview with side-by-side diff against the master resume.

4.5 Actions & CLI — Engine Operations





Stage Runners: Execution panels for harvest, score, build-packages, clean-cache, and export.



Parameter Controls: Dry-run toggles, concurrency limit sliders, model selectors (Claude 3.5 Sonnet, GPT-4o, Ollama), ID whitelists.



Live Shell Execution: Subprocess manager with SIGKILL worker controls.

4.6 Settings & Configuration — Daemon Tuning





Semantic Filters: Target roles, seniority tiers, compensation minimums, hard negative exclusions.



LLM Engine & Budget Guardrails: API key keyrings, local Ollama endpoints, daily spend caps, strictness temperature.



ATS Crawler Matrix: Source enablement (Greenhouse, Lever, Ashby, Workable, Hacker News), company priority whitelists and blacklists.



LaTeX Template Workspace: Jinja2/LaTeX macros editor with live side-by-side preview.



5. Non-Functional & Technical Requirements





Local-First & Zero Data Exfiltration: Master CV, candidate contact details, and credentials remain on local storage (~/.config/jobhunter/).



Speed & Ergonomics: Full keyboard navigation support (e.g., ⌘K, J/K navigation, ⌘1-⌘3 workflow triggers).



Reproducible LaTeX Builds: Integrated with xelatex and tectonic for reproducible, sub-second single-page PDF generation.



Desktop Native Responsive Design: Tailored for 1440px+ desktop developer workflows.