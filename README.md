# Waypoint Backend

Waypoint Backend is the API and AI grounding layer for an interstate relocation product. It serves structured state data, deterministic relocation intelligence, cost estimates, move plans, local exploration data, service contacts, emergency contacts, and a grounded AI assistant.

This repository is designed to make the frontend feel live, useful, and judge-ready while keeping the data model simple enough to understand quickly.

## Why It Stands Out

- Complete relocation API: comparison, cost, plans, AI chat, exploration, services, emergency contacts, cities, and safety endpoints.
- Grounded AI assistant: OpenAI responses are constrained by structured context from the selected corridor and states explicitly mentioned in the prompt.
- Dynamic prompt handling: if a user asks about California vs Texas while the UI is on Wyoming, the API detects the named states and gives the model the right context instead of refusing.
- Deterministic data generation: stable derived metrics make demos repeatable while still feeling rich across all 50 states.
- MongoDB-backed source of truth: state data is seeded into MongoDB and served through FastAPI.
- Demo resilience: health checks, auto-seeding, typed request models, normalized exceptions, and explicit disclaimers.

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- Motor / PyMongo
- MongoDB or MongoDB Atlas
- OpenAI API
- python-dotenv

## API Surface

All routes are under `/api/v1`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service, database, and OpenAI readiness |
| `GET` | `/states` | List state codes and names |
| `GET` | `/states/{code}` | Full state profile |
| `GET` | `/compare` | Area profile for destination state/city/area |
| `GET` | `/compare/rules` | State-to-state relocation rule differences |
| `POST` | `/chat` | Grounded AI assistant answer with sources |
| `GET` | `/chat/suggestions` | Suggested assistant prompts |
| `POST` | `/plan` | Personalized move checklist |
| `POST` | `/cost` | Tax and cost-of-living estimate |
| `GET` | `/cities` | City overview for a state |
| `GET` | `/safety` | State and city safety/livability report |
| `GET` | `/explore` | Nearby essentials and map-ready places |
| `GET` | `/services` | Relocation provider groups |
| `GET` | `/emergency` | Emergency and public-service contacts |

FastAPI docs are available at:

```text
http://localhost:8000/docs
```

## Local Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```bash
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=stateshift
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4.1-2025-04-14
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AUTO_SEED=true
LOG_LEVEL=INFO
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Data Model

State source data lives in:

```text
app/data/states.json
```

On startup, if `AUTO_SEED=true` and the MongoDB `states` collection is empty, the backend loads that JSON into MongoDB. The domain layer then derives stable profiles for area fit, cost, safety, exploration places, services, contacts, and plan tasks.

## AI Grounding Strategy

The assistant flow is intentionally simple and explainable:

1. `/chat` receives the user question plus selected corridor context.
2. The backend loads state documents from MongoDB.
3. It detects any US states explicitly named in the question.
4. It builds a concise context block with the selected corridor and the named states.
5. The OpenAI call answers in Markdown with practical relocation guidance.
6. Source links are selected based on the question category.

This prevents a common demo failure: the assistant should not say "I can only help with Wyoming" when the user explicitly asks to compare California and Texas.

## Key Files

```text
app/main.py                 FastAPI app, lifecycle, CORS, exception handling
app/config.py               Environment settings
app/db.py                   MongoDB client and collection access
app/llm.py                  OpenAI wrapper and system prompt
app/domain/dataset.py       Deterministic relocation domain logic
app/api/v1/*.py             Versioned API routes
app/scripts/ingest.py       MongoDB seed script
app/data/states.json        50-state source data
```

## Manual Verification

Compile check:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/waypoint-backend-pycache python3 -m compileall app
```

Seed manually:

```bash
python3 -m app.scripts.ingest
```

Example requests:

```bash
curl "http://localhost:8000/api/v1/compare?state=TX&city=Austin&area=Mueller"

curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"Compare California and Texas please","fromState":"CA","toState":"WY","city":"Jackson"}'

curl -X POST "http://localhost:8000/api/v1/cost" \
  -H "Content-Type: application/json" \
  -d '{"fromState":"CA","toState":"TX","salary":120000,"filing":"single","housing":"rent"}'
```

## Frontend Pairing

Run the frontend from the sibling repository:

```bash
cd ../State-frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Product and Compliance Notes

Waypoint provides general relocation information only. Laws, taxes, costs, deadlines, and local rules can change by city, county, and state. Users should verify important decisions with official sources or qualified professionals.
