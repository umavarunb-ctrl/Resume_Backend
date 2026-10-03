# Recruiter Resume Search Platform - Backend API

Production-ready backend API service for recruiter-facing resume search, candidate management, and semantic indexing.

## Current Phase: Phase 1 — Backend Foundation

This initial release establishes the clean, modular backend foundation:
- Python 3.10.2 compatible modular architecture
- FastAPI application lifecycle management (`lifespan`)
- Pydantic Settings loaded from `.env`
- Centralized MongoDB Atlas connection manager with health ping verification
- PyJWT and Bcrypt password hashing security foundations
- PDF upload and selectable-text extraction via PyMuPDF
- Deterministic section-aware resume parsing engine (no LLM required)
- 384-dimensional dense vector embeddings via sentence-transformers (`all-MiniLM-L6-v2`)
- Automated Pytest test suite with 36 test cases

---

## Architecture

### Planned System Architecture

```text
                    Recruiter Frontend
                           │
                           ▼
                    FastAPI Backend
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
        Authentication   Search       Resume Upload
             │             │             │
             │             │             ▼
             │             │        PDF Extraction
             │             │             │
             │             │             ▼
             │             │        Resume Parsing
             │             │             │
             │             ▼             ▼
             │       Hybrid Search    Embeddings
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                     MongoDB Atlas
                           │
                  Atlas Vector Search
                           │
                           ▼
                    Object Storage
```

---

## Project Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point, CORS, lifespan
│   ├── core/                    # Core infrastructure & configuration
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic BaseSettings (.env loader)
│   │   ├── database.py          # MongoDB Atlas lifecycle & health ping
│   │   ├── security.py          # Bcrypt hashing & PyJWT token utilities
│   │   └── logging.py           # Structured application logging
│   ├── api/                     # API presentation layer
│   │   ├── __init__.py
│   │   ├── dependencies.py      # FastAPI DI (DB, settings, pagination)
│   │   └── routes/              # Routers for all modules
│   │       ├── __init__.py
│   │       ├── health.py        # /api/health & /api/health/database
│   │       ├── auth.py          # (Placeholder)
│   │       ├── candidates.py    # (Placeholder)
│   │       ├── search.py        # (Placeholder)
│   │       ├── uploads.py       # (Placeholder)
│   │       └── users.py         # (Placeholder)
│   ├── models/                  # MongoDB document model declarations (Placeholder)
│   ├── schemas/                 # Pydantic validation & response schemas
│   │   ├── __init__.py
│   │   └── health.py            # Health endpoint schemas
│   ├── services/                # Business logic services (Placeholder)
│   ├── repositories/            # Direct database access repositories (Placeholder)
│   └── utils/                   # Shared utility helpers (pagination, text, validation)
├── tests/                       # Automated test suite
│   ├── __init__.py
│   ├── test_health.py
│   └── test_database.py
├── .env.example                 # Sample configuration template
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Requirements

- **Python**: `3.10.2`
- **Database**: MongoDB Atlas cluster

---

## Setup Instructions

### 1. Create and Activate Virtual Environment (Windows CMD)

```cmd
py -3.10 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the template to create your local `.env`:

```cmd
copy .env.example .env
```

Edit `.env` to configure your MongoDB Atlas URI and a strong JWT secret:
- `MONGODB_URI`: Your MongoDB Atlas connection string (e.g., `mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority`)
- `JWT_SECRET`: A secure, randomly generated 256-bit secret key

*Never commit `.env` or hard-code credentials into version control.*

---

## Running the Application

Activate the virtual environment and start the development server:

```cmd
venv\Scripts\activate
uvicorn app.main:app --reload
```

The server will start at `http://127.0.0.1:8000`.

---

## API Endpoints & Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Returns service health status and API version |
| `GET` | `/api/health/database` | Verifies active MongoDB Atlas connection |
| `POST` | `/api/auth/register` | Register new recruiter account |
| `POST` | `/api/auth/login` | Authenticate and obtain JWT access token |
| `GET` | `/api/users/me` | Fetch authenticated recruiter profile |
| `POST` | `/api/uploads/resume` | Upload PDF resume and extract selectable text (Open for testing) |
| `GET` | `/api/uploads/{file_id}` | Retrieve resume upload metadata and full extracted text (Open for testing) |
| `GET` | `/api/uploads` | List uploaded resumes (paginated, open for testing) |
| `POST` | `/api/candidates/parse/{upload_id}` | Parse uploaded resume into structured candidate profile |
| `POST` | `/api/candidates` | Create candidate profile directly |
| `GET` | `/api/candidates` | List candidates with skills filtering and keyword search |
| `GET` | `/api/candidates/{candidate_id}` | Retrieve full candidate profile |
| `DELETE` | `/api/candidates/{candidate_id}` | Delete candidate profile |
| `POST` | `/api/search/semantic` | Natural language semantic vector search |
| `POST` | `/api/search/hybrid` | Hybrid search (semantic vectors + hard skills & experience filters) |
| `GET` | `/docs` | Interactive Swagger UI API documentation |
| `GET` | `/redoc` | Interactive ReDoc API documentation |

---

## MongoDB Atlas Vector Search Index Configuration

To enable hardware-accelerated `$vectorSearch` directly within your MongoDB Atlas cluster:

1. Open your MongoDB Atlas Dashboard -> **Atlas Search / Vector Search**.
2. Select your database (`resume_ramcharan`) and collection (`candidates`).
3. Click **Create Index** -> **JSON Editor**.
4. Set index name to: `vector_index`
5. Paste the definition below:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

*(Note: If the Atlas vector index is not yet created, the API automatically falls back to vectorized cosine similarity calculation in Python, ensuring zero downtime.)*

### Example Health Response:

```json
{
  "status": "healthy",
  "service": "Recruiter Resume Search API",
  "version": "1.0.0"
}
```

### Example Database Health Response (Connected):

```json
{
  "status": "healthy",
  "database": "connected"
}
```

*(If MongoDB is not reachable or unconfigured, `/api/health/database` returns HTTP 503 with `"database": "disconnected"`.)*

---

## Running Tests

Execute the test suite using `pytest`:

```cmd
pytest
```

---

## Docker Deployment

To build and run the containerized application:

```cmd
docker build -t recruiter-resume-api .
docker run -p 8000:8000 --env-file .env recruiter-resume-api
```
