# Vendor AI Tracker

A multi-user web application to collect, store, and query vendor information using AI-powered search and a conversational chatbot interface.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend / UI** | [Streamlit](https://streamlit.io) | Web app framework — chat UI, forms, tables |
| **LLM (AI answers)** | [Groq](https://console.groq.com) + `llama-3.1-8b-instant` | Generates natural language answers from vendor context |
| **Embeddings** | [Sentence Transformers](https://www.sbert.net) — `all-MiniLM-L6-v2` | Converts vendor text into 384-dimensional vectors for semantic search |
| **Vector Search (cloud)** | [pgvector](https://github.com/pgvector/pgvector) on Supabase | Finds semantically similar vendors using cosine distance |
| **Vector Search (local)** | NumPy cosine similarity | Fallback when Supabase is unavailable |
| **Database (cloud)** | [Supabase](https://supabase.com) — PostgreSQL | Shared cloud database for multi-user data |
| **Database (local)** | SQLite | Local fallback for single-machine development |
| **Config / Secrets** | `python-dotenv` + Streamlit Secrets | Manages API keys and connection strings |
| **Data Import** | pandas + openpyxl | Reads CSV and Excel files for bulk vendor upload |
| **Deployment** | [Streamlit Cloud](https://share.streamlit.io) | Free public hosting |

---

## Project Structure

```
vendor-ai-tracker/
├── app.py                  # Main chatbot page
├── pages/
│   └── submit.py           # Public vendor submission form
├── services/
│   ├── db_service.py       # Database layer (Postgres + SQLite)
│   ├── embedding_service.py# Text → vector conversion
│   ├── retrieval_service.py# Semantic search + LLM answer generation
│   └── llm_service.py      # Groq API wrapper
├── .streamlit/
│   ├── config.toml         # Theme and server settings
│   └── secrets.toml        # Local secrets (gitignored)
├── db/
│   └── vendor_ai_tracker.db# SQLite file (local fallback)
├── requirements.txt
├── secrets.toml.example    # Template for secrets setup
└── .env                    # Local environment variables (gitignored)
```

---

## End-to-End Flow

### 1. Vendor Submission (three ways)

```
User (browser)
    │
    ├─ Chat: "add vendor"      ──► app.py collects name, phone,
    │                               company, rate step-by-step
    │
    ├─ Submit Form (/submit)   ──► pages/submit.py — web form with
    │                               Name, Company, Phone, Email,
    │                               Rate, Category, Location, Notes
    │
    └─ Bulk Upload (sidebar)   ──► Upload CSV or Excel →
                                    ALL columns read automatically →
                                    no column mapping needed
```

### 2. Saving a Vendor

```
save_vendor(fields: dict)          ← any key-value pairs from the form/file
    │
    ├─ Supabase available?
    │       YES → INSERT INTO vendors (fields JSONB) on PostgreSQL
    │       NO  → INSERT INTO vendors (fields TEXT/JSON) on SQLite
    │
    └─ Returns vendor_id
```

### 3. Indexing for AI Search

```
retrieval.index_vendor(vendor_id, fields)
    │
    ├─ Build text: "name: Acme, phone: 555-0001, rate: $50/hr, ..."
    │
    ├─ EmbeddingService.embed_text(text)
    │       └─ SentenceTransformer (all-MiniLM-L6-v2)
    │               └─ Returns 384-dimensional float vector
    │
    └─ update_embedding(vendor_id, vector)
            ├─ Supabase: UPDATE vendors SET embedding = vector(384)
            └─ SQLite:   UPDATE vendors SET embedding = JSON text
```

### 4. AI Question Answering

```
User types: "Who has the lowest rate?"
    │
    ├─ EmbeddingService.embed_text(query)
    │       └─ Query → 384-dim vector
    │
    ├─ search_by_vector(query_vector, top_k=5)
    │       ├─ Supabase: embedding <=> query_vector  (pgvector cosine distance)
    │       └─ SQLite:   cosine_similarity() in Python (NumPy)
    │               └─ Returns top 5 most relevant vendors
    │
    ├─ Build context string from matched vendor fields
    │
    └─ llm_service.generate(prompt, system)
            └─ Groq API (llama-3.1-8b-instant)
                    └─ Returns natural language answer
```

### 5. Database Backend Auto-detection

```
App starts
    │
    └─ _detect_backend()
            │
            ├─ DATABASE_URL set?
            │       YES → Try connecting to PostgreSQL (5s timeout)
            │               Success → backend = "pg"  (Supabase)
            │               Fail    → backend = "sqlite"
            │
            └─ DATABASE_URL not set → backend = "sqlite"

backend is cached for the lifetime of the process.
If SQLite is active, a warning banner is shown in the UI.
```

---

## Database Schema

```sql
-- vendors table (same structure on both backends)

-- PostgreSQL (Supabase)
CREATE TABLE vendors (
    id         SERIAL PRIMARY KEY,
    fields     JSONB NOT NULL DEFAULT '{}',   -- all vendor data, any keys
    embedding  vector(384),                   -- pgvector for semantic search
    created_at TIMESTAMP DEFAULT NOW()
);

-- SQLite (local fallback)
CREATE TABLE vendors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fields     TEXT NOT NULL DEFAULT '{}',    -- JSON string
    embedding  TEXT,                          -- JSON array string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The `fields` column stores any key-value pairs as JSON — no schema change is needed when a new Excel file has different columns.

---

## Configuration

### Local development — `.env`

```env
DATABASE_URL=postgresql://...   # Supabase connection string
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
DB_PATH=db/vendor_ai_tracker.db # SQLite path (fallback)
```

### Streamlit Cloud — Secrets UI

```toml
DATABASE_URL = "postgresql://..."
GROQ_API_KEY = "gsk_..."
GROQ_MODEL   = "llama-3.1-8b-instant"
```

---

## Multi-user Architecture

```
Person 1 (browser) ──┐
Person 2 (browser) ──┼──► Streamlit Cloud app ──► Supabase PostgreSQL
Person 3 (browser) ──┘                             (single shared DB)
```

All users write to and read from the same Supabase database.
The SQLite fallback is **single-machine only** and is not suitable for multiple users.

---

## Running Locally

```bash
# 1. Install dependencies
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt

# 2. Configure environment
cp secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your keys

# 3. Run
streamlit run app.py
```

Open http://localhost:8501

- **Main chatbot**: http://localhost:8501
- **Submit form**:  http://localhost:8501/submit

---

## Deploying to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select repo, branch `main`, main file `app.py`
4. Under **Advanced settings → Secrets**, paste your secrets
5. Click **Deploy**

Share `https://your-app.streamlit.app/submit` with anyone to collect vendor details.

---

## Key Design Decisions

**Dynamic schema (`fields` JSON column)**
All vendor data is stored as a JSON object rather than fixed columns. This means any CSV or Excel file can be imported without changing the database schema — a file with 3 columns and a file with 15 columns both work the same way.

**Dual database backend**
The app automatically uses Supabase when available and falls back to SQLite. This means development works without any cloud setup, and production works without any code change.

**Semantic search over keyword search**
Vendor text is converted to vector embeddings at save time. At query time, the user's question is also embedded and compared by cosine similarity. This means "cheap vendor" will match a vendor with rate "$30/hr" even if the word "cheap" never appears in the data.
