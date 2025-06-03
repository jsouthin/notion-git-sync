"""
Notion Git Sync - A tool to synchronize Notion pages to markdown files.

This package provides functionality to:
1. Convert Notion pages to markdown
2. Handle YAML frontmatter
3. Support nested content and rich block types
4. Integrate with Git for change tracking
"""

from .sync import NotionSync, Config
from .converter import MarkdownConverter
from .frontmatter import FrontmatterHandler

__version__ = "0.1.0"
__all__ = ["NotionSync", "Config", "MarkdownConverter", "FrontmatterHandler"]
