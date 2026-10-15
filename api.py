import os
import sys

# Force offline mode for HuggingFace embeddings to prevent slow network retry hangs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from contextlib import asynccontextmanager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Security, Header
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from RAG import (
    build_vector_store,
    build_hybrid_retriever,
    rag_answer,
    load_chat_history,
    clear_chat_history,
    list_sessions,
    list_documents,
    delete_document,
    load_config,
    SUPPORTED_LOADERS,
)

# ─────────────────────────────────────────────────────────────
# Shared application state
# ─────────────────────────────────────────────────────────────
app_state: dict = {}

# ─────────────────────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────────────────────
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    expected_key = os.getenv("API_SECRET_KEY", "my-super-secret-key-123")
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key


def _reload_index(config: dict) -> None:
    """Re-build vector store + hybrid retriever and update app_state."""
    data_folder = config["paths"]["data_folder"]
    os.makedirs(data_folder, exist_ok=True)
    vector_store, split_docs = build_vector_store(data_folder, config)
    if vector_store is not None and split_docs:
        retriever = build_hybrid_retriever(vector_store, split_docs, config)
    else:
        retriever = None
    app_state["vector_store"] = vector_store
    app_state["split_docs"]   = split_docs
    app_state["retriever"]    = retriever


import threading

index_ready_event = threading.Event()

def _load_index_worker(config: dict):
    try:
        _reload_index(config)
        print("[OK] Vector store and retriever loaded successfully.")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        app_state["index_error"] = err
        print(f"[ERROR] Background index loading failed:\n{err}")
    finally:
        index_ready_event.set()


# ─────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    app_state["config"] = config
    # Start background loader thread so Uvicorn binds to $PORT immediately
    # Railway health check passes in milliseconds instead of timing out
    loader_thread = threading.Thread(target=_load_index_worker, args=(config,), daemon=True)
    loader_thread.start()
    yield
    app_state.clear()


# ─────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAG API",
    description=(
        "A production-ready Retrieval-Augmented Generation API.\n\n"
        "**Features:** Hybrid Search (BM25 + Semantic), Multi-Session Memory, "
        "Document Management, and a fully configurable pipeline."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    query: str
    session_id: str = "default"
    user_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    session_id: str


def get_storage_session_id(session_id: str, user_id: str | None = None) -> str:
    """Namespace session IDs per user so users only access their own history."""
    if user_id and user_id.strip():
        return f"{user_id.strip()}:{session_id}"
    return session_id


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

# ── Health & Root ─────────────────────────────────────────────
@app.get("/", tags=["System"])
def root():
    """Root endpoint for Railway health monitoring."""
    return {"status": "ok", "message": "RAG Assistant API is online"}


@app.get("/health", tags=["System"])
def health_check():
    """Check whether the API is running and the index is loaded."""
    docs = list_documents(app_state.get("config"))
    return {
        "status": "ok",
        "vector_store_ready": app_state.get("vector_store") is not None,
        "indexed_documents": len(docs),
        "documents": docs,
        "index_error": app_state.get("index_error"),
    }


# ── Ask ───────────────────────────────────────────────────────
@app.post("/ask", response_model=AskResponse, tags=["Chat"])
def ask(
    req: AskRequest,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    api_key: str = Depends(get_api_key),
):
    """
    Ask a question against the indexed documents.

    - **query**: your question
    - **session_id**: unique identifier for the conversation session (default: `"default"`)
    - **user_id**: optional unique identifier for the user (to isolate history per user)
    """
    # Wait for the background index loader if still initializing (up to 25s)
    if app_state.get("retriever") is None:
        index_ready_event.wait(timeout=25)

    retriever = app_state.get("retriever")
    if retriever is None:
        raise HTTPException(
            status_code=503,
            detail="The assistant is still initializing its knowledge base. Please try again in a few seconds.",
        )
    effective_user_id = req.user_id or x_user_id
    storage_sid = get_storage_session_id(req.session_id, effective_user_id)
    try:
        answer = rag_answer(retriever, req.query, storage_sid, app_state["config"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return AskResponse(answer=answer, session_id=req.session_id)


# ── Upload ────────────────────────────────────────────────────
@app.post("/upload", tags=["Documents"])
async def upload_document(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    """
    Upload a new document (.pdf, .txt, .csv, .docx) to the knowledge base.
    The document is indexed immediately after upload.
    """
    config = app_state.get("config") or load_config()
    ext    = os.path.splitext(file.filename)[1].lower()

    if ext not in SUPPORTED_LOADERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {list(SUPPORTED_LOADERS.keys())}",
        )

    data_folder = config["paths"]["data_folder"]
    os.makedirs(data_folder, exist_ok=True)
    file_path = os.path.join(data_folder, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        _reload_index(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File saved but indexing failed: {e}")

    return {"message": f"'{file.filename}' uploaded and indexed successfully."}


# ── List Documents ────────────────────────────────────────────
@app.get("/documents", tags=["Documents"])
def get_documents():
    """List all currently indexed documents."""
    docs = list_documents(app_state.get("config"))
    return {"documents": docs, "count": len(docs)}


# ── Delete Document ───────────────────────────────────────────
@app.delete("/documents/{filename}", tags=["Documents"])
def remove_document(filename: str, api_key: str = Depends(get_api_key)):
    """
    Delete a document from the knowledge base and rebuild the index.
    """
    config      = app_state.get("config") or load_config()
    data_folder = config["paths"]["data_folder"]

    success = delete_document(filename, data_folder, config)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")

    try:
        _reload_index(config)
    except Exception as e:
        return {"message": f"Document deleted but index rebuild failed: {e}"}

    return {"message": f"'{filename}' deleted and index rebuilt successfully."}


# ── Chat History ──────────────────────────────────────────────
@app.get("/history/{session_id}", tags=["Sessions"])
def get_history(
    session_id: str,
    user_id: str | None = None,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    api_key: str = Depends(get_api_key),
):
    """Retrieve the full chat history for a session from PostgreSQL, scoped by user_id."""
    effective_user_id = user_id or x_user_id
    storage_sid = get_storage_session_id(session_id, effective_user_id)
    history = load_chat_history(storage_sid)
    return {
        "session_id":    session_id,
        "history":       history,
        "message_count": len(history),
    }


@app.delete("/history/{session_id}", tags=["Sessions"])
def delete_history(
    session_id: str,
    user_id: str | None = None,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    api_key: str = Depends(get_api_key),
):
    """Clear the chat history for a session from PostgreSQL, scoped by user_id."""
    effective_user_id = user_id or x_user_id
    storage_sid = get_storage_session_id(session_id, effective_user_id)
    clear_chat_history(storage_sid)
    return {"message": f"Chat history cleared for session '{session_id}'."}


# ── Sessions ──────────────────────────────────────────────────
@app.get("/sessions", tags=["Sessions"])
def get_sessions(
    user_id: str | None = None,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    api_key: str = Depends(get_api_key),
):
    """List all active session IDs from PostgreSQL, filtered by user_id if provided."""
    effective_user_id = user_id or x_user_id
    sessions = list_sessions(user_id=effective_user_id)
    return {"sessions": sessions, "count": len(sessions)}

