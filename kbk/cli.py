"""CLI for Knowledge Base Kit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from kbk.config import KBKConfig
from kbk.document import Document
from kbk.exceptions import StoreError, DocumentError, VersioningError, SyncError
from kbk.store import KnowledgeStore
from kbk.versioning import VersionManager
from kbk.sync import SyncManager


def _handle_error(func):
    """Decorator: wrap CLI commands in try/except for domain exceptions."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (StoreError, DocumentError, VersioningError, SyncError) as e:
            click.echo(f"❌ {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Unexpected error: {e}", err=True)
            sys.exit(1)
    return wrapper


@click.group()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--path", "-p", default=None, help="Knowledge base root path")
@click.pass_context
def cli(ctx: click.Context, config: str | None, path: str | None):
    """Knowledge Base Kit — vector knowledge base with versioning and sync."""
    ctx.ensure_object(dict)
    cfg = KBKConfig.load(config) if config else KBKConfig()
    if path:
        cfg.db_path = path
        cfg.export_path = os.path.join(path, "exports")
    ctx.obj["config"] = cfg
    ctx.obj["store"] = KnowledgeStore(cfg)
    ctx.obj["versioning"] = VersionManager(config=cfg)
    ctx.obj["sync"] = SyncManager(cfg)


@cli.command()
@click.pass_context
@_handle_error
def init(ctx: click.Context):
    """Initialize a new knowledge base."""
    cfg: KBKConfig = ctx.obj["config"]
    store: KnowledgeStore = ctx.obj["store"]
    sync_mgr: SyncManager = ctx.obj["sync"]
    os.makedirs(cfg.db_path, exist_ok=True)
    os.makedirs(cfg.export_path, exist_ok=True)
    store._init_client()
    sync_mgr._get_or_init_repo()
    click.echo(f"✅ Knowledge base initialized at {cfg.db_path}")


@cli.command()
@click.option("--collection", "-c", default="default", help="Collection name")
@click.option("--id", "doc_id", default=None, help="Document ID (auto-generated if not set)")
@click.option("--content", "-t", required=True, help="Document content")
@click.option("--tag", "-g", multiple=True, default=None, help="Tags")
@click.option("--metadata", "-m", default=None, help="JSON metadata")
@click.pass_context
@_handle_error
def add(ctx: click.Context, collection: str, doc_id: str | None, content: str, tag: tuple[str, ...] | None, metadata: str | None):
    """Add a document to the knowledge base."""
    store: KnowledgeStore = ctx.obj["store"]
    versioning: VersionManager = ctx.obj["versioning"]

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            click.echo("❌ Invalid JSON metadata", err=True)
            sys.exit(1)

    doc = Document(
        id=doc_id or os.urandom(8).hex(),
        version=1,
        tags=list(tag) if tag else [],
        metadata=meta,
        content=content,
        collection=collection,
    )
    store.add(doc)
    versioning.save_snapshot(doc)
    click.echo(f"✅ Added document {doc.id} to '{collection}'")


@cli.command()
@click.argument("query")
@click.option("--collection", "-c", default=None, help="Filter by collection")
@click.option("--limit", "-n", default=10, help="Max results")
@click.pass_context
@_handle_error
def search(ctx: click.Context, query: str, collection: str | None, limit: int):
    """Search documents by semantic similarity."""
    store: KnowledgeStore = ctx.obj["store"]
    results = store.search(query, n_results=limit, collection_filter=collection)
    if not results:
        click.echo("No results found.")
        return
    for doc in results:
        tags = f" [{', '.join(doc.tags)}]" if doc.tags else ""
        click.echo(f"  [{doc.collection}] {doc.id} v{doc.version}{tags}")
        click.echo(f"    {doc.content[:150]}..." if len(doc.content) > 150 else f"    {doc.content}")
        click.echo()


@cli.command()
@click.pass_context
@_handle_error
def sync(ctx: click.Context):
    """Synchronize with remote git repository."""
    sync_mgr: SyncManager = ctx.obj["sync"]
    store: KnowledgeStore = ctx.obj["store"]
    cfg: KBKConfig = ctx.obj["config"]

    # Export all documents to JSON
    all_docs = []
    for col in store.list_collections():
        all_docs.extend(store.list_documents(collection=col, limit=999999))
    store.export_to_json(os.path.join(cfg.export_path, "chromadb-export.json"))
    push_result = sync_mgr.push_to_git(all_docs)
    
    # Pull remote changes
    pulled = sync_mgr.pull_from_git()
    
    # Import remote documents that don't conflict
    conflicts = []
    for doc in pulled:
        try:
            store.add(doc)
        except ValueError as e:
            conflicts.append({"doc": doc, "error": str(e)})
    
    if conflicts:
        click.echo(f"⚠️  {len(conflicts)} conflict(s) detected:")
        for c in conflicts:
            click.echo(f"  ❌ {c['doc'].id}: {c['error']}")
        click.echo("  Run 'kbk sync --resolve' to auto-resolve")
    else:
        click.echo("✅ Sync complete")


@cli.command()
@click.option("--collection", "-c", default=None)
@click.option("--id", "doc_id", default=None)
@click.pass_context
@_handle_error
def history(ctx: click.Context, collection: str | None, doc_id: str | None):
    """Show version history for documents."""
    versioning: VersionManager = ctx.obj["versioning"]
    if doc_id:
        try:
            history = versioning.get_history(doc_id)
            if not history:
                click.echo("No history found.")
                return
            click.echo(f"History for {doc_id}:")
            for h in history:
                click.echo(f"  v{h['version']} — {h.get('updated_at', h.get('created_at', '?'))}")
        except Exception as e:
            click.echo(f"❌ {e}")
    else:
        click.echo("Use: kbk history --id <doc-id>")


@cli.command()
@click.option("--collection", "-c", required=True)
@click.option("--id", "doc_id", required=True)
@click.option("--version", "-v", required=True, type=int)
@click.pass_context
@_handle_error
def rollback(ctx: click.Context, collection: str, doc_id: str, version: int):
    """Rollback a document to a previous version."""
    store: KnowledgeStore = ctx.obj["store"]
    versioning: VersionManager = ctx.obj["versioning"]

    doc = store.get(doc_id, collection)
    if doc is None:
        click.echo(f"❌ Document {collection}/{doc_id} not found")
        return

    restored = versioning.rollback(doc, version)
    if restored:
        store.update(restored)
        click.echo(f"✅ Rolled back {collection}/{doc_id} to v{version}")
    else:
        click.echo(f"❌ Version {version} not found for {collection}/{doc_id}")


@cli.command()
@click.pass_context
@_handle_error
def status(ctx: click.Context):
    """Show knowledge base status."""
    store: KnowledgeStore = ctx.obj["store"]
    sync_mgr: SyncManager = ctx.obj["sync"]
    versioning: VersionManager = ctx.obj["versioning"]
    cfg: KBKConfig = ctx.obj["config"]

    click.echo("📊 Knowledge Base Status")
    click.echo(f"  Path: {cfg.db_path}")
    click.echo(f"  Collections:")
    for col in store.list_collections():
        click.echo(f"    📁 {col}: {store.count(col)} docs")

    click.echo(f"  Git repo: {'✅ synced' if sync_mgr._get_or_init_repo() else '❌ not initialized'}")
    click.echo(f"  Snapshot count: {versioning.snapshot_count()}")
    
    # Check export freshness
    export_path = os.path.join(cfg.export_path, "chromadb-export.json")
    if os.path.exists(export_path):
        mtime = os.path.getmtime(export_path)
        from datetime import datetime
        click.echo(f"  Last export: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}")
    else:
        click.echo("  Last export: never")


@cli.command()
@click.option("--export-path", default=None, help="Output path for the exported JSON")
@click.pass_context
@_handle_error
def export(ctx: click.Context, export_path: str | None):
    """Export all documents to JSON."""
    store: KnowledgeStore = ctx.obj["store"]
    path = export_path or os.path.join(ctx.obj["config"].export_path, "chromadb-export.json")
    count = store.export_to_json(path)
    click.echo(f"✅ Exported {count} documents to {path}")


@cli.command()
@click.option("--seed-file", default=None, help="JSON file to seed from")
@click.pass_context
@_handle_error
def seed(ctx: click.Context, seed_file: str | None):
    """Seed/restore the knowledge base from a JSON export."""
    store: KnowledgeStore = ctx.obj["store"]
    path = seed_file or os.path.join(ctx.obj["config"].export_path, "chromadb-export.json")
    if not os.path.exists(path):
        click.echo(f"❌ Seed file not found: {path}", err=True)
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    # data is {exported_at: str, collections: {name: [...]}}
    total = 0
    for col_name, docs in data.get("collections", data.items()):
        if col_name == "exported_at":
            continue
        if not isinstance(docs, list):
            continue
        for doc_data in docs:
            if isinstance(doc_data, dict) and "content" in doc_data:
                doc = Document(
                    id=doc_data.get("id", os.urandom(8).hex()),
                    version=doc_data.get("version", 1),
                    tags=doc_data.get("tags", []),
                    metadata=doc_data.get("metadata", {}),
                    content=doc_data["content"],
                    collection=doc_data.get("collection", col_name),
                    created_at=doc_data.get("created_at", ""),
                    updated_at=doc_data.get("updated_at", ""),
                )
                try:
                    store.add(doc)
                    total += 1
                except Exception:
                    pass
    click.echo(f"✅ Seeded {total} documents from {path}")


if __name__ == "__main__":
    cli()
