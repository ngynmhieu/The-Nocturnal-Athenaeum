# The Nocturnal Athenaeum

## Rule 1 — Read the module docs before doing anything else

**If you have no context of this project, you must read the relevant module's documentation before making any change or investigating any issue.** Do not start editing, and do not start grepping the codebase blind.

Documentation is **not** in a single root `/docs` folder. Every module owns a `docs/` folder:

```
<module>/docs/
├── <module>_guidelines.md    # architecture + conventions for the whole module
└── modules/
    └── <feature>.md          # one doc per feature (auth, chat, read, llm, ...)
```

The required first step, in order:

1. Identify which module(s) the task touches — `frontend`, `backend`, `models`, or `supabase`.
2. Read that module's top-level guideline (`<module>/docs/<module>_guidelines.md`).
3. Read the per-feature doc for the feature involved (`<module>/docs/modules/<feature>.md`).
4. Only then read code, propose a plan, or make changes.

If a change spans modules (most features do — a new feature usually touches all four), read the matching doc in **each** affected module. The same feature name appears across modules deliberately: `auth`, `chat`, and `read` each have a frontend doc, a backend doc, and a supabase doc describing their own slice of it.

These docs define the intended architecture. When code and docs disagree, raise it rather than silently following either one.

### Documentation map

| Module | Guideline | Feature docs |
|---|---|---|
| `frontend` | [frontend_guidelines.md](../frontend/docs/frontend_guidelines.md), [styling_guidelines.md](../frontend/docs/styling_guidelines.md) | `auth`, `chat`, `read` |
| `backend` | [backend_guidelines.md](../backend/docs/backend_guidelines.md) | `auth`, `chat`, `read` |
| `models` | [models_guideline.md](../models/docs/models_guideline.md) | `llm` |
| `supabase` | [supabase_guidelines.md](../supabase/docs/supabase_guidelines.md) | `auth`, `chat`, `read` |

---

## The four modules

The project is split into four top-level modules. Each is independently runnable or deployable, and each is organized **by feature (vertical slices)**, never by technical layer.

### `frontend/` — the user interface

React + TypeScript + Vite + Tailwind, launched via `frontend/run_frontend.bat` (or `run_all.bat`).

A **modular monolith** using **Feature-Sliced Design** inside each module: pages compose, features hold user actions, entities hold business concepts, and `shared/` holds cross-cutting primitives that must never depend on business modules. Cross-module imports go through a module's public API (`index.ts`) — never deep into its folders.

Styling is strict: all colors are CSS variables defined in `index.css`, and sizing uses proportional units (`rem`, `%`, `vh`) rather than fixed pixels.

### `backend/` — the application API

FastAPI **modular monolith**, launched via `backend/run_backend.bat` (or `run_all.bat`).

Organized feature-first to mirror the frontend. Each feature under `app/modules/` owns its full stack in one flat folder — `router.py` (thin HTTP layer), `service.py` (business logic), `schemas.py` (API shapes), `models.py` (persistence shapes), `dependencies.py` (the module's public surface). `app/core/` holds infrastructure (config, database, security); `app/shared/` holds reusable business-agnostic code.

The backend holds no model in-process — it calls the models service over HTTP.

### `models/` — the model-serving service

A **standalone service** that stores, loads, and runs models, exposing an **OpenAI-compatible HTTP API**. Launched via `models/run_models.bat` (or `run_all.bat`).

It exists as a separate process because a model and an application have opposite lifecycles: loading weights takes minutes, restarting the backend takes seconds. Keeping them apart means the backend can restart freely while the model stays warm.

Two design principles govern it:

- **A module is a model type.** Today there is one: `llm`. A future embedding/vision/ASR type becomes its own module.
- **A model is data; the module is the code.** Parameter differences go in a JSON config; behavior differences go in the module. Adding another chat model is a JSON file and zero code.

### `supabase/` — the database schema source of truth

Not a running service. A config-and-migrations folder for the **cloud** Postgres + Auth instance, managed by the Supabase CLI.

- `schema/` — authored source of truth, organized by module (`auth/`, `chat/`, `read/`). This is the *intent*.
- `migrations/` — ordered, timestamped SQL that has been applied. This is the *history*.
- `scripts/` — `gen_migration.py` and `sync_schema.py`, which drive change detection against `schema/.snapshots/`.

This project uses the CLI in **remote-only mode**. All schema changes go to the cloud via `db push`. **Never install Docker or run `supabase start`.**

---

## Working conventions

- **Never widen a module's scope to avoid reading its docs.** The docs are short; read them.
- Match the surrounding code's naming, comment density, and idiom.
- A feature added to one module usually needs a matching change in the others — check all four before calling a feature done.
- Secrets live in `.env` files per module and are gitignored. Never commit them, and never paste their contents into output.
