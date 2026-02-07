#!/usr/bin/env python3
# Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: ChromaDB vector store integration for SLATE
"""
SLATE ChromaDB Integration — Persistent Vector Store for Codebase Embeddings
=============================================================================

Replaces flat-file JSON embedding storage with ChromaDB for production-grade
semantic search across the SLATE codebase. Integrates with the ML Orchestrator's
Ollama embedding pipeline and the autonomous task discovery system.

Architecture:
    Ollama (nomic-embed-text) --> ChromaDB (persistent) --> Semantic Search API
         |                            |                          |
    Embed code/docs            Store vectors              Query for tasks
         |                            |                          |
    ml_orchestrator.py         slate_chromadb.py          Autonomous loops

Features:
- Persistent local storage (survives restarts)
- Collection-per-domain (code, docs, tasks, workflows)
- Semantic search with metadata filtering
- Batch embedding via Ollama nomic-embed-text
- Incremental index updates (only changed files)

Security:
- Local-only: ChromaDB in-process (no server, no network)
- Data stored at: slate_memory/chromadb/

Usage:
    python slate/slate_chromadb.py --status          # Show collections & stats
    python slate/slate_chromadb.py --index            # Index codebase
    python slate/slate_chromadb.py --search "query"   # Semantic search
    python slate/slate_chromadb.py --reset             # Reset all collections
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: workspace setup
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CHROMADB_DIR = WORKSPACE_ROOT / "slate_memory" / "chromadb"
STATE_FILE = WORKSPACE_ROOT / ".slate_chromadb_state.json"

# Collection definitions
COLLECTIONS = {
    "slate_code": {
        "description": "Python source code from slate/ and agents/",
        "dirs": ["slate", "agents"],
        "extensions": [".py"],
        "chunk_size": 500,
    },
    "slate_docs": {
        "description": "Documentation and markdown files",
        "dirs": ["docs", "skills", ".github"],
        "extensions": [".md"],
        "chunk_size": 800,
    },
    "slate_workflows": {
        "description": "CI/CD workflow definitions",
        "dirs": [".github/workflows"],
        "extensions": [".yml", ".yaml"],
        "chunk_size": 600,
    },
    "slate_config": {
        "description": "Configuration files",
        "dirs": [".github", "plugins", "models"],
        "extensions": [".yaml", ".yml", ".json", ".toml"],
        "chunk_size": 400,
    },
}


class SlateChromaDB:
    """Persistent vector store for SLATE codebase semantic search."""

    # Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: ChromaDB integration core

    def __init__(self):
        self.workspace = WORKSPACE_ROOT
        self.db_path = CHROMADB_DIR
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._ollama = None
        self.state = self._load_state()

    @property
    def client(self):
        """Lazy-load ChromaDB client (persistent, in-process)."""
        if self._client is None:
            import chromadb
            # Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: Use persistent client
            self._client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=chromadb.Settings(
                    anonymized_telemetry=False,  # No external telemetry (security rule)
                    allow_reset=True,
                ),
            )
        return self._client

    @property
    def ollama(self):
        """Lazy-load Ollama client for embeddings."""
        if self._ollama is None:
            from slate.ml_orchestrator import OllamaClient
            self._ollama = OllamaClient()
        return self._ollama

    def _load_state(self) -> dict:
        """Load indexing state."""
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "last_full_index": None,
            "last_incremental": None,
            "file_hashes": {},
            "total_indexed": 0,
            "total_chunks": 0,
        }

    def _save_state(self):
        """Save indexing state."""
        STATE_FILE.write_text(
            json.dumps(self.state, indent=2, default=str), encoding="utf-8"
        )

    def _file_hash(self, path: Path) -> str:
        """Get SHA-256 hash of file content."""
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

    def _chunk_text(self, text: str, max_chars: int = 500) -> list[str]:
        """Split text into overlapping chunks by lines."""
        lines = text.split("\n")
        chunks = []
        current: list[str] = []
        current_len = 0

        for line in lines:
            if current_len + len(line) > max_chars and current:
                chunks.append("\n".join(current))
                # Keep last 2 lines for overlap
                overlap = current[-2:] if len(current) >= 2 else current
                current = list(overlap)
                current_len = sum(len(l) + 1 for l in current)
            current.append(line)
            current_len += len(line) + 1

        if current:
            chunks.append("\n".join(current))

        return chunks or [text[:max_chars]]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts via Ollama."""
        embeddings = []
        for text in texts:
            try:
                emb = self.ollama.embed("nomic-embed-text:latest", text)
                embeddings.append(emb)
            except Exception:
                # Return zero vector on failure
                embeddings.append([0.0] * 768)
        return embeddings

    # ------------------------------------------------------------------
    # Collection Management
    # ------------------------------------------------------------------

    def get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def list_collections(self) -> list[dict]:
        """List all collections with stats."""
        results = []
        for col in self.client.list_collections():
            count = col.count()
            results.append({
                "name": col.name,
                "count": count,
                "metadata": col.metadata,
            })
        return results

    def reset_all(self):
        """Reset all collections."""
        self.client.reset()
        self.state = {
            "last_full_index": None,
            "last_incremental": None,
            "file_hashes": {},
            "total_indexed": 0,
            "total_chunks": 0,
        }
        self._save_state()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_collection(self, collection_name: str, incremental: bool = True) -> dict:
        """Index files into a specific collection."""
        if collection_name not in COLLECTIONS:
            return {"error": f"Unknown collection: {collection_name}"}

        config = COLLECTIONS[collection_name]
        collection = self.get_or_create_collection(collection_name)
        chunk_size = config.get("chunk_size", 500)

        files_indexed = 0
        files_skipped = 0
        chunks_added = 0

        for dir_name in config["dirs"]:
            dir_path = self.workspace / dir_name
            if not dir_path.exists():
                continue

            for ext in config["extensions"]:
                for file_path in dir_path.rglob(f"*{ext}"):
                    rel_path = str(file_path.relative_to(self.workspace))

                    # Skip files in gitignored directories
                    if any(skip in rel_path for skip in [
                        "actions-runner", "__pycache__", ".venv", "node_modules",
                        "slate_work", ".git"
                    ]):
                        continue

                    # Incremental: skip unchanged files
                    if incremental:
                        current_hash = self._file_hash(file_path)
                        stored_hash = self.state["file_hashes"].get(rel_path)
                        if stored_hash == current_hash:
                            files_skipped += 1
                            continue
                        self.state["file_hashes"][rel_path] = current_hash

                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        chunks = self._chunk_text(content, max_chars=chunk_size)

                        # Delete existing entries for this file
                        try:
                            collection.delete(where={"file_path": rel_path})
                        except Exception:
                            pass

                        # Embed and add chunks
                        ids = [f"{rel_path}::{i}" for i in range(len(chunks))]
                        metadatas = [
                            {
                                "file_path": rel_path,
                                "chunk_index": i,
                                "total_chunks": len(chunks),
                                "extension": ext,
                                "directory": dir_name,
                            }
                            for i in range(len(chunks))
                        ]

                        embeddings = self._embed_batch(chunks)
                        collection.add(
                            ids=ids,
                            documents=chunks,
                            embeddings=embeddings,
                            metadatas=metadatas,
                        )

                        files_indexed += 1
                        chunks_added += len(chunks)

                    except Exception as e:
                        print(f"  Skip {rel_path}: {e}")

        return {
            "collection": collection_name,
            "files_indexed": files_indexed,
            "files_skipped": files_skipped,
            "chunks_added": chunks_added,
            "total_in_collection": collection.count(),
        }

    def index_all(self, incremental: bool = True) -> dict:
        """Index all collections."""
        results = {}
        total_files = 0
        total_chunks = 0

        for name in COLLECTIONS:
            print(f"  Indexing {name}...")
            result = self.index_collection(name, incremental=incremental)
            results[name] = result
            total_files += result.get("files_indexed", 0)
            total_chunks += result.get("chunks_added", 0)

        self.state["total_indexed"] = total_files
        self.state["total_chunks"] = total_chunks
        ts = datetime.now(timezone.utc).isoformat()
        if incremental:
            self.state["last_incremental"] = ts
        else:
            self.state["last_full_index"] = ts
        self._save_state()

        return {
            "collections": results,
            "total_files": total_files,
            "total_chunks": total_chunks,
            "incremental": incremental,
            "timestamp": ts,
        }

    # ------------------------------------------------------------------
    # Semantic Search
    # ------------------------------------------------------------------

    def search(self, query: str, collection_name: str | None = None,
               n_results: int = 10, where: dict | None = None) -> list[dict]:
        """Semantic search across collections."""
        # Embed the query
        query_embedding = self.ollama.embed("nomic-embed-text:latest", query)

        all_results: list[dict] = []

        collections_to_search = (
            [collection_name] if collection_name else list(COLLECTIONS.keys())
        )

        for col_name in collections_to_search:
            try:
                collection = self.client.get_collection(col_name)
                if collection.count() == 0:
                    continue

                kwargs: dict[str, Any] = {
                    "query_embeddings": [query_embedding],
                    "n_results": min(n_results, collection.count()),
                }
                if where:
                    kwargs["where"] = where

                results = collection.query(**kwargs)

                for i, doc_id in enumerate(results["ids"][0]):
                    all_results.append({
                        "id": doc_id,
                        "collection": col_name,
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "score": 1.0 - results["distances"][0][i],  # Cosine similarity
                    })
            except Exception:
                pass

        # Sort by score (highest first) and limit
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:n_results]

    def search_code(self, query: str, n_results: int = 5) -> list[dict]:
        """Search specifically in code collections."""
        return self.search(query, collection_name="slate_code", n_results=n_results)

    def search_docs(self, query: str, n_results: int = 5) -> list[dict]:
        """Search specifically in documentation."""
        return self.search(query, collection_name="slate_docs", n_results=n_results)

    def find_similar_code(self, code_snippet: str, n_results: int = 5) -> list[dict]:
        """Find code similar to a given snippet."""
        return self.search(code_snippet, collection_name="slate_code",
                          n_results=n_results)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get ChromaDB status."""
        try:
            collections = self.list_collections()
            total_docs = sum(c["count"] for c in collections)

            # Check Ollama embedding model
            ollama_ok = False
            try:
                ollama_ok = self.ollama.is_running()
            except Exception:
                pass

            return {
                "available": True,
                "db_path": str(self.db_path),
                "db_size_mb": round(
                    sum(f.stat().st_size for f in self.db_path.rglob("*") if f.is_file())
                    / (1024 * 1024), 1
                ) if self.db_path.exists() else 0,
                "collections": collections,
                "total_documents": total_docs,
                "embedding_model": "nomic-embed-text:latest",
                "embedding_available": ollama_ok,
                "last_full_index": self.state.get("last_full_index"),
                "last_incremental": self.state.get("last_incremental"),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def print_status(self):
        """Print human-readable status."""
        status = self.get_status()

        print()
        print("=" * 60)
        print("  SLATE ChromaDB Vector Store")
        print("=" * 60)
        print()

        if not status.get("available"):
            print(f"  Status: ERROR - {status.get('error', 'unknown')}")
            print()
            return

        print(f"  Status:     Active")
        print(f"  Storage:    {status['db_path']}")
        print(f"  Size:       {status['db_size_mb']} MB")
        print(f"  Documents:  {status['total_documents']}")
        print(f"  Embeddings: {'✓' if status['embedding_available'] else '✗'} {status['embedding_model']}")
        print()

        if status["collections"]:
            print("  Collections:")
            for col in status["collections"]:
                desc = COLLECTIONS.get(col["name"], {}).get("description", "")
                print(f"    {col['name']}: {col['count']} docs — {desc}")
        else:
            print("  Collections: None (run --index to build)")

        if status.get("last_full_index"):
            print(f"\n  Last Full Index:    {status['last_full_index']}")
        if status.get("last_incremental"):
            print(f"  Last Incremental:   {status['last_incremental']}")

        print()
        print("=" * 60)
        print()


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SLATE ChromaDB Vector Store")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--index", action="store_true", help="Index codebase")
    parser.add_argument("--full-index", action="store_true", help="Full re-index (not incremental)")
    parser.add_argument("--search", type=str, help="Semantic search query")
    parser.add_argument("--collection", type=str, help="Search in specific collection")
    parser.add_argument("--n", type=int, default=5, help="Number of results")
    parser.add_argument("--reset", action="store_true", help="Reset all collections")
    args = parser.parse_args()

    db = SlateChromaDB()

    if args.reset:
        print("Resetting all ChromaDB collections...")
        db.reset_all()
        print("Done.")

    elif args.index or args.full_index:
        incremental = not args.full_index
        mode = "incremental" if incremental else "full"
        print(f"Building {mode} codebase index...")
        result = db.index_all(incremental=incremental)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n  Indexed {result['total_files']} files, {result['total_chunks']} chunks")
            for name, r in result["collections"].items():
                print(f"    {name}: {r['files_indexed']} new, {r.get('files_skipped', 0)} skipped, {r['total_in_collection']} total")
            print()

    elif args.search:
        results = db.search(
            args.search,
            collection_name=args.collection,
            n_results=args.n,
        )
        if args.json:
            # Trim documents for JSON output
            for r in results:
                r["document"] = r["document"][:200] + "..." if len(r["document"]) > 200 else r["document"]
            print(json.dumps(results, indent=2))
        else:
            print(f"\n  Search: \"{args.search}\"")
            print(f"  Results: {len(results)}\n")
            for i, r in enumerate(results, 1):
                score = r["score"]
                meta = r["metadata"]
                doc_preview = r["document"][:120].replace("\n", " ")
                print(f"  [{i}] {meta['file_path']} (chunk {meta['chunk_index']}) — score: {score:.3f}")
                print(f"      {doc_preview}...")
                print()

    elif args.status or args.json:
        if args.json:
            print(json.dumps(db.get_status(), indent=2))
        else:
            db.print_status()

    else:
        db.print_status()


if __name__ == "__main__":
    main()
