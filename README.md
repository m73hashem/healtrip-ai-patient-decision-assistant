# HealTrip AI Patient Decision Assistant

A small full-stack prototype focused on engineering decisions rather than visual polish.

## Stack
- Frontend: React + Vite + TypeScript
- Backend: Python + FastAPI
- Database: PostgreSQL + SQLAlchemy
- AI: SovereignEG OpenAI-compatible Chat Completions API with function tools
- Local orchestration: Docker Compose

The backend uses the OpenAI Python client configured with SovereignEG's `https://backend.sovereigneg.com/v1` endpoint. Chat Completions provides function tool calls; the model requests tools, while the backend validates arguments and owns tool execution.

## Architecture

```text
React chat
   |
   | POST /api/v1/chat
   v
FastAPI
   |
   +-- small emergency phrase guard + agent instructions
   |
   +-- SovereignEG Chat Completions API
   |       |
   |       +--> search_doctors() ----+
   |       +--> search_hospitals() --+--> SQLAlchemy --> PostgreSQL
   |                                  |
   +<---------------------------------+
   |
   +--> structured API response
```

## Agent design

The LLM produces a short explanation and structured action. It cannot query SQL and is not the source of provider records. It can request two application-owned tools:

1. `search_doctors(specialty, city, limit)`
2. `search_hospitals(city, emergency_available, limit)`

The backend validates tool arguments with small Pydantic schemas, executes fixed SQLAlchemy queries against PostgreSQL, and returns results to the model as Chat Completions tool messages with role `tool` and the matching `tool_call_id`. The preceding assistant message contains the requested `tool_calls`. Invalid arguments and tool query exceptions are returned to the model as controlled tool errors so it can respond or recover.

The final model response uses a strict structured JSON schema with `message` and `action`; the backend maps an invalid action or malformed response to `CLARIFY`.

### Anti-hallucination strategy

PostgreSQL is the source of provider records. The backend constructs structured recommendations only from successful tool results, and the frontend renders those records separately under “Database-backed recommendations.” The LLM-generated explanation is instructed to discuss provider categories generically and not include provider names; provider identities are not taken from its prose. This is a prototype-level prompt boundary, not a guarantee that generated text can never contain a name, so the structured recommendation section is the trusted source for displayed provider options.

## Safety / medical boundary

This is not a clinical decision-support system or clinical triage engine. A small deterministic phrase guard runs before the model/provider search for a limited set of obvious prototype examples (such as chest pain, severe breathing difficulty, fainting, and signs of stroke) and returns urgent/emergency guidance without searching providers. It is intentionally incomplete, may miss emergencies or trigger on context such as negation, and does not diagnose. Other safety behavior still depends on the model prompt. Do not use it for real medical decisions.

## Error handling

- Invalid request/history: FastAPI/Pydantic validation, including allowed history roles and bounded content.
- Invalid tool name/arguments: backend rejects execution and returns a controlled tool error to the model.
- Tool query exceptions are caught in the agent and returned to the model as controlled tool errors. Failures that escape request handling, including some database/API failures, may return HTTP 502.
- Empty database search: tool returns an empty list; the model is instructed to report that no match was found. Structured recommendations remain empty.
- Tool calls are capped by the application loop to avoid runaway execution.

## Security considerations

- API key stays server-side.
- Frontend never receives database credentials.
- User input is length-limited.
- ORM queries avoid string-built SQL.
- Production should add authentication, rate limiting, audit logging, secret management, encryption, and a privacy/retention policy for any real patient data.
- Real PHI should not be sent to a third-party model without an appropriate privacy/compliance review and contractual setup.

## Database

```text
specialties
  id PK
  name_en
  name_ar

hospitals
  id PK
  name_en
  name_ar
  city
  country
  emergency_available

doctors
  id PK
  name_en
  name_ar
  specialty_id FK -> specialties.id
  hospital_id FK -> hospitals.id
  languages
  years_experience
  available
```

## API

`GET /health`

`POST /api/v1/chat`

Request:
```json
{
  "message": "I have chest pain and I am not sure what to do.",
  "history": []
}
```

Response:
```json
{
  "message": "...",
  "action": "ER",
  "recommendations": [],
  "tool_calls": []
}
```

Allowed actions are `ER`, `URGENT_CARE`, `SPECIALIST`, `SECOND_OPINION`, `SELF_CARE`, and `CLARIFY`.

## Run locally

1. Copy the project-root `.env.example` to project-root `.env`, then set `OPENAI_API_KEY` to your SovereignEG API key. `OPENAI_MODEL` defaults to `gpt-5.5` and can be changed in the same file. Alternatively, export these variables in your shell before starting Compose.
2. Run `docker compose up --build`.
3. Open `http://localhost:5173`.
4. Backend health: `http://localhost:8000/health`.

Compose reads `OPENAI_API_KEY` and `OPENAI_MODEL` from the shell or project-root `.env`. It supplies the database URL and frontend CORS origin in `docker-compose.yml`.

Without an API key the UI still runs; the backend returns a simple fallback and the deterministic emergency phrase guard remains active.

## Deploy a Render demo

The root `render.yaml` defines three services: a static React/Vite frontend, the FastAPI Docker web service, and PostgreSQL. The frontend calls the backend over HTTPS using `VITE_API_BASE_URL`; Render supplies the backend's public URL through a Blueprint service reference. The backend receives its PostgreSQL connection string from the Render database and calls SovereignEG directly. `CORS_ORIGIN` is wired to the frontend's Render URL through a service reference.

Create the Blueprint from this repository and provide `OPENAI_API_KEY` when Render prompts for it (or set it in the backend service's environment settings). `OPENAI_MODEL` defaults to `gpt-5.5`. Keep the provider key on the backend; no secret belongs in a `VITE_*` variable. Local development remains unchanged: without `VITE_API_BASE_URL`, the browser uses `http://localhost:8000`, while Compose continues to allow `http://localhost:5173` for CORS.

This Free deployment is for evaluation and prototype demonstrations, not production or real patient data. Render Free web services spin down after 15 minutes without traffic, so the first request after idle can take about a minute to start. Free PostgreSQL is limited to 1 GB and expires 30 days after creation; arrange any needed export before expiry. Free services can also restart, and the web service filesystem is ephemeral. See [Render's Free instance limits](https://render.com/docs/free).

## Tests and production build

Run these commands from the project root. The backend runtime image copies `backend/app` but does not include `backend/tests`, so the test command mounts the backend source read-only into a temporary container:

```sh
docker compose run --rm --no-deps \
  -v "$PWD/backend:/app:ro" \
  backend python -m pytest -q -p no:cacheprovider tests
```

The current suite reports `8 passed`.

Build the frontend inside the running Docker frontend container; host npm is not required:

```sh
docker compose exec frontend sh -c 'npm install && npm run build'
```

This runs the package install and the TypeScript plus Vite production build. The build output is written to `frontend/dist/`.

## What I would change for production

- Move triage rules into a versioned, clinician-reviewed policy service.
- Store conversations with explicit consent and retention controls, or keep them ephemeral.
- Keep provider identities in structured database-backed recommendations, separate from generated prose.
- Add authentication, observability, rate limiting, retries/circuit breakers, migrations (Alembic), and automated evaluation of safety/tool-grounding cases.
- Add test cases for emergency symptoms, ambiguous symptoms, unavailable specialties, empty searches, prompt injection, and provider hallucination attempts.
