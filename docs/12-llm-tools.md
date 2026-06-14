# LLM Tools For Nina Chat And Agent

This document is the source of truth for the tool-calling layer that powers Nina's chat and agent modes. It is the reference a future agent should consult to stay oriented while making changes. If something in the code disagrees with this doc, update the doc to match the code in the same change.

## Scope

- Chat mode uses real tool calls against the Obsidian vault, plus reads of projects, tickets, kanban, jobs, and LLM logs.
- Agent mode uses the same tool surface plus write tools (tickets, projects, notes, research, workflows, jobs).
- Chat is read-only by construction: it gets `definitions(read_only=True)`. Agent gets the full set.
- Multi-turn chat carries the last N (default 6) user/assistant/tool turns into the prompt.
- Existing `nina ask` and `POST /ask` paths continue to work; they go through the same tool path.

Out of scope for this layer (deferred to other work):

- TUI streaming of tokens.
- Persistent cross-session memory.

## Module Layout

- `packages/nina_core/nina_core/llm/provider.py` — LLM provider boundary. `LLMRequest`, `LLMResponse`, `LLMService`, `CodexAuthProvider`, `OpenAIProvider`, `FakeProvider`.
- `packages/nina_core/nina_core/llm/tools.py` — `ToolSpec`, `ToolContext`, `ToolRegistry`, default Nina tool set.
- `packages/nina_core/nina_core/sessions/service.py` — `SessionService` with `_run_tool_loop`, `_send_chat`, `_send_agent`, cancellation, and history loading.
- `packages/nina_core/nina_core/search/indexer.py` — FTS5 search and `ask_obsidian` (the one-shot RAG path that still exists for `/ask` and `nina ask`).
- `packages/nina_core/nina_core/search/embeddings.py` — `EmbeddingService` abstraction, `FastembedEmbeddingService`, `FakeEmbeddingService`, `OpenAIEmbeddingService`, RRF merge helpers.
- `packages/nina_core/nina_core/search/watcher.py` — `VaultWatcher` using `watchdog` (started in daemon lifespan).
- `packages/nina_core/nina_core/notes/service.py` — `NoteService` for read/write of Markdown notes under the vault.
- `apps/server/nina_server/app.py` — FastAPI app, including `/notes*`, `/sessions/{id}/cancel`, and `/ask`.

## LLM Provider Tool Calling

### LLMRequest

```python
class LLMRequest(BaseModel):
    purpose: str
    prompt: str                                  # still required for compatibility; ignored when messages is set
    messages: list[dict] | None = None           # multi-turn input
    tools: list[ToolDefinition] | None = None    # JSON-schema function definitions
    tool_choice: str | None = "auto"             # "auto" | "required" | "none"
    model: str | None = None
    workflow_run_id: str | None = None
    session_id: str | None = None
    max_tool_iterations: int = 5                 # used by the service loop, not the provider
```

`ToolDefinition` is `{ name: str, description: str, parameters: dict }`. `parameters` is a JSON Schema object with `type: "object"`, `properties`, and `required`.

### LLMResponse

```python
class LLMResponse(BaseModel):
    response: str
    model: str
    provider: str
    tool_calls: list[ToolCall] = []              # id, name, arguments dict
    finish_reason: str | None = None
```

### Provider translation

- `CodexAuthProvider.complete` uses the OpenAI Responses API. Tools are passed as `tools=[{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]`, with `tool_choice=request.tool_choice or "auto"`. The streaming loop already walks `event.type`; tool calls come through `response.output_item.added` with `item.type == "function_call"` and the JSON args land on `response.function_call_arguments.done`.
- `OpenAIProvider.complete` uses `chat.completions.create` with the same tool shape. `message.tool_calls` is a list of `ChatCompletionMessageToolCall`; args are a JSON string in `function.arguments`.
- `FakeProvider.complete` returns a configurable fake tool call sequence (see `FakeProvider.fake_tool_calls`) and a final text response so tests can exercise the loop without a network.

## Tool Registry

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]          # JSON schema
    handler: Callable[[ToolContext, dict], dict[str, Any]]
    read_only: bool = True
    requires_session: bool = False

class ToolContext:
    db_path: str
    vault_path: Path
    db: Session
    obsidian: ObsidianService
    session_id: str | None
    embeddings: EmbeddingService | None

class ToolRegistry:
    def register(self, spec: ToolSpec) -> None
    def definitions(self, *, read_only: bool | None = None) -> list[dict]
    def execute(self, name: str, args: dict, ctx: ToolContext) -> dict
```

`definitions(read_only=True)` returns only read tools; `definitions(read_only=False)` returns all. `definitions(read_only=None)` returns all regardless of `read_only`.

The default Nina tool set is built by `default_tool_registry()` in `nina_core.llm.tools`. It registers everything in the table below.

## Default Tool Set

### Read (chat + agent)

| Tool | Args | Returns |
| --- | --- | --- |
| `obsidian_search` | `query: str, limit: int = 5` | `{ "results": [{ "path", "title", "nina_type", "snippet" }] }` |
| `obsidian_semantic_search` | `query: str, limit: int = 5` | same shape, via cosine over embeddings |
| `obsidian_hybrid_search` | `query: str, limit: int = 5` | RRF merge of lexical and semantic |
| `obsidian_get_note` | `path: str` | `{ "path", "title", "nina_type", "frontmatter", "body", "mtime" }` |
| `obsidian_list_notes` | `folder?, nina_type?, limit?` | `{ "notes": [...] }` |
| `kanban_get` | none | `{ "columns": { col: [...] } }` |
| `tickets_list` | `status?, project_id?, include_archived?` | `{ "tickets": [...] }` |
| `tickets_get` | `id_or_title: str` | `{ "ticket": ... }` or 404 |
| `projects_list` | none | `{ "projects": [...] }` |
| `projects_get` | `id_or_name: str` | `{ "project": ... }` or 404 |
| `jobs_list` | none | `{ "jobs": [...] }` |
| `job_runs` | `name?, limit?` | `{ "runs": [...] }` |
| `llm_logs` | `limit?` | `{ "interactions": [...] }` |

### Write (agent only)

| Tool | Args | Returns |
| --- | --- | --- |
| `tickets_create` | `title, description?, project_id?, kanban_column?` | `{ "ticket": ... }` |
| `tickets_update` | `id, title?, description?, status?, kanban_column?, kanban_position?` | `{ "ticket": ... }` |
| `tickets_move` | `id, column, position?` | `{ "ticket": ... }` |
| `tickets_delete` | `id` | `{ "deleted": true }` |
| `tickets_archive` | `id` | `{ "ticket": ... }` |
| `tickets_unarchive` | `id` | `{ "ticket": ... }` |
| `projects_create` | `name, description?` | `{ "project": ... }` |
| `projects_update` | `id, name?, description?, status?` | `{ "project": ... }` |
| `projects_delete` | `id` | `{ "deleted": true }` |
| `notes_create` | `path, body, nina_type?` | `{ "path": ... }` |
| `notes_append` | `path, body` | `{ "path": ... }` |
| `notes_update` | `path, body` | `{ "path": ... }` |
| `research_run` | `topic` | `{ "note_path", "summary", "sources" }` |
| `workflows_run` | `name, input?` | `{ "id", "status", "output" }` |
| `jobs_run` | `name` | `{ "run": ... }` |
| `jobs_enable` | `name` | `{ "job": ... }` |
| `jobs_disable` | `name` | `{ "job": ... }` |
| `search_reindex` | none | `{ "reindexed": true }` |
| `obsidian_open` | `path` | `{ "opened": true }` |

Path safety for `notes_*` and `obsidian_open`:

1. Resolve to absolute; reject `..` traversal.
2. Must be inside `vault_path`.
3. Refuse paths under `System/Indexes/`, `System/Logs/`, `System/Deleted/`, `Templates/`.

## Session Tool Loop

`SessionService._run_tool_loop(session_id, content, *, read_only, history_limit=6, max_iterations=5, system_prompt=...)` is the shared core:

1. Load the last `history_limit` messages for the session, in chronological order.
2. Build a `messages` list: `[system, *history, user]`. The user message is the latest content. If `history_limit` is 0, the list is just `[system, user]`.
3. Call `self.llm.complete(LLMRequest(purpose=..., messages=messages, tools=tools, tool_choice="auto", session_id=session_id))`.
4. If the response has `tool_calls`, execute each via `self.tools.execute(...)` wrapped in try/except (errors are returned as `{ "error": "..." }` to the model). Append a `tool` message for each result (and a single `assistant` message with the `tool_calls` so the LLM sees its own call). Loop.
5. Stop on a final text response, `max_iterations`, or `cancel_requested`.
6. Persist the user message, each `tool` invocation as a `role="tool"` `ConversationMessage`, and the final `assistant` message with metadata `{ "tools_used": [...], "sources": [...], "iterations": n, "finish_reason": "..." }`.

The user message is saved **before** the loop starts. The `tool` and `assistant` messages are saved after. This keeps the session consistent with multi-turn.

### Cancellation

`POST /sessions/{id}/cancel` flips a row-level flag the loop checks between iterations. The loop calls `_check_cancel(session_id)` after each `llm.complete`. If set, it stops with `finish_reason="cancelled"`. The assistant message still gets persisted with a best-effort text ("Cancelled by user.").

### Text fallback

If the LLM returns no `tool_calls` and `mode == "agent"`, the existing text-based parser (`_extract_commands`, `_fallback_agent_commands`) runs to maintain backward compatibility with the original `nina ticket create ...` style. The new tool-calling path is preferred, not required.

## Multi-turn Chat

`SessionService._send_chat` is a thin wrapper around `_run_tool_loop(..., read_only=True, history_limit=6)`. The history is whatever the session already contains. Sources are aggregated from any `obsidian_search` / `obsidian_semantic_search` / `obsidian_hybrid_search` results and attached to the assistant message metadata so the TUI's "Sources" rendering continues to work.

## Embeddings

```python
class EmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]     # batched
    def cosine_top_k(self, query: list[float], rows, k: int) -> list[ScoredRow]
    @property
    def model_name(self) -> str
    @property
    def dim(self) -> int
```

- `FastembedEmbeddingService` uses `fastembed` (ONNX, no torch). Default model `BAAI/bge-small-en-v1.5` (~30MB, 384 dims). Downloaded on first use; failures raise a clear error.
- `FakeEmbeddingService` produces deterministic random vectors from a hash of the text. Used by tests and `NINA_EMBEDDING_PROVIDER=fake`.
- `OpenAIEmbeddingService` uses `text-embedding-3-small` via the OpenAI client. Requires `OPENAI_API_KEY`.

Storage: `note_embeddings(note_id, path, title, nina_type, model, dim, embedding BLOB, created_at, updated_at)`. The `embedding` column is a packed `float32` little-endian blob. A unique index on `(note_id, model)` makes upserts idempotent.

RRF (Reciprocal Rank Fusion) merge:

```
score(doc) = sum over rankers of: 1 / (k + rank)
```

with `k = 60` by default. Hybrid search runs lexical and semantic, RRF-merges their rankings, and returns the top K.

## Live Indexing

`VaultWatcher` is a `watchdog` observer that runs in the daemon process. On `on_modified` / `on_created` / `on_moved` / `on_deleted`, it debounces per path (200ms) and reindexes the single note (FTS5 + embeddings). Configurable via `NINA_SEARCH_WATCHER` (`"on" | "off"`, default `"on"`).

Skipped paths: `System/Indexes/`, `System/Logs/`, `System/Deleted/`, anything under `.obsidian/`, anything ending in `*.tmp` or `*.swp`.

A scheduled `reindex-vault` job (cron `*/15 * * * *` by default) calls the same `index_notes` / re-embed path as a backstop. Configurable via `NINA_REINDEX_CRON` (empty string disables the job).

## API

- `GET /notes?folder=&nina_type=&limit=20` → `{ "notes": [{ "path", "title", "nina_type", "entity_id", "last_indexed_at", "updated_at" }] }`
- `GET /notes/{path:path}` → `{ "path", "title", "nina_type", "frontmatter", "body", "mtime" }`
- `POST /notes` body `{ path, body, nina_type? }` → `{ "path" }`
- `PATCH /notes/{path:path}` body `{ body?, append?, frontmatter_patch? }` → `{ "path" }`
- `POST /sessions/{id}/cancel` → `{ "cancelled": true }`

## Test Plan

- Unit:
  - `tests/unit/test_tool_registry.py` — register, list (read-only filter), execute, allowlist.
  - `tests/unit/test_llm_provider.py` — extend with `tools=`, `tool_choice`, `tool_calls` parse.
  - `tests/unit/test_sessions_service.py` — multi-turn, tool-calling chat, tool-calling agent.
  - `tests/unit/test_embeddings.py` — deterministic fake, RRF merge.
  - `tests/unit/test_notes_service.py` — path safety, get/append/update.
- Integration:
  - `tests/integration/test_daemon_api.py` — `/notes` GET/POST/PATCH, `/sessions/{id}/cancel`, tool-using chat/agent.
  - `tests/integration/test_cli_daemon_smoke.py` — `nina note show`, `nina note create`, `nina chat test` with tool calls.
- Smoke: `make smoke` covers the new endpoints.

## Security Boundary

- Chat calls `definitions(read_only=True)`. The provider only sees read tools, so even a chat-prompt-injection cannot cause writes through the tool loop.
- Agent calls `definitions(read_only=False)`. The provider sees write tools, but each handler enforces its own validation (e.g., `notes_create` refuses paths outside the vault, `tickets_create` rejects empty titles).
- Path-safety: `notes_*` and `obsidian_open` validate absolute paths, `..` traversal, and refused prefixes.
- No general shell, no plugin system, no user-defined tools in this layer.
