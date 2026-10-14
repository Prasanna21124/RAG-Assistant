import os
import sys
import json
import pickle
import shutil
import yaml
import csv
import uuid
import hashlib
from datetime import datetime

# Configure safe UTF-8 output streams
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Supported file types
# ─────────────────────────────────────────────────────────────
SUPPORTED_LOADERS = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".csv": CSVLoader,
    ".docx": Docx2txtLoader,
}

_SPLIT_DOCS_FILE = "split_docs.pkl"


# ─────────────────────────────────────────────────────────────
# Step 0 — Configuration
# ─────────────────────────────────────────────────────────────
def compute_file_hash(file_path: str) -> str:
    """Compute a SHA-256 hash for a file."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_config(config_path: str = "config.yaml") -> dict:
    """Load config.yaml with sensible defaults for every key."""
    defaults = {
        "llm": {
            "model": "gemini-2.5-flash",
            "temperature": 0.2,
            # "max_tokens": 1024,
        },
        "retrieval": {
            "k": 10,
            "chunk_size": 1500,
            "chunk_overlap": 300,
            "bm25_weight": 0.4,
            "semantic_weight": 0.6,
        },
        "paths": {
            "data_folder": "data/",
            "index_path": "faiss_index/",
            "sessions_dir": "sessions/",
        },
    }
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        for section, values in user_cfg.items():
            if section in defaults and isinstance(values, dict):
                defaults[section].update(values)
            else:
                defaults[section] = values
    return defaults


# ─────────────────────────────────────────────────────────────
# Step 1 — Load Documents
# ─────────────────────────────────────────────────────────────
def load_documents_from_folder(folder_path: str, files_to_load: list = None) -> list:
    """Load specific documents from a folder."""
    if not os.path.exists(folder_path):
        raise FileNotFoundError(
            f"Data folder not found: '{folder_path}'\n"
            f"Please create the folder and add your documents."
        )

    if not files_to_load:
        print(f"⚠ No documents to load.")
        return []

    print(f"\n📂 Loading {len(files_to_load)} document(s):")

    documents = []
    for file in files_to_load:
        file_path = os.path.join(folder_path, file)
        ext = os.path.splitext(file)[1].lower()
        if ext not in SUPPORTED_LOADERS:
            continue
        try:
            if ext in (".txt", ".csv"):
                try:
                    loader = SUPPORTED_LOADERS[ext](file_path, encoding="utf-8")
                    loaded = loader.load()
                except UnicodeDecodeError:
                    loader = SUPPORTED_LOADERS[ext](file_path, encoding="utf-8-sig")
                    loaded = loader.load()
            else:
                loader = SUPPORTED_LOADERS[ext](file_path)
                loaded = loader.load()
            print(f"   ✓ {file}  →  {len(loaded)} item(s) loaded")
            documents.extend(loaded)
        except Exception as e:
            print(f"   ✗ {file}  →  Failed to load: {e}")

    print(f"\n✅ Total pages loaded: {len(documents)}\n")
    return documents


# ─────────────────────────────────────────────────────────────
# Step 2 — Build / Update Vector Store
# ─────────────────────────────────────────────────────────────
def _load_split_docs(index_path: str) -> list:
    pkl = os.path.join(index_path, _SPLIT_DOCS_FILE)
    if os.path.exists(pkl):
        with open(pkl, "rb") as f:
            return pickle.load(f)
    return []


def _save_split_docs(docs: list, index_path: str) -> None:
    os.makedirs(index_path, exist_ok=True)
    with open(os.path.join(index_path, _SPLIT_DOCS_FILE), "wb") as f:
        pickle.dump(docs, f)


def build_vector_store(folder_path: str, config: dict = None) -> tuple:
    """
    Build or incrementally update the FAISS vector store.
    Returns (vector_store, all_split_docs).
    both values may be None / [] if no documents exist yet.
    """
    if config is None:
        config = load_config()

    index_path   = config["paths"]["index_path"]
    chunk_size   = config["retrieval"]["chunk_size"]
    chunk_overlap = config["retrieval"]["chunk_overlap"]

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    metadata_path = os.path.join(index_path, "index_metadata.json")
    index_metadata: dict = {}
    vector_store  = None
    all_split_docs: list = []

    # 1. Load existing index
    if os.path.exists(index_path) and os.path.exists(metadata_path):
        print(f"⚡ Loading existing vector store from '{index_path}'...")
        vector_store = FAISS.load_local(
            folder_path=index_path,
            embeddings=embedding_model,
            allow_dangerous_deserialization=True,
        )
        with open(metadata_path, "r") as f:
            index_metadata = json.load(f)
        all_split_docs = _load_split_docs(index_path)
    elif os.path.exists(index_path) and os.path.exists(os.path.join(index_path, "indexed_files.json")):
        # Clean up old format entirely to rebuild correctly
        print("⚡ Old index format detected. Rebuilding from scratch...")
        import shutil
        shutil.rmtree(index_path)

    # 2. Identify new, modified, and deleted files
    current_files = []
    if os.path.exists(folder_path):
        current_files = [
            f for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in SUPPORTED_LOADERS
        ]

    files_to_index = []
    deleted_files = []
    chunk_ids_to_delete = []

    for f in current_files:
        file_path = os.path.join(folder_path, f)
        file_hash = compute_file_hash(file_path)
        if f not in index_metadata or not index_metadata[f].get("chunk_ids"):
            # NEW or previously unindexed/empty
            files_to_index.append(f)
            index_metadata[f] = {"hash": file_hash, "chunk_ids": []}
        else:
            if index_metadata[f].get("hash") != file_hash:
                # MODIFIED
                files_to_index.append(f)
                chunk_ids_to_delete.extend(index_metadata[f].get("chunk_ids", []))
                deleted_files.append(f)
                index_metadata[f] = {"hash": file_hash, "chunk_ids": []}

    for f in list(index_metadata.keys()):
        if f not in current_files:
            chunk_ids_to_delete.extend(index_metadata[f].get("chunk_ids", []))
            deleted_files.append(f)
            del index_metadata[f]

    if not files_to_index and not chunk_ids_to_delete:
        print("✅ No new, modified, or deleted documents. Vector store is up to date.\n")
        return vector_store, all_split_docs

    # 3. Handle deletions from Vector Store and all_split_docs
    if chunk_ids_to_delete and vector_store is not None:
        print(f"🗑  Deleting {len(chunk_ids_to_delete)} old chunk(s) from vector store.")
        vector_store.delete(chunk_ids_to_delete)
        all_split_docs = [
            doc for doc in all_split_docs
            if os.path.basename(doc.metadata.get("source", "")) not in deleted_files
        ]

    # 4. Find new documents
    new_documents = load_documents_from_folder(folder_path, files_to_load=files_to_index)

    if new_documents:
        # 5. Chunk new documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        new_split_docs = splitter.split_documents(new_documents)
        print(f"🔪 Split into {len(new_split_docs)} chunk(s).")

        all_split_docs.extend(new_split_docs)

        chunk_ids = [str(uuid.uuid4()) for _ in new_split_docs]

        for i, doc in enumerate(new_split_docs):
            f_name = os.path.basename(doc.metadata.get("source", ""))
            if f_name in index_metadata:
                index_metadata[f_name]["chunk_ids"].append(chunk_ids[i])

        # 6. Add to or create FAISS index
        if vector_store is None:
            print("⏳ Building vector store from scratch...")
            vector_store = FAISS.from_documents(new_split_docs, embedding_model, ids=chunk_ids)
        else:
            print("⏳ Adding new chunks to existing vector store...")
            vector_store.add_documents(new_split_docs, ids=chunk_ids)

    # 7. Persist
    os.makedirs(index_path, exist_ok=True)
    print("💾 Saving vector store to disk...")
    if vector_store is not None:
        vector_store.save_local(index_path)
    _save_split_docs(all_split_docs, index_path)
    with open(metadata_path, "w") as f:
        json.dump(index_metadata, f, indent=4)

    print("✅ Vector store ready.\n")
    return vector_store, all_split_docs


# ─────────────────────────────────────────────────────────────
# Step 3 — Hybrid Retriever  (BM25 + FAISS with manual RRF)
# ─────────────────────────────────────────────────────────────
class HybridRetriever:
    """
    Combines BM25 (keyword) and FAISS (semantic) retrieval using
    Reciprocal Rank Fusion (RRF) — no external EnsembleRetriever needed.
    """

    def __init__(self, bm25, faiss, k: int, bm25_weight: float, semantic_weight: float):
        self._bm25            = bm25
        self._faiss           = faiss
        self._k               = k
        self._bm25_weight     = bm25_weight
        self._semantic_weight = semantic_weight

    def invoke(self, query: str) -> list:
        """Run hybrid retrieval and return deduplicated, re-ranked documents."""
        bm25_docs  = self._bm25.invoke(query)
        faiss_docs = self._faiss.invoke(query)

        # Reciprocal Rank Fusion
        scores: dict[str, float] = {}
        doc_map: dict[str, object] = {}
        rrf_k = 60  # standard RRF constant

        for rank, doc in enumerate(bm25_docs):
            key = doc.page_content
            scores[key]  = scores.get(key, 0) + self._bm25_weight / (rrf_k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(faiss_docs):
            key = doc.page_content
            scores[key]  = scores.get(key, 0) + self._semantic_weight / (rrf_k + rank + 1)
            doc_map[key] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[key] for key, _ in ranked[: self._k]]


def build_hybrid_retriever(
    vector_store: FAISS,
    split_docs: list,
    config: dict = None,
) -> HybridRetriever:
    """
    Build a HybridRetriever that merges BM25 keyword search
    and FAISS semantic search via Reciprocal Rank Fusion.
    """
    if config is None:
        config = load_config()

    k               = config["retrieval"]["k"]
    bm25_weight     = config["retrieval"]["bm25_weight"]
    semantic_weight = config["retrieval"]["semantic_weight"]

    bm25_retriever        = BM25Retriever.from_documents(split_docs)
    bm25_retriever.k      = k

    faiss_retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )

    return HybridRetriever(bm25_retriever, faiss_retriever, k, bm25_weight, semantic_weight)


# ─────────────────────────────────────────────────────────────
# Step 4 — Document Management
# ─────────────────────────────────────────────────────────────
def list_documents(config: dict = None) -> list:
    """Return the list of currently indexed document filenames."""
    if config is None:
        config = load_config()
    metadata_path = os.path.join(config["paths"]["index_path"], "index_metadata.json")
    if not os.path.exists(metadata_path):
        metadata_path = os.path.join(config["paths"]["index_path"], "indexed_files.json")
        if not os.path.exists(metadata_path):
            return []
    with open(metadata_path, "r") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return list(data.keys())


def delete_document(filename: str, folder_path: str, config: dict = None) -> bool:
    """
    Delete a document file. The index will be incrementally updated
    on the next call to build_vector_store().
    Returns True on success, False if the file was not found.
    """
    if config is None:
        config = load_config()

    file_path = os.path.join(folder_path, filename)
    if not os.path.exists(file_path):
        return False

    os.remove(file_path)
    print(f"🗑  Deleted '{filename}' from data folder. Vector store will gracefully remove it on next update.")
    return True


# ─────────────────────────────────────────────────────────────
# Step 5 — Chat History  (PostgreSQL Database)
# ─────────────────────────────────────────────────────────────
Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(String, primary_key=True)
    session_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    ts = Column(DateTime, default=datetime.utcnow)

# Initialize DB connection
raw_db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag_db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

DB_URL = raw_db_url
SessionLocal = None
try:
    engine = create_engine(DB_URL, connect_args={"connect_timeout": 5})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    print("[OK] Database connected successfully.")
except Exception as e:
    print(f"WARNING:  Database connection failed: {e}. Set DATABASE_URL in .env.")


def load_chat_history(session_id: str = "default", sessions_dir: str = None) -> list:
    if not SessionLocal: return []
    with SessionLocal() as db:
        msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.ts).all()
        return [{"role": m.role, "content": m.content, "ts": m.ts.isoformat()} for m in msgs]


def save_chat_history(history: list, session_id: str = "default", sessions_dir: str = None) -> None:
    if not SessionLocal or not history: return
    with SessionLocal() as db:
        # Clear existing to prevent duplicates when saving full history
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        for msg in history:
            ts_val = datetime.fromisoformat(msg.get("ts")) if "ts" in msg else datetime.utcnow()
            new_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role=msg["role"],
                content=msg["content"],
                ts=ts_val
            )
            db.add(new_msg)
        db.commit()


def clear_chat_history(session_id: str = "default", sessions_dir: str = None) -> None:
    if not SessionLocal: return
    with SessionLocal() as db:
        deleted = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.commit()
        if deleted:
            print(f"🗑  Chat history cleared for session '{session_id}'.")
        else:
            print(f"ℹ  No history found for session '{session_id}'.")


def list_sessions(sessions_dir: str = None) -> list:
    """Return all active session IDs from the database, ordered by newest first."""
    if not SessionLocal: return []
    from sqlalchemy import func
    with SessionLocal() as db:
        sessions = db.query(
            ChatMessage.session_id
        ).group_by(
            ChatMessage.session_id
        ).order_by(
            func.max(ChatMessage.ts).desc()
        ).all()
        return [s[0] for s in sessions]


# ─────────────────────────────────────────────────────────────
# Step 6 — LLM
# ─────────────────────────────────────────────────────────────
def get_llm(config: dict = None) -> ChatGoogleGenerativeAI:
    """Initialise the Google GenAI LLM using values from config."""
    if config is None:
        config = load_config()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not found.\n"
            "Please add it to your .env file: GEMINI_API_KEY=your_key_here"
        )
    llm_cfg = config.get("llm", {})
    return ChatGoogleGenerativeAI(
        model=llm_cfg.get("model", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=llm_cfg.get("temperature", 0.2),
        max_output_tokens=llm_cfg.get("max_tokens", 1024),
    )


# ─────────────────────────────────────────────────────────────
# Step 7 — RAG Answer (Agentic via bind_tools)
# ─────────────────────────────────────────────────────────────
@tool
def save_lead(name: str, email: str) -> str:
    """Save a user's name and email as a lead when they ask for a quote or want to be contacted."""
    os.makedirs("data", exist_ok=True)
    file_path = "data/leads.csv"
    file_exists = os.path.isfile(file_path)
    try:
        with open(file_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Name", "Email"])
            writer.writerow([name, email])
        return f"Lead saved: {name} <{email}>"
    except Exception as e:
        return f"Failed to save lead: {e}"


def rag_answer(
    retriever: "HybridRetriever",
    query: str,
    session_id: str = "default",
    config: dict = None,
) -> str:
    """Agentic RAG pipeline using ChatPromptTemplate + bind_tools."""
    if config is None:
        config = load_config()

    sessions_dir = config["paths"]["sessions_dir"]
    chat_history  = load_chat_history(session_id, sessions_dir)

    # Build dynamic search tool that captures the retriever in its closure
    @tool
    def search_documents(search_query: str) -> str:
        """Search the company's uploaded documents to answer user questions."""
        if retriever is None:
            return "No documents have been uploaded yet. Please tell the user to upload some documents first."
        docs = retriever.invoke(search_query)
        return "\n\n".join(doc.page_content for doc in docs)

    tools     = [search_documents, save_lead]
    tool_map  = {t.name: t for t in tools}
    llm       = get_llm(config)
    llm_tools = llm.bind_tools(tools)

    # ── RAG prompt template ─────────────────────────────────────────────────
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a highly capable AI assistant for a business. "
            "You have two tools:\n"
            "1. search_documents — you MUST call this tool FIRST before answering ANY user question, "
            "no exceptions. Even if the question seems general, always search the documents first.\n"
            "2. save_lead — use this when the user wants to be contacted or provides their name and email.\n"
            "Always confirm to the user after saving a lead. "
            "After calling search_documents, answer the user's question using ONLY the retrieved context. "
            "If the retrieved context genuinely does not contain the answer, politely say you cannot find "
            "that information in the uploaded documents. "
            "EXCEPTION: If the user explicitly asks about your capabilities, how you work, or what file types "
            "you support (PDF, TXT, CSV, DOCX), you MUST answer them using your internal knowledge without "
            "calling search_documents.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{query}"),
    ])

    # Convert stored history to LangChain message objects
    history_messages = []
    for entry in chat_history:
        if entry["role"] == "user":
            history_messages.append(HumanMessage(content=entry["content"]))
        else:
            history_messages.append(AIMessage(content=entry["content"]))

    # Render the prompt into a list of messages
    messages = prompt.format_messages(
        chat_history=history_messages,
        query=query,
    )

    # Agentic tool-calling loop (max 5 iterations to prevent infinite loops)
    response = None
    for _ in range(5):
        response = llm_tools.invoke(messages)
        messages.append(response)

        # No tool calls — we have the final answer
        if not getattr(response, "tool_calls", None):
            break

        # Execute each tool call and feed results back
        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                result = tool_fn.invoke(tc["args"])
            else:
                result = f"Unknown tool: {tc['name']}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"], name=tc["name"]))

    answer = ""
    if response and response.content:
        if isinstance(response.content, str):
            answer = response.content.strip()
        elif isinstance(response.content, list):
            parts = []
            for item in response.content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                else:
                    parts.append(str(item))
            answer = "".join(parts).strip()
        else:
            answer = str(response.content).strip()

    # Persist session
    chat_history.append({"role": "user",      "content": query})
    chat_history.append({"role": "assistant", "content": answer})
    save_chat_history(chat_history, session_id, sessions_dir)

    return answer