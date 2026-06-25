#!/usr/bin/env python3
"""
knowledge_base.py
==================
Layer B - Knowledge Base (RAG)

Gestisce la "memoria che cresce ogni giorno" dell'agente:
  - Calcola embedding dei documenti usando Ollama (nomic-embed-text)
  - Li salva in Qdrant (vector DB locale)
  - Permette ricerca semantica: "trovami i pattern più simili a X"

Questo NON fa training del modello. È un indice ricercabile che
l'agente di reasoning (Claude via API) consulterà prima di analizzare
un componente APK.

Uso da riga di comando:
    python3 knowledge_base.py init
    python3 knowledge_base.py add --text "..." --source "..." --category "..." --cwe "..."
    python3 knowledge_base.py search --query "..."
    python3 knowledge_base.py stats
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "vuln_knowledge"


# ---------------------------------------------------------------------------
# Embedding via Ollama
# ---------------------------------------------------------------------------

def get_embedding(text: str) -> list[float]:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    embedding = data.get("embedding")
    if not embedding:
        raise RuntimeError(f"Ollama non ha restituito un embedding valido: {data}")
    return embedding


# ---------------------------------------------------------------------------
# Qdrant client
# ---------------------------------------------------------------------------

def get_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def init_collection() -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        print(f"[*] Collection '{COLLECTION_NAME}' già esistente, nessuna azione.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
    )
    print(f"[✓] Collection '{COLLECTION_NAME}' creata (dim={EMBED_DIM}, cosine).")


def stable_id(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:15], 16)


def add_document(
    text: str,
    source: str,
    category: str | None = None,
    cwe: str | None = None,
    extra_metadata: dict | None = None,
) -> None:
    client = get_client()
    embedding = get_embedding(text)

    payload = {
        "text": text,
        "source": source,
        "category": category,
        "cwe": cwe,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_metadata:
        payload.update(extra_metadata)

    point_id = stable_id(text)
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=embedding, payload=payload)],
    )
    print(f"[✓] Documento aggiunto (id={point_id}, source={source}, category={category})")


def search(query: str, top_k: int = 5, category: str | None = None) -> list[dict]:
    client = get_client()
    query_vector = get_embedding(query)

    query_filter = None
    if category:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category))]
        )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        query_filter=query_filter,
    ).points

    output = []
    for r in results:
        output.append({
            "score": round(r.score, 4),
            "text": r.payload.get("text"),
            "source": r.payload.get("source"),
            "category": r.payload.get("category"),
            "cwe": r.payload.get("cwe"),
        })
    return output


def collection_stats() -> dict:
    client = get_client()
    info = client.get_collection(COLLECTION_NAME)
    return {
        "points_count": info.points_count
        
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Knowledge Base RAG per l'agente di analisi APK")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Crea la collection Qdrant (una sola volta)")
    sub.add_parser("stats", help="Mostra statistiche della collection")

    add_p = sub.add_parser("add", help="Aggiunge un documento alla KB")
    add_p.add_argument("--text", required=True)
    add_p.add_argument("--source", required=True)
    add_p.add_argument("--category", default=None)
    add_p.add_argument("--cwe", default=None)

    search_p = sub.add_parser("search", help="Cerca documenti simili")
    search_p.add_argument("--query", required=True)
    search_p.add_argument("--top-k", type=int, default=5)
    search_p.add_argument("--category", default=None)

    args = parser.parse_args()

    if args.command == "init":
        init_collection()

    elif args.command == "stats":
        stats = collection_stats()
        print(json.dumps(stats, indent=2))

    elif args.command == "add":
        add_document(
            text=args.text,
            source=args.source,
            category=args.category,
            cwe=args.cwe,
        )

    elif args.command == "search":
        results = search(args.query, top_k=args.top_k, category=args.category)
        if not results:
            print("Nessun risultato trovato.")
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] score={r['score']}  source={r['source']}  category={r['category']}  cwe={r['cwe']}")
            print(f"    {r['text']}")


if __name__ == "__main__":
    main()
