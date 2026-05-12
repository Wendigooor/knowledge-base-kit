"""CLI for KBK v0.2 — Enterprise Semantic Index with Pull + Allowlist."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from kbk.config import KBKConfig, load_targets
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer
from kbk.mcp_server import KBKMCPServer
from kbk.showcase import ShowcaseBuilder
from kbk.exceptions import StoreError


console = Console()

def _handle_error(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            sys.exit(130)
        except StoreError as e:
            console.print(f"[red]❌ Store error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)
    return wrapper


@click.group()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.pass_context
def cli(ctx, config):
    """KBK v0.2 — Enterprise Semantic Index. Pull + Allowlist."""
    ctx.ensure_object(dict)
    cfg = KBKConfig.load(config)
    ctx.obj["config"] = cfg

    # Ensure base dirs
    base = Path.home() / ".kbk"
    base.mkdir(parents=True, exist_ok=True)

    ctx.obj["store"] = KnowledgeStore(cfg)
    ctx.obj["state"] = StateTracker(cfg.state_path)
    ctx.obj["indexer"] = Indexer(
        ctx.obj["store"], ctx.obj["state"],
        llm_api_key=cfg.llm_api_key,
        llm_model=cfg.llm_model,
        llm_base_url=cfg.llm_base_url,
    )


@cli.command()
@_handle_error
def init():
    """Initialize KBK: create dirs, ChromaDB, state tracker, sample config."""
    base = Path.home() / ".kbk"
    base.mkdir(parents=True, exist_ok=True)

    # Create sample targets file
    targets_path = base / "targets.yaml"
    if not targets_path.exists():
        targets_path.write_text("""# KBK whitelisted sources
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved'"
    access_group: "public"
""")
    # Init ChromaDB
    cfg = KBKConfig()
    store = KnowledgeStore(cfg)
    store._init_client()
    # Init state tracker
    StateTracker(cfg.state_path)

    console.print(f"[green]✅[/green] KBK initialized at ~/.kbk/")
    console.print(f"  ChromaDB: {cfg.db_path}")
    console.print(f"  State tracker: {cfg.state_path}")
    console.print(f"  Targets: {cfg.targets_path}")
    console.print(f"\nRun [bold]kbk sync[/bold] to index your first documents.")
    console.print(f"Run [bold]kbk serve[/bold] to start MCP server for LLMs.")
    console.print(f"Run [bold]kbk build-showcase[/bold] to generate Confluence showcase.")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be indexed without doing it")
@_handle_error
def sync(dry_run: bool):
    """Pull whitelisted sources, diff, ETL, embed — full pipeline."""
    cfg: KBKConfig = click.get_current_context().obj["config"]
    store: KnowledgeStore = click.get_current_context().obj["store"]
    state: StateTracker = click.get_current_context().obj["state"]
    indexer: Indexer = click.get_current_context().obj["indexer"]

    targets = load_targets(cfg.targets_path)
    if not targets:
        console.print("[yellow]⚠️[/yellow] No targets configured. Edit ~/.kbk/targets.yaml")
        return

    console.print("[bold]🔍 KBK Sync[/bold]")
    console.print(f"  Targets: {len(targets)} sources")
    console.print(f"  Dry run: {'yes' if dry_run else 'no'}")
    console.print()

    total_new = 0
    total_skipped = 0
    total_chunks = 0

    for t in targets:
        source_type = t.get("type", "unknown")
        location = t.get("location", "?")
        console.print(f"[bold]── {source_type.upper()}: {location}[/bold]")

        if source_type == "confluence":
            from kbk.connectors.confluence import ConfluenceConnector
            connector = ConfluenceConnector(
                base_url=cfg.confluence_url,
                token=cfg.confluence_token,
                state=state,
            )
            from kbk.models import SourceTarget
            target = SourceTarget(
                type="confluence", location=location,
                filter_query=t.get("filter_query", ""),
                access_group=t.get("access_group", "public"),
            )
            pages = connector.process_target(target)

            if not pages:
                console.print(f"  [dim]No new/changed documents[/dim]")
                continue

            console.print(f"  Found {len(pages)} new/changed documents")

            for page in pages:
                if dry_run:
                    console.print(f"  [dim]📄 Would index: {page['title']}[/dim]")
                    total_new += 1
                    continue

                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                    console=console, transient=True,
                ) as progress:
                    progress.add_task(f"  Indexing: {page['title'][:50]}...", total=None)
                    chunks = indexer.process_document(
                        url=page["url"],
                        raw_html=page["body"],
                        title=page["title"],
                        access_group=page.get("access_group", "public"),
                        collection=location.lower(),
                        content_hash=page["content_hash"],
                    )
                    state.mark_indexed(page["url"], page["content_hash"], [c.id for c in chunks])
                    total_chunks += len(chunks)
                    total_new += 1

            if not dry_run:
                console.print(f"  [green]✅ {len(pages)} indexed → {total_chunks} chunks[/green]")

        elif source_type == "gitlab":
            console.print("  [dim]GitLab connector: coming in v0.3[/dim]")
        else:
            console.print(f"  [red]Unknown source type: {source_type}[/red]")

    console.print()
    cost = indexer.total_cost_estimate
    console.print("[bold]📊 Sync Summary[/bold]")
    console.print(f"  New/changed: {total_new}")
    console.print(f"  Skipped (cached): {total_skipped}")
    console.print(f"  Chunks created: {total_chunks}")
    if cost["prompt_tokens"] > 0:
        console.print(f"  LLM cost: ${cost['estimated_cost_usd']:.4f} ({cost['prompt_tokens']} prompt + {cost['completion_tokens']} completion tokens)")


@cli.command()
@click.option("--port", default=None, help="MCP server port (default: stdio)")
@_handle_error
def serve(port: str = None):
    """Start MCP server for LLM access to the knowledge index.

    Without --port: uses stdio transport (for Claude Desktop, Cursor).
    With --port: starts HTTP server (for remote access).
    """
    store: KnowledgeStore = click.get_current_context().obj["store"]
    server = KBKMCPServer(store)

    if port:
        console.print(f"[green]✅[/green] MCP server starting on port {port}")
        from http.server import HTTPServer, BaseHTTPRequestHandler
        # Simple HTTP wrapper would go here
        console.print("[yellow]⚠️[/yellow] HTTP mode coming in v0.3. Use stdio for now.")
        return

    console.print("[green]✅[/green] MCP server started (stdio)")
    console.print("  Connect from Claude Desktop or Cursor:")
    console.print(f"  {sys.executable} -m kbk.cli serve")
    console.print()
    server.run()


@cli.command()
@click.option("--output", "-o", default="confluence", type=click.Choice(["confluence", "markdown"]),
              help="Output format for the showcase")
@_handle_error
def build_showcase(output: str):
    """Generate Read-Only knowledge showcase (Confluence page or Markdown)."""
    cfg: KBKConfig = click.get_current_context().obj["config"]
    store: KnowledgeStore = click.get_current_context().obj["store"]
    builder = ShowcaseBuilder(store, cfg)

    stats = store.get_stats()
    if stats["total"] == 0:
        console.print("[yellow]⚠️[/yellow] Index is empty. Run [bold]kbk sync[/bold] first.")
        return

    if output == "confluence":
        if not cfg.confluence_url or not cfg.confluence_token:
            console.print("[red]❌[/red] Confluence not configured. Set confluence_url and confluence_token in config.")
            console.print("  Trying markdown output instead...")
            output = "markdown"
        else:
            url = builder.build()
            console.print(f"[green]✅[/green] Showcase published to Confluence")
            console.print(f"  {url}")

    if output == "markdown":
        md = builder.build_markdown()
        path = Path.home() / ".kbk" / "showcase.md"
        path.write_text(md, encoding="utf-8")
        console.print(f"[green]✅[/green] Showcase saved to {path}")
        console.print()
        # Show preview
        lines = md.split("\n")
        for l in lines[:20]:
            console.print(l)


@cli.command()
@click.argument("query")
@click.option("--collection", "-c", default=None)
@click.option("--limit", "-n", default=10)
@_handle_error
def search(query: str, collection: str = None, limit: int = 10):
    """Semantic search across the knowledge index."""
    store: KnowledgeStore = click.get_current_context().obj["store"]
    results = store.search(query, n_results=limit, collection_filter=collection)
    if not results:
        console.print("No results found.")
        return
    console.print(f"[bold]🔍 Search:[/bold] {query}")
    console.print()
    for c in results:
        tags = f" [dim]{' '.join(f'#{t}' for t in c.tags[:3])}[/dim]" if c.tags else ""
        link = f" [blue]{c.source_url}[/blue]" if c.source_url else ""
        console.print(f"  {c.summary[:200]}{tags}{link}")
        console.print()


@cli.command()
@_handle_error
def status():
    """Show knowledge index status."""
    store: KnowledgeStore = click.get_current_context().obj["store"]
    state: StateTracker = click.get_current_context().obj["state"]
    stats = store.get_stats()
    state_stats = state.stats

    console.print("[bold]📊 KBK Status[/bold]")
    console.print(f"  Collections: {len(stats['collections'])}")
    for col, cnt in stats["collections"].items():
        console.print(f"    📁 {col}: {cnt} chunks")
    console.print(f"  Total chunks: {stats['total']}")
    console.print(f"  Tracked sources: {state_stats['tracked_docs']}")
    console.print(f"  State file: {state_stats['path']}")

    if stats["total"] == 0:
        console.print("\n[yellow]Index is empty. Commands:[/yellow]")
        console.print("  kbk sync    — index documents from whitelisted sources")
        console.print("  kbk serve   — start MCP server for LLMs")
        console.print("  kbk build-showcase — generate Confluence showcase")


if __name__ == "__main__":
    cli()
