"""CLI for Knowledge Base Kit v2 — Enterprise Semantic Index."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from kbk.config import KBKConfig
from kbk.document import IndexedDocument
from kbk.exceptions import StoreError, DocumentError
from kbk.store import KnowledgeStore
from kbk.indexer import Indexer


def _handle_error(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (StoreError, DocumentError) as e:
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
    """KBK — Enterprise Semantic Index. От index/1v1."""
    ctx.ensure_object(dict)
    cfg = KBKConfig.load(config) if config else KBKConfig()
    if path:
        cfg.db_path = path
    ctx.obj["config"] = cfg
    ctx.obj["store"] = KnowledgeStore(cfg)
    ctx.obj["indexer"] = Indexer(ctx.obj["store"])


@cli.command()
@click.pass_context
@_handle_error
def init(ctx: click.Context):
    """Initialize the semantic index."""
    cfg: KBKConfig = ctx.obj["config"]
    store: KnowledgeStore = ctx.obj["store"]
    os.makedirs(cfg.db_path, exist_ok=True)
    store._init_client()
    click.echo(f"✅ Knowledge index initialized at {cfg.db_path}")


@cli.command()
@click.option("--text", "-t", required=True, help="Raw text content or URL")
@click.option("--source", "-s", default="manual", help="Source type: confluence|jira|git|manual")
@click.option("--url", "-u", default="", help="Source URL")
@click.option("--collection", "-c", default="unclassified", help="Target collection")
@click.option("--tag", "-g", multiple=True, help="Tags (optional)")
@click.pass_context
@_handle_error
def index(ctx: click.Context, text: str, source: str, url: str,
          collection: str, tag: tuple[str, ...]):
    """Index a document: clean → summarize → classify → embed → store."""
    indexer: Indexer = ctx.obj["indexer"]
    metadata = {"source_type": source, "source_url": url or "manual://" + text[:40]}
    if tag:
        metadata["manual_tags"] = list(tag)

    doc = indexer.index(
        raw_text=text,
        source_url=metadata["source_url"],
        source_type=source,
        collection=collection,
        metadata=metadata,
    )
    click.echo(f"✅ Indexed {doc.id} → {collection} [{', '.join(doc.tags[:5])}]")


@cli.command()
@click.argument("query")
@click.option("--collection", "-c", default=None, help="Filter by collection")
@click.option("--limit", "-n", default=10, help="Max results")
@click.pass_context
@_handle_error
def search(ctx: click.Context, query: str, collection: str | None, limit: int):
    """Semantic search across the index."""
    store: KnowledgeStore = ctx.obj["store"]
    results = store.search(query, n_results=limit, collection_filter=collection)
    if not results:
        click.echo("No results found.")
        return
    for doc in results:
        tags = f" [{', '.join(doc.tags[:3])}]" if doc.tags else ""
        click.echo(f"  [{doc.collection}] {doc.id}{tags}")
        click.echo(f"    {doc.summary[:200]}..." if len(doc.summary) > 200 else f"    {doc.summary}")
        click.echo(f"    🔗 {doc.source_url}")
        click.echo()


@cli.command()
@click.pass_context
@_handle_error
def status(ctx: click.Context):
    """Show semantic index status."""
    store: KnowledgeStore = ctx.obj["store"]
    cfg: KBKConfig = ctx.obj["config"]

    stats = store.get_stats()
    click.echo("📊 Knowledge Index Status")
    click.echo(f"  Path: {cfg.db_path}")
    click.echo(f"  Collections:")
    if stats["total"] == 0:
        click.echo("    (empty — run 'kbk index' to add documents)")
    for col, cnt in stats["collections"].items():
        click.echo(f"    📁 {col}: {cnt} docs")
    click.echo(f"  Total: {stats['total']} documents")

    # Check export freshness
    export_path = os.path.join(cfg.export_path, "index-stats.json")
    if os.path.exists(export_path):
        from datetime import datetime
        mtime = os.path.getmtime(export_path)
        click.echo(f"  Last stats export: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}")
    else:
        click.echo("  Last stats export: never")


@cli.command()
@click.option("--source", "-s", default=None, help="Filter by source type")
@click.pass_context
@_handle_error
def connectors(ctx: click.Context, source: str | None):
    """List and manage source connectors."""
    conn_dir = Path(__file__).parent / "connectors"
    files = list(conn_dir.glob("*.py"))
    available = [f.stem for f in files if f.stem != "__init__"]

    click.echo("🔌 Available Connectors")
    if not available:
        click.echo("  No connectors installed.")
        click.echo("  Connectors available: confluence, jira, gitlab, slack")
        click.echo("  Install with: pip install kbk-[connector-name]")
        return

    for name in available:
        active = "✅" if source is None or source == name else "  "
        click.echo(f"  {active} {name}")


@cli.command()
@click.pass_context
@_handle_error
def explore(ctx: click.Context):
    """Open the Read-Only knowledge space (Confluence/Backstage)."""
    click.echo("📖 Knowledge Space")
    click.echo("  Read-Only Confluence space: https://confluence.softswiss.com/spaces/KBK")
    click.echo("  Or run: kbk search <query>")
    click.echo()
    click.echo("  Structure:")
    for col in ["architecture", "infrastructure", "business", "runbooks", "decisions", "team"]:
        click.echo(f"    📁 {col.capitalize()}")


if __name__ == "__main__":
    cli()
