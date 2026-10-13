# Custom Business AI Assistant (Premium RAG System)

Welcome! This document is your complete guide to running, using, and customizing your new AI assistant. Whether you are technical or not, this guide is written to be clear and easy to follow every step of the way.

---

## Table of Contents

1. [What Is This System?](#1-what-is-this-system)
2. [What Can It Do?](#2-what-can-it-do)
3. [Project Structure](#3-project-structure)
4. [Prerequisites](#4-prerequisites)
5. [Setup & First Launch](#5-setup--first-launch)
6. [Using the Web Dashboard](#6-using-the-web-dashboard)
7. [Managing Your Documents](#7-managing-your-documents)
8. [Customizing the AI Behavior](#8-customizing-the-ai-behavior)
9. [API Reference](#9-api-reference)
10. [Lead Generation Feature](#10-lead-generation-feature)
11. [Troubleshooting](#11-troubleshooting)
12. [Frequently Asked Questions](#12-frequently-asked-questions)

---

## 1. What Is This System?

This is a **custom AI assistant trained entirely on your own business documents**. Instead of using generic internet knowledge, the AI reads your specific files - like product manuals, pricing sheets, FAQs, or policy documents - and answers questions based only on that information.

Think of it like hiring a new employee who has read every document in your company and can answer any question about it instantly, 24/7.

**The system has three main parts working together:**

| Part | What It Does |
|------|-------------|
| **React Web Dashboard** | The modern chat interface your users interact with |
| **FastAPI Backend** | The brain - processes questions, searches documents, calls the AI |
| **PostgreSQL Database** | Stores all conversation history persistently |

Everything is packaged with **Docker**, so the entire system starts with a single command.

---

## 2. What Can It Do?

### Intelligent Document Q&A
Upload your business documents and ask questions in plain English. The AI searches across all your files simultaneously to find the most relevant answer.

### Hybrid Search (More Accurate Than Standard Search)
Under the hood, the system uses two search methods at the same time and combines the best results:
- **Semantic Search (FAISS)** - Understands the *meaning* of your question, even if you use different words than what is in the document.
- **Keyword Search (BM25)** - Finds exact matches and specific terms like product codes or names.

This hybrid approach gives significantly more accurate results than using either method alone.

### Memory Across Conversations
Each conversation is a **session**. The AI remembers everything you said earlier in the same session, so you can ask follow-up questions naturally without repeating yourself. All sessions are saved in the database permanently.

### Multiple Sessions
You can have unlimited separate conversations (e.g., one for "Customer Support", another for "Sales Queries"). Each session has its own independent history.

### Lead Generation (Automatic)
When a customer says they want to be contacted or requests a quote, the AI automatically asks for their name and email and saves it to a `leads.csv` file. No manual work required.

### Document Management via UI
Upload new documents or remove old ones directly from the web dashboard - no need to touch the server.

### Dark / Light Mode
The web interface supports both dark and light themes, which are saved per browser.

### Export Conversations
Any conversation can be downloaded as a `.txt` file with a single click.

---

## 3. Project Structure

Here is what each file and folder in this project does:

```
Project Root
|
|-- RAG.py              # Core engine: document loading, search, AI logic, database
|-- api.py              # REST API: all the web endpoints your dashboard calls
|-- config.yaml         # Configuration file: tune AI behaviour without touching code
|-- requirements.txt    # Python package dependencies
|-- Dockerfile          # Instructions to containerize the Python API
|-- docker-compose.yml  # Starts the full stack (Database + API + Frontend) together
|-- .env                # Your secret API keys (NEVER share this file)
|
|-- data/               # Drop your business documents here
|   |-- leads.csv       # Auto-created when a lead is captured
|
|-- faiss_index/        # Auto-created: stores the searchable document index
|
|-- sessions/           # Auto-created: stores per-session chat history files
|
|-- frontend/           # The React web dashboard
    |-- Dockerfile      # Instructions to containerize the React UI
    |-- src/
        |-- App.jsx     # Main dashboard application code
```

> **Important:** The `faiss_index/` and `sessions/` folders are built automatically. You do not need to create them manually.

---

## 4. Prerequisites

Before running the application, you need the following installed on your computer or server:

### Option A: Docker (Recommended - Easiest Setup)
- **Docker Desktop**: Download from [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- That is it. Docker handles everything else automatically.

### Option B: Manual Setup (For Developers)
- **Python 3.11+**: [https://www.python.org/downloads](https://www.python.org/downloads)
- **Node.js 18+**: [https://nodejs.org](https://nodejs.org)
- **PostgreSQL 15+**: [https://www.postgresql.org/download](https://www.postgresql.org/download)

---

## 5. Setup & First Launch

### Step 1: Configure Your API Keys

Open the `.env` file in the project root folder. It should look like this:

```ini
GEMINI_API_KEY=your_gemini_api_key_here
API_SECRET_KEY=your_custom_secure_password_here
DATABASE_URL=postgresql://postgres:your_password@db:5432/rag_db
```

**What each key does:**

| Key | Description |
|-----|-------------|
| `GEMINI_API_KEY` | Your Google Gemini API key. The AI uses this to generate answers. Get one free at [aistudio.google.com](https://aistudio.google.com/) |
| `API_SECRET_KEY` | A password you create to protect your API. Choose any strong password (e.g., `MyCompany-Secret-2024!`) |
| `DATABASE_URL` | The connection string to PostgreSQL. **If using Docker, leave this exactly as-is.** |

> **Never share your `.env` file** with anyone or upload it to GitHub. Your Gemini key is sensitive.

---

### Step 2: Add Your Documents

Place your business documents inside the `data/` folder. You can add as many files as you want in any mix of supported formats:

```
data/
|-- employee_handbook.pdf
|-- product_catalog.docx
|-- pricing_2024.csv
|-- company_faq.txt
```

> **Tip:** You can also upload documents through the web dashboard after the system is running - no need to restart anything.

---

### Step 3: Launch the System

Open a terminal (Command Prompt or PowerShell on Windows) in the project root folder and run:

```bash
docker-compose up --build
```

The first launch will take **3-5 minutes** as Docker downloads and installs all components. Subsequent launches will be much faster (under 30 seconds).

You will know it is ready when you see a line similar to:
```
api-1  | INFO:     Application startup complete.
```

---

### Step 4: Open the Dashboard

Once running, open your browser and go to:

| Service | URL |
|---------|-----|
| **Web Chat Dashboard** | [http://localhost:5173](http://localhost:5173) |
| **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) |

---

### Stopping the System

To stop everything cleanly, press `Ctrl + C` in the terminal where Docker is running, then:

```bash
docker-compose down
```

To stop AND delete all saved data (conversations, index):
```bash
docker-compose down -v
```

---

## 6. Using the Web Dashboard

The dashboard is designed to be intuitive. Here is a quick tour of every feature:

### The Sidebar (Left Panel)
- **Thread List** - Every conversation you start appears here as a thread. Click any thread to switch to it.
- **Search Bar** - Type to filter and find a specific past conversation by name.
- **Rename** - Hover over a thread and click the pencil icon to give it a custom name.
- **Delete** - Click the x icon on a thread to permanently delete it and its history.
- **Download Chat** - Saves the current conversation as a `.txt` file to your computer.
- **Clear Chat** - Deletes all messages in the current session from the database.

### The Top Bar (Header)
- **New Chat button** - Starts a brand-new conversation session. (Keyboard shortcut: `Alt + N`)
- **Theme Toggle** - Switches between dark and light mode.
- **API Status Indicator** - A small dot showing whether the backend is online (green) or offline (red).

### The Chat Area
- Type your question in the input box at the bottom and press **Enter** to send.
- Press **Shift + Enter** to add a new line without sending.
- Click the **+** button to upload a document directly from the chat.
- Click **Copy** on any AI response to copy it to your clipboard.
- A **scroll-to-bottom** arrow appears when you scroll up in a long conversation.

### Suggestion Pills
When you open a new chat, the dashboard shows suggested starter questions. If documents are uploaded, it suggests document-specific questions. If no documents are loaded yet, it suggests questions about the system capabilities.

---

## 7. Managing Your Documents

### Uploading Documents

**Method 1 - Via the Web Dashboard (Recommended)**
Click the **+** button in the chat input area. Select your file. The system will upload it, index it, and make it searchable within seconds. A toast notification will confirm success.

**Method 2 - Via the `data/` Folder**
Copy files directly into the `data/` folder on the server. They will be indexed automatically the next time the API starts.

### Deleting Documents

You can remove a document via the REST API (see the `/documents/{filename}` DELETE endpoint in Section 9). When a document is deleted, the search index is automatically rebuilt to exclude it.

### How Indexing Works (Incremental)

The system uses **smart incremental indexing** - it never rebuilds the entire index from scratch. Instead, on every startup or document upload:

| Event | What Happens |
|-------|-------------|
| New file added | Only the new file is chunked and indexed |
| Existing file modified | Old chunks are removed; the file is re-indexed |
| File deleted | Its chunks are automatically removed from the index |
| File unchanged | Skipped entirely (detected via SHA-256 hash) |

This means the system starts fast even with hundreds of documents indexed.

### Supported File Types

| Type | Extension | Notes |
|------|-----------|-------|
| PDF | `.pdf` | All standard PDFs, including multi-page |
| Word Document | `.docx` | Microsoft Word format |
| Plain Text | `.txt` | Any UTF-8 text file |
| Spreadsheet / CSV | `.csv` | Each row is treated as a separate passage |

> **Note:** Password-protected or encrypted files cannot be read. Save them without a password first.

---

## 8. Customizing the AI Behavior

The `config.yaml` file lets you fine-tune the AI without editing any code. Open it in any text editor.

```yaml
llm:
  model: gemini-1.5-flash  # The Google Gemini model to use (e.g. gemini-1.5-flash, gemini-2.0-flash)
  temperature: 0.2          # Controls creativity (0.0 = factual, 1.0 = creative)
  max_tokens: 1024          # Maximum length of each AI response

retrieval:
  k: 10                     # How many document passages to retrieve per question
  chunk_size: 1500          # How large each document chunk is (in characters)
  chunk_overlap: 300        # Overlap between chunks to avoid cutting context mid-sentence
  bm25_weight: 0.4          # Importance of keyword search (0.0 to 1.0)
  semantic_weight: 0.6      # Importance of meaning-based search (0.0 to 1.0)

paths:
  data_folder: data/        # Folder where source documents are stored
  index_path: faiss_index/  # Folder where the FAISS vector index is persisted on disk
  sessions_dir: sessions/   # Folder where per-session chat history files live
```

### Recommended Settings by Use Case

| Use Case | Suggested Changes |
|----------|-------------------|
| Precise, factual answers (legal, medical) | `temperature: 0.0`, `k: 15` |
| Conversational / friendly tone | `temperature: 0.5`, `model: gpt-4o` |
| Large documents (500+ pages) | `chunk_size: 2000`, `chunk_overlap: 400` |
| Short documents / FAQs | `chunk_size: 800`, `chunk_overlap: 150` |
| Emphasis on exact keyword matching | Increase `bm25_weight` to `0.6`, reduce `semantic_weight` to `0.4` |

> After editing `config.yaml`, restart the API for changes to take effect: `docker-compose restart api`

---

## 9. API Reference

The full interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs) when the system is running.

All API endpoints require the `X-API-Key` header set to the value of your `API_SECRET_KEY`.

### Endpoints at a Glance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check if the API is online and how many documents are indexed |
| `POST` | `/ask` | Send a question and receive an AI answer |
| `POST` | `/upload` | Upload a new document to the knowledge base |
| `GET` | `/documents` | List all currently indexed documents |
| `DELETE` | `/documents/{filename}` | Remove a document and rebuild the index |
| `GET` | `/history/{session_id}` | Retrieve all messages for a session |
| `DELETE` | `/history/{session_id}` | Clear the history for a session |
| `GET` | `/sessions` | List all active session IDs |

### Example: Asking a Question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_secret_key" \
  -d '{"query": "What is the return policy?", "session_id": "customer-123"}'
```

**Response:**
```json
{
  "answer": "According to your return policy document, customers can return items within 30 days...",
  "session_id": "customer-123"
}
```

---

## 10. Lead Generation Feature

The AI assistant has a built-in **automatic lead capture** tool. When a user in the chat says something like:

> *"I would like to get a quote"* or *"Can someone contact me?"* or *"I am interested, please reach out"*

The AI will politely ask for their **name** and **email address** and save the information automatically to `data/leads.csv`.

### Example Conversation

```
User:    "I am interested in your enterprise plan. Can someone call me?"
AI:      "Of course! I would be happy to have someone reach out to you. Could I get your name and email address?"
User:    "Sure, I am John Smith, john@company.com"
AI:      "Thank you, John! I have saved your details and a team member will be in touch shortly."
```

### Viewing Your Leads

Open `data/leads.csv` in Excel or Google Sheets:

```
Name,Email
John Smith,john@company.com
Jane Doe,jane@example.com
```

This file is appended to automatically - it is never overwritten.

---

## 11. Troubleshooting

### Docker & Startup Issues

| Problem | Solution |
|---------|----------|
| `docker-compose` command not found | Make sure Docker Desktop is installed and running. Try restarting your computer. |
| Port `5173` or `8000` already in use | Another application is using that port. Stop it, or change the port in `docker-compose.yml`. |
| Build fails with a package error | Run `docker-compose build --no-cache` to force a clean rebuild. |
| Containers start but then immediately exit | Run `docker-compose logs api` to see the specific error message. |
| Warning: `version` attribute is obsolete | Remove the `version: '3.8'` line at the top of `docker-compose.yml` - it is no longer required in modern Docker Compose. |

### API & Authentication Issues

| Problem | Solution |
|---------|----------|
| `403 Forbidden` or `Invalid API Key` | The `X-API-Key` in the request does not match `API_SECRET_KEY` in your `.env` file. Double-check both. |
| `GEMINI_API_KEY not found` error in logs | The `.env` file is missing or `GEMINI_API_KEY` is not set correctly. Ensure there are no spaces around the `=`. |
| AI returns `"I cannot find the answer in the documents"` | The document was likely not indexed. Check `/health` to confirm `indexed_documents` is greater than 0. |

### Document Issues

| Problem | Solution |
|---------|----------|
| File uploads but AI cannot answer from it | The file may be image-based (scanned PDF). The system reads text only. Convert to text-based PDF first. |
| `Unsupported file type` error | Only `.pdf`, `.txt`, `.csv`, and `.docx` are supported. Convert other formats first. |
| Old document content still appearing after deletion | The index may need a moment to rebuild. Wait 30 seconds and try again. |

### Database Issues

| Problem | Solution |
|---------|----------|
| `Database connection failed` in logs | If running without Docker, ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct. |
| Chat history not loading | Confirm the `db` container is healthy: `docker-compose ps`. If not, run `docker-compose restart db`. |


