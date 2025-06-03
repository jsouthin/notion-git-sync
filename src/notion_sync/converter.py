"""
Notion to Markdown converter.

This module handles the conversion of Notion blocks to markdown format,
with support for various block types and nested structures.
"""

from typing import List, Dict, Any, Optional
from notion_client.helpers import collect_paginated_api

class MarkdownConverter:
    """Converts Notion blocks to markdown format.
    
    This class handles the conversion of Notion's block structure to markdown,
    including proper handling of frontmatter, titles, and nested content.
    
    Supported block types:
    - Headings (h1-h6)
    - Paragraphs
    - Lists (bulleted, numbered, todo)
    - Code blocks
    - Quotes and callouts
    - Images and bookmarks
    - Tables
    - Toggles
    - Equations
    - Column layouts
    """
    
    def __init__(self, frontmatter_handler, notion_client):
        """Initialize the converter.
        
        Args:
            frontmatter_handler: Handler for YAML frontmatter
            notion_client: Initialized Notion client for API calls
        """
        self.frontmatter = frontmatter_handler
        self.notion_client = notion_client
        self.in_blockquote = False
        self.last_was_admonition = False
    
    def convert_page(self, page: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Optional[str]:
        """Convert a Notion page and its blocks to markdown.
        
        Args:
            page: Notion page object with properties
            blocks: List of child blocks from the page
            
        Returns:
            Formatted markdown string with frontmatter, or None if invalid
        """
        # Get title and frontmatter
        title = self._get_text_from_rich_text(page["properties"]["title"]["title"])
        yaml_raw = self.frontmatter.extract_from_blocks(blocks, self.notion_client)
        
        if not yaml_raw:
            print(f"Skip (no valid frontmatter): {title}")
            return None
            
        # Filter blocks
        filtered_blocks = self._filter_blocks(blocks, title, yaml_raw)
        
        # Construct markdown
        parts = [
            "---",
            yaml_raw.strip(),
            "---",
            "",
            f"# {title}",
            "",
            self._blocks_to_md(filtered_blocks)
        ]
        
        return "\n".join(parts)
    
    def _get_text_from_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """Extract plain text from Notion's rich text format."""
        return "".join(t["plain_text"] for t in rich_text) if rich_text else ""
    
    def _filter_blocks(self, blocks: List[Dict[str, Any]], title: str, yaml_raw: str) -> List[Dict[str, Any]]:
        """Filter out metadata and duplicate title blocks."""
        filtered = []
        for block in blocks:
            if self._should_include_block(block, title, yaml_raw):
                filtered.append(block)
        return filtered
    
    def _should_include_block(self, block: Dict[str, Any], title: str, yaml_raw: str) -> bool:
        """Check if a block should be included in the output."""
        block_type = block["type"]
        
        # Skip metadata toggles
        if block_type == "toggle":
            text = self._get_text_from_rich_text(block["toggle"].get("rich_text", []))
            if any(pattern.lower() in text.strip().lower() 
                  for pattern in self.frontmatter.metadata_patterns):
                return False
        
        # Skip YAML code blocks matching frontmatter
        if block_type == "code" and block["code"]["language"].lower() == "yaml":
            text = self._get_text_from_rich_text(block["code"].get("rich_text", []))
            if text.strip() == yaml_raw.strip():
                return False
        
        # Skip duplicate title blocks
        if block_type == "heading_1":
            text = self._get_text_from_rich_text(block["heading_1"].get("rich_text", []))
            if text.strip() in [title, f"{title} [WIP]"]:
                return False
        
        return True
    
    def _blocks_to_md(self, blocks: List[Dict[str, Any]], depth: int = 0) -> str:
        """Convert blocks to markdown, handling nested structures."""
        lines = []
        last_block_type = None
        
        for block in blocks:
            if content := self._process_block(block, depth):
                # Add spacing between different block types
                if lines and last_block_type != block["type"]:
                    lines.append("")
                
                lines.append(content)
                last_block_type = block["type"]
        
        return "\n".join(lines)
    
    def _process_block(self, block: Dict[str, Any], depth: int = 0) -> str:
        """Process a single block, converting it to markdown."""
        block_type = block["type"]
        content = block[block_type]
        indent = "  " * depth
        
        # Get text content
        text = self._get_text_from_rich_text(content.get("rich_text", []))
        
        if block_type.startswith("heading_"):
            level = int(block_type[-1])
            return f"{'#' * level} {text}"
            
        elif block_type == "paragraph":
            return text if text else ""
            
        elif block_type == "bulleted_list_item":
            return f"{indent}* {text}"
            
        elif block_type == "numbered_list_item":
            return f"{indent}1. {text}"
            
        elif block_type == "to_do":
            check = "x" if content["checked"] else " "
            return f"{indent}- [{check}] {text}"
            
        elif block_type == "code":
            lang = content["language"] or ""
            return f"```{lang}\n{text}\n```"
            
        elif block_type == "quote":
            return f"> {text}"
            
        elif block_type == "callout":
            icon = content["icon"].get("emoji", "ℹ️")
            result = [f"> **{icon}** {text}"]
            
            if block.get("has_children"):
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                child_content = self._blocks_to_md(children, depth)
                if child_content:
                    result.extend(f"> {line}" for line in child_content.splitlines())
            
            return "\n".join(result)
            
        elif block_type == "image":
            url = content["file"]["url"] if content["type"] == "file" else content["external"]["url"]
            caption = self._get_text_from_rich_text(content.get("caption", []))
            return f"![{caption or 'image'}]({url})"
            
        elif block_type == "bookmark":
            url = content["url"]
            caption = self._get_text_from_rich_text(content.get("caption", []))
            return f"[{caption or url}]({url})"
            
        elif block_type == "equation":
            return f"$${text}$$"
            
        elif block_type == "table":
            return self._render_table(block)
            
        elif block_type == "toggle":
            return self._render_toggle(block, depth)
            
        return ""
    
    def _render_table(self, table: Dict[str, Any]) -> str:
        """Convert a Notion table to markdown table format."""
        rows = collect_paginated_api(
            self.notion_client.blocks.children.list,
            block_id=table["id"]
        )
        
        if not rows:
            return ""
            
        # Extract cells
        table_cells = []
        for row in rows:
            cells = [
                self._get_text_from_rich_text(cell).strip()
                for cell in row["table_row"]["cells"]
            ]
            table_cells.append(cells)
            
        if not table_cells:
            return ""
            
        # Calculate column widths
        col_widths = []
        for col in range(len(table_cells[0])):
            width = max(len(cell[col]) for cell in table_cells)
            col_widths.append(width)
            
        # Format table
        header = "| " + " | ".join(cell.ljust(width) for cell, width in zip(table_cells[0], col_widths)) + " |"
        separator = "|" + "|".join(f" {'-' * width} " for width in col_widths) + "|"
        body = [
            "| " + " | ".join(cell.ljust(width) for cell, width in zip(row, col_widths)) + " |"
            for row in table_cells[1:]
        ]
        
        return "\n".join(["", header, separator, *body, ""])
    
    def _render_toggle(self, block: Dict[str, Any], depth: int) -> str:
        """Convert a Notion toggle block to markdown."""
        text = self._get_text_from_rich_text(block["toggle"].get("rich_text", []))
        if not text:
            return ""
            
        result = [f"<details><summary>{text}</summary>"]
        
        if block.get("has_children"):
            children = collect_paginated_api(
                self.notion_client.blocks.children.list,
                block_id=block["id"]
            )
            child_content = self._blocks_to_md(children, depth + 1)
            if child_content:
                result.extend(child_content.splitlines())
        
        result.append("</details>")
        return "\n".join(result)
