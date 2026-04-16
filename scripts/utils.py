"""Shared utilities for setup scripts."""


def print_header(title: str) -> None:
    """Print a formatted CLI section header."""
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()
