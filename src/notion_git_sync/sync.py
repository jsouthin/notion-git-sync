"""
Main synchronization module for Notion to Git.

This module handles the overall sync process:
1. Walking the page hierarchy
2. Converting pages to markdown
3. Saving files
4. Staging changes in git
"""

import os
import re
import pathlib
import subprocess
from typing import List, Optional, Iterator
from dataclasses import dataclass

from notion_client import Client
from notion_client.helpers import collect_paginated_api
from notion_client.errors import APIResponseError

from .converter import MarkdownConverter
from .frontmatter import FrontmatterHandler

@dataclass
class Config:
    """Configuration for the Notion sync process.
    
    Attributes:
        notion_client: Initialized Notion API client
        parent_ids: List of parent page IDs to crawl
        output_dir: Directory to save markdown files
        required_frontmatter: Set of required YAML frontmatter keys
    """
    notion_client: Client
    parent_ids: List[str]
    output_dir: pathlib.Path
    required_frontmatter: set
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables.
        
        Required environment variables:
            NOTION_TOKEN: Integration secret (secret_* or ntn_*)
            NOTION_PARENT_IDS: Comma-separated list of parent page IDs
            
        Returns:
            Initialized Config object
        """
        token = os.environ.get("NOTION_TOKEN")
        if not token:
            raise ValueError("NOTION_TOKEN environment variable must be set")
            
        parent_ids = os.getenv("NOTION_PARENT_IDS", "").strip().split(",")
        if not parent_ids or not parent_ids[0]:
            raise ValueError("NOTION_PARENT_IDS environment variable must be set")
            
        output_dir = pathlib.Path("docs/notion")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return cls(
            notion_client=Client(auth=token),
            parent_ids=parent_ids,
            output_dir=output_dir,
            required_frontmatter={"title", "owner", "last_reviewed", "next_review_due"}
        )

class NotionSync:
    """Main class for synchronizing Notion pages to markdown files."""
    
    def __init__(self, config: Config):
        """Initialize the sync process.
        
        Args:
            config: Configuration object with settings
        """
        self.config = config
        self.frontmatter = FrontmatterHandler(config.required_frontmatter)
        self.converter = MarkdownConverter(self.frontmatter, config.notion_client)
    
    def process_page(self, page_id: str) -> Optional[pathlib.Path]:
        """Process a single Notion page and convert it to markdown.
        
        Args:
            page_id: The Notion page ID to process
            
        Returns:
            Path to the output file if created/updated, None otherwise
        """
        try:
            # Fetch page and blocks
            page = self.config.notion_client.pages.retrieve(page_id)
            title = self._get_title(page)
            
            blocks = collect_paginated_api(
                self.config.notion_client.blocks.children.list,
                block_id=page_id
            )
            
            # Convert to markdown
            md_content = self.converter.convert_page(page, blocks)
            if md_content is None:
                return None
                
            # Save to file if changed
            out_file = self.config.output_dir / f"{self._slugify(title)}.md"
            
            if not out_file.exists():
                out_file.write_text(md_content)
                return out_file
            else:
                # Only update if content has changed
                try:
                    current_content = out_file.read_text()
                    if self._get_content_hash(current_content) != self._get_content_hash(md_content):
                        out_file.write_text(md_content)
                        return out_file
                except Exception as e:
                    print(f"Error reading existing file {out_file}: {e}")
                    return None
                    
        except APIResponseError as e:
            print(f"API error for page {page_id}: {e}")
        except Exception as e:
            print(f"Unexpected error processing page {page_id}: {e}")
            
        return None
    
    def walk_pages(self, parent_id: str, visited: Optional[set] = None) -> Iterator[str]:
        """Recursively yield all child page IDs from a parent.
        
        Args:
            parent_id: Parent page ID to start from
            visited: Set of already visited page IDs to prevent cycles
            
        Yields:
            Child page IDs
        """
        if visited is None:
            visited = set()
            
        if parent_id in visited:
            return
            
        visited.add(parent_id)
        
        try:
            blocks = collect_paginated_api(
                self.config.notion_client.blocks.children.list,
                block_id=parent_id
            )
            
            for block in blocks:
                if block["type"] == "child_page":
                    yield block["id"]
                    yield from self.walk_pages(block["id"], visited)
                elif block["type"] == "toggle":
                    yield from self.walk_pages(block["id"], visited)
                    
        except APIResponseError as e:
            print(f"API error walking pages from {parent_id}: {e}")
    
    def sync(self) -> List[pathlib.Path]:
        """Sync all pages from configured parent pages.
        
        Returns:
            List of paths to files that were created or updated
        """
        changed = []
        
        for parent_id in self.config.parent_ids:
            for page_id in self.walk_pages(parent_id):
                if out_file := self.process_page(page_id):
                    changed.append(out_file)
                    
        if changed:
            self._stage_changes(changed)
            
        return changed
    
    def _get_title(self, page: dict) -> str:
        """Extract title from page properties."""
        return "".join(
            t["plain_text"] 
            for t in page["properties"]["title"]["title"]
        )
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    
    def _get_content_hash(self, text: str) -> str:
        """Get hash of content for change detection."""
        import hashlib
        return hashlib.sha1(text.encode()).hexdigest()
    
    def _stage_changes(self, changed_files: List[pathlib.Path]) -> None:
        """Stage changed files in git."""
        try:
            subprocess.run(
                ["git", "add", *map(str, changed_files)],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Check if there are actual staged changes
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True
            )
            
            if result.returncode == 1:  # Changes detected
                print(f"✓ {len(changed_files)} file(s) updated and staged in git")
            else:
                print("✓ Files processed but no content changes detected")
                
        except subprocess.CalledProcessError as e:
            print(f"Warning: Git operation failed: {e}")
            if e.stderr:
                print(f"Git error: {e.stderr.strip()}")

def main():
    """Main entry point for the Notion sync script."""
    try:
        syncer = NotionSync(Config.from_env())
        syncer.sync()
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
