# HERMES — AI Documentation Intelligence Platform

HERMES is an AI-powered documentation intelligence platform that automatically generates, tests, and maintains technical documentation as software code changes.

## Core Differentiators

1. **Change-Aware Documentation**: Documentation updates are triggered directly by AST structural diffs rather than relying on manual discipline.
2. **Executable Examples**: Supported code examples are extracted and tested in an isolated Python subprocess environment with strict timeouts and output capture.
3. **Bounded Self-Correction**: When an example fails verification, the traceback feeds into a bounded self-correction loop (max 2 attempts) to attempt automated repair before human review.
4. **Source-Grounded Claims**: Generated technical specifications cite exact source files, classes, methods, and line ranges (`[data_pipeline.py#L32-L78]`).
5. **Reviewable Automation**: Prepares unified diffs and stages GitHub pull requests with structured checklists.

---

## Architecture & Technology Stack

- **Frontend**: Semantic HTML5, CSS3 with institutional design system (`#F7F7F4` porcelain, `#292D2A` graphite, `#78918A` institutional teal-gray, light/dark mode), and modular Vanilla JavaScript.
- **Backend**: Python 3.14 + Flask REST API.
- **AST Parser**: Python built-in `ast` module extracting classes, functions, arguments, type annotations, and docstring coverage debt.
- **Execution Sandbox**: Subprocess execution with resource timeouts, path isolation, and standard error capture.
- **Persistence**: SQLite database (`hermes.db`) storing documents, versions, verification test outcomes, staged pull requests, activity audit logs, and settings.
- **AI Engine**: Hybrid provider architecture supporting Google Gemini 1.5 Flash, OpenAI GPT-4o-mini, and an offline deterministic AST documentation generator that works without any external API keys.

---

## Directory Layout

```
hermes/
├── app.py                     # Flask application server & REST endpoints
├── database.py                # SQLite schema, migrations, seed data & queries
├── requirements.txt           # Python dependencies
├── engine/
│   ├── ast_parser.py          # Python AST structural analysis & debt detection
│   ├── drift_detector.py      # Revision comparison & signature drift detection
│   ├── doc_generator.py       # Source-grounded Markdown generator (AI & Offline)
│   ├── verifier.py            # Code snippet extraction & isolated execution
│   ├── correction_loop.py     # Bounded error-traceback correction loop
│   └── git_simulator.py       # Unified diff generator & PR staging
├── sample_files/
│   ├── data_pipeline.py       # Stream processing pipeline sample
│   ├── auth_service.py        # HMAC token management sample
│   └── cache_client.py        # Memory cache with TTL sample
├── static/
│   ├── css/
│   │   └── hermes.css         # Institutional styling, grid, typography & themes
│   └── js/
│       └── app.js             # SPA routing, API fetchers, markdown renderer, modal
└── templates/
    └── index.html             # Public website & Authenticated workspace UI
```

---

## Getting Started

### 1. Launch the Server

Run the Flask server with Python:

```powershell
python app.py
```

The application will start on `http://127.0.0.1:5000`.

### 2. Available Endpoints

- `GET /` — Unified web application (Public Website & Authenticated Workspace)
- `GET /api/stats` — Real-time metrics from SQLite database
- `GET /api/documents` — Catalog of managed documentation
- `POST /api/analyze` — AST structural parsing of Python source
- `POST /api/verify` — Extract and execute documentation snippets
- `POST /api/correct` — Bounded correction loop on failing snippets
- `POST /api/run-pipeline` — 12-stage end-to-end documentation synchronization
- `POST /api/assistant/chat` — Source-grounded Q&A assistant
- `GET /api/runs` — Verification run execution history
- `GET /api/pull-requests` — Staged pull requests & unified diffs
