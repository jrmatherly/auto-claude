"""
Data Models for Task Context
=============================

Core data structures for representing file matches and task context.
"""

from dataclasses import dataclass, field


@dataclass
class FileMatch:
    """A file that matched the search criteria."""

    path: str
    service: str
    reason: str
    relevance_score: float = 0.0
    matching_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class MultiRepoContext:
    """Context for multi-repository workspaces.

    Loaded from .auto-claude/repo_mapping.json to provide cross-repo awareness.
    """

    workspace_root: str = ""
    repos: dict[str, dict] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    cross_repo_patterns: dict[str, dict] = field(default_factory=dict)
    worktree_strategy: dict[str, str] = field(default_factory=dict)

    def get_dependent_repos(self, repo_name: str) -> list[str]:
        """Get repos that depend on the given repo."""
        dependents = []
        for repo, deps in self.dependencies.items():
            if repo_name in deps:
                dependents.append(repo)
        return dependents

    def get_cross_repo_impact(self, repo_name: str) -> list[dict]:
        """Get cross-repo patterns that involve the given repo."""
        impacts = []
        for pattern_name, pattern_info in self.cross_repo_patterns.items():
            if repo_name in pattern_info.get("repos", []):
                impacts.append({"pattern": pattern_name, **pattern_info})
        return impacts


@dataclass
class TaskContext:
    """Complete context for a task."""

    task_description: str
    scoped_services: list[str]
    files_to_modify: list[dict]
    files_to_reference: list[dict]
    patterns_discovered: dict[str, str]
    service_contexts: dict[str, dict]
    graph_hints: list[dict] = field(
        default_factory=list
    )  # Historical hints from Graphiti
    multi_repo_context: MultiRepoContext | None = None  # Multi-repo workspace context
