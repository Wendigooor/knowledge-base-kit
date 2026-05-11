"""Git synchronisation for Knowledge Base Kit.

Handles pushing/pulling document snapshots to/from a Git remote,
conflict detection and automatic conflict resolution.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from kbk.config import KBKConfig
from kbk.document import Document
from kbk.exceptions import ConflictError, SyncError

try:
    import pygit2
    PYGIT2_AVAILABLE = True
except ImportError:
    PYGIT2_AVAILABLE = False


class SyncManager:
    """Manages Git-based synchronisation of the knowledge base.

    The synchronisation works by dumping all documents as JSON files
    in a temporary directory, committing them to a Git repository,
    and pushing to a remote.
    """

    def __init__(self, config: Optional[KBKConfig] = None):
        """Initialise with optional config.

        Args:
            config: KBKConfig instance.
        """
        self.config = config or KBKConfig()
        self._repo: Optional[pygit2.Repository] = None

    def _ensure_pygit2(self) -> None:
        """Check that pygit2 is installed."""
        if not PYGIT2_AVAILABLE:
            raise SyncError(
                "pygit2 is required for Git sync. "
                "Install it with: pip install pygit2"
            )

    def _get_or_init_repo(self) -> pygit2.Repository:
        """Get or initialise the Git repository."""
        if self._repo is not None:
            return self._repo

        self._ensure_pygit2()
        repo_path = Path(self.config.repo_path)
        repo_path.mkdir(parents=True, exist_ok=True)

        git_dir = repo_path / ".git"
        if git_dir.exists():
            try:
                self._repo = pygit2.Repository(str(repo_path))
            except Exception as exc:
                raise SyncError(
                    f"Failed to open repository at {repo_path}: {exc}"
                ) from exc
        else:
            try:
                self._repo = pygit2.init_repository(str(repo_path), bare=False)
            except Exception as exc:
                raise SyncError(
                    f"Failed to initialise repository at {repo_path}: {exc}"
                ) from exc

        return self._repo

    def _export_documents(
        self,
        documents: list[Document],
        export_dir: Path,
    ) -> None:
        """Export documents as JSON files into a directory for git tracking."""
        export_dir.mkdir(parents=True, exist_ok=True)
        for doc in documents:
            doc_path = export_dir / f"{doc.id}.json"
            doc_path.write_text(
                json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _import_documents(self, import_dir: Path) -> list[Document]:
        """Import documents from JSON files in a directory."""
        docs = []
        if not import_dir.exists():
            return docs
        for json_file in sorted(import_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                docs.append(Document.from_dict(data))
            except (json.JSONDecodeError, KeyError) as exc:
                raise SyncError(
                    f"Corrupt document file {json_file.name}: {exc}"
                ) from exc
        return docs

    def push_to_git(
        self,
        documents: list[Document],
        message: Optional[str] = None,
    ) -> str:
        """Export documents and push to Git remote.

        Documents are exported as individual JSON files, committed
        to the local repository, and pushed to the configured remote.

        Args:
            documents: List of Document instances to sync.
            message: Optional commit message. Auto-generated if omitted.

        Returns:
            The commit hash.
        """
        repo = self._get_or_init_repo()
        commit_msg = message or (
            f"KBK sync: {len(documents)} documents — "
            f"{datetime.now(timezone.utc).isoformat()}"
        )

        # Write documents into the repo working directory
        export_path = Path(repo.workdir) / "documents"
        self._export_documents(documents, export_path)

        # Stage all changes
        try:
            index = repo.index
            index.add_all()
            index.write()

            tree = index.write_tree()
            author = pygit2.Signature(
                "KBK Sync", "kbk@knowledge-base-kit.local"
            )
            committer = author

            if repo.head_is_unborn:
                parents = []
            else:
                parents = [repo.head.target]

            oid = repo.create_commit(
                "refs/heads/" + self.config.git_branch,
                author,
                committer,
                commit_msg,
                tree,
                parents,
            )
        except Exception as exc:
            raise SyncError(f"Git commit failed: {exc}") from exc

        # Push to remote if configured
        if self.config.git_remote_url:
            self._push_to_remote(repo)

        return str(oid)

    def _push_to_remote(self, repo: pygit2.Repository) -> None:
        """Push to the configured remote."""
        try:
            # Ensure remote exists
            remotes = [r.name for r in repo.remotes]
            remote_name = "origin"

            if remote_name not in remotes:
                repo.remotes.create(
                    remote_name,
                    self.config.git_remote_url,
                )

            remote = repo.remotes[remote_name]
            remote.push(
                [f"refs/heads/{self.config.git_branch}:refs/heads/{self.config.git_branch}"],
            )
        except Exception as exc:
            raise SyncError(f"Git push failed: {exc}") from exc

    def pull_from_git(self) -> list[Document]:
        """Pull documents from Git remote and return them.

        Fetches from remote, merges/rebases, and reads document JSON files
        from the repository working directory.

        Returns:
            List of Document instances imported from the repository.

        Raises:
            SyncError: If git operations fail.
        """
        repo = self._get_or_init_repo()

        if self.config.git_remote_url:
            try:
                remotes = [r.name for r in repo.remotes]
                if "origin" not in remotes:
                    repo.remotes.create("origin", self.config.git_remote_url)

                remote = repo.remotes["origin"]
                remote.fetch()

                # Merge fetched branch
                remote_branch = f"refs/remotes/origin/{self.config.git_branch}"
                if remote_branch in repo.references:
                    remote_commit = repo.references[remote_branch].target
                    repo.merge(remote_commit)
            except Exception as exc:
                raise SyncError(f"Git pull failed: {exc}") from exc

        # Import documents from the repo working directory
        export_path = Path(repo.workdir) / "documents"
        return self._import_documents(export_path)

    def detect_conflicts(
        self,
        local_docs: list[Document],
        remote_docs: list[Document],
    ) -> list[dict]:
        """Detect conflicts between local and remote document sets.

        A conflict occurs when the same document ID exists in both
        sets with different content and the local version is not
        strictly newer or older than the remote version.

        Args:
            local_docs: Documents from the local store.
            remote_docs: Documents pulled from the remote.

        Returns:
            List of conflict descriptors:
              { "doc_id": str, "local_version": int,
                "remote_version": int, "auto_resolved": bool }
        """
        local_map = {d.id: d for d in local_docs}
        remote_map = {d.id: d for d in remote_docs}
        conflicts: list[dict] = []

        common_ids = set(local_map.keys()) & set(remote_map.keys())
        for doc_id in common_ids:
            local = local_map[doc_id]
            remote = remote_map[doc_id]

            if local.content == remote.content and local.tags == remote.tags:
                continue  # Identical — no conflict

            # Auto-resolve: keep the version with higher version number
            if remote.version > local.version:
                # Remote is newer: mark for auto-resolve (use remote)
                conflicts.append({
                    "doc_id": doc_id,
                    "local_version": local.version,
                    "remote_version": remote.version,
                    "auto_resolved": True,
                    "resolved_content": remote.content,
                    "resolved_tags": list(remote.tags),
                    "resolved_metadata": dict(remote.metadata),
                })
            elif local.version > remote.version:
                # Local is newer
                conflicts.append({
                    "doc_id": doc_id,
                    "local_version": local.version,
                    "remote_version": remote.version,
                    "auto_resolved": True,
                    "resolved_content": local.content,
                    "resolved_tags": list(local.tags),
                    "resolved_metadata": dict(local.metadata),
                })
            else:
                # Same version, different content — real conflict
                conflicts.append({
                    "doc_id": doc_id,
                    "local_version": local.version,
                    "remote_version": remote.version,
                    "auto_resolved": False,
                    "local_content": local.content,
                    "remote_content": remote.content,
                    "local_tags": list(local.tags),
                    "remote_tags": list(remote.tags),
                })

        # New documents on either side are not conflicts
        return conflicts

    def resolve_conflict(
        self,
        conflict: dict,
        resolution: str = "local",
    ) -> Optional[Document]:
        """Resolve a single conflict manually.

        Args:
            conflict: Conflict descriptor from detect_conflicts().
            resolution: One of "local", "remote", or a custom content string.

        Returns:
            A Document with the resolved content, or None if auto-resolved.

        Raises:
            ConflictError: If resolution mode is invalid.
        """
        if conflict.get("auto_resolved"):
            # Already auto-resolved
            return None

        doc_id = conflict["doc_id"]

        if resolution == "local":
            return Document(
                id=doc_id,
                version=conflict["local_version"],
                content=conflict["local_content"],
                tags=conflict["local_tags"],
            )
        elif resolution == "remote":
            return Document(
                id=doc_id,
                version=conflict["remote_version"],
                content=conflict["remote_content"],
                tags=conflict["remote_tags"],
            )
        else:
            # Custom content string provided
            return Document(
                id=doc_id,
                version=max(
                    conflict["local_version"],
                    conflict["remote_version"],
                ) + 1,
                content=resolution,
            )

    def status(self) -> dict:
        """Get the current sync status of the repository.

        Returns:
            Dict with 'ahead', 'behind', 'dirty', and 'last_commit' keys.
        """
        repo = self._get_or_init_repo()
        result: dict = {
            "ahead": 0,
            "behind": 0,
            "dirty": False,
            "last_commit": None,
        }

        # Check if working directory is dirty
        try:
            status = repo.status()
            result["dirty"] = any(
                s in (
                    pygit2.GIT_STATUS_WT_MODIFIED,
                    pygit2.GIT_STATUS_WT_NEW,
                    pygit2.GIT_STATUS_WT_DELETED,
                )
                for s in status.values()
            )
        except Exception:
            pass

        # Get last commit info
        try:
            if not repo.head_is_unborn:
                commit = repo.revparse_single("HEAD")
                result["last_commit"] = {
                    "hash": str(commit.id),
                    "message": commit.message.strip(),
                    "time": str(commit.commit_time),
                }
        except Exception:
            pass

        # Check ahead/behind via remote tracking if available
        try:
            branch_name = self.config.git_branch
            branch = repo.lookup_branch(branch_name)
            if branch and branch.upstream:
                ahead_behind = repo.ahead_behind(
                    branch.target,
                    branch.upstream.target,
                )
                result["ahead"] = ahead_behind[0]
                result["behind"] = ahead_behind[1]
        except Exception:
            pass

        return result
