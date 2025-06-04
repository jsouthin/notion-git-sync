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
    
    def _get_text_from_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """Extract plain text from Notion's rich text format."""
        return "".join(t["plain_text"] for t in rich_text) if rich_text else ""
    
    def _process_block(self, block: Dict[str, Any], depth: int = 0) -> str:
        """Process a single block, converting it to markdown."""
        block_type = block["type"]
        content = block[block_type]
        indent = "  " * depth
        
        # Get text content
        text = self._get_text_from_rich_text(content.get("rich_text", []))
        
        # Process different block types
        if block_type.startswith("heading_"):
            level = int(block_type[-1])
            return f"{'#' * level} {text}"
            
        elif block_type == "paragraph":
            return text if text else ""
            
        elif block_type == "bulleted_list_item":
            # Calculate proper indentation for nested lists
            list_indent = "  " * depth
            result = [f"{list_indent}* {text}"]
            
            # Process child blocks for nested lists
            if block.get("has_children"):
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                for child in children:
                    child_content = self._process_block(child, depth + 1)
                    if child_content:
                        result.extend(child_content.splitlines())
            
            return "\n".join(result)
            
        elif block_type == "numbered_list_item":
            # Calculate proper indentation for nested lists
            list_indent = "  " * depth
            result = [f"{list_indent}1. {text}"]
            
            # Process child blocks for nested lists
            if block.get("has_children"):
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                for child in children:
                    child_content = self._process_block(child, depth + 1)
                    if child_content:
                        result.extend(child_content.splitlines())
            
            return "\n".join(result)
            
        elif block_type == "to_do":
            check = "x" if content["checked"] else " "
            # Calculate proper indentation for nested lists
            list_indent = "  " * depth
            result = [f"{list_indent}- [{check}] {text}"]
            
            # Process child blocks for nested lists
            if block.get("has_children"):
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                for child in children:
                    child_content = self._process_block(child, depth + 1)
                    if child_content:
                        result.extend(child_content.splitlines())
            
            return "\n".join(result)
            
        elif block_type == "code":
            lang = content["language"] or ""
            return f"```{lang}\n{text}\n```"
            
        elif block_type == "quote":
            return f"> {text}"
            
        elif block_type == "callout":
            # Start blockquote context for the entire callout
            self.in_blockquote = True
            
            # Initialize result list
            result = []
            
            # Add the callout header with icon and type
            icon = content["icon"].get("emoji", "ℹ️")
            result.append(f"> **{icon}** {text}")
            
            # Process any child blocks within the callout
            if block.get("has_children"):
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                
                # Add a blank line after the header for content separation
                result.append(">")
                
                # Process children directly without filtering
                for child in children:
                    child_content = self._process_block(child, depth)
                    if child_content:
                        # Add each line of the child content
                        for line in child_content.splitlines():
                            if line.strip():
                                # Preserve bullet points and other formatting in blockquotes
                                if line.lstrip().startswith('>'):
                                    result.append(line)
                                else:
                                    # Add blockquote marker and ensure proper line breaks
                                    result.append(f"> {line}")
                            else:
                                result.append(">")  # Empty line in blockquote
                
                # Ensure a blank line after the content
                result.append(">")
            
            # Reset blockquote context
            self.in_blockquote = False
            
            # Return the processed callout to prevent further processing
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
            
        # Process any remaining child blocks
        if block.get("has_children") and block_type not in ["toggle", "column_list", "callout"]:
            children = collect_paginated_api(
                self.notion_client.blocks.children.list,
                block_id=block["id"]
            )
            # Only process child blocks if this isn't already a nested list item
            if block_type not in ["bulleted_list_item", "numbered_list_item", "to_do"]:
                child_content = []
                for child in children:
                    content = self._process_block(child, depth + 1)
                    if content:
                        child_content.extend(content.splitlines())
                if child_content:
                    return "\n".join(child_content)
        
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
    
    def _blocks_to_md(self, blocks: List[Dict[str, Any]], depth: int = 0) -> str:
        """Convert blocks to markdown, handling nested structures."""
        lines = []
        last_block_type = None
        
        for block in blocks:
            # Process the current block
            if content := self._process_block(block, depth):
                # Check if current block is an admonition
                is_current_admonition = self._is_admonition(block)
                
                # Add extra spacing between blocks based on type
                if lines:  # If we have previous content
                    # Always add a blank line between different block types
                    if last_block_type != block["type"]:
                        lines.append("")
                    # Add an extra blank line between admonitions
                    elif is_current_admonition and self.last_was_admonition:
                        lines.append("")
                
                lines.append(content)
                self.last_was_admonition = is_current_admonition
                last_block_type = block["type"]
            
            # Only process child blocks if this block type doesn't handle its own children
            if block.get("has_children") and block["type"] not in [
                "bulleted_list_item", 
                "numbered_list_item", 
                "to_do",
                "toggle",
                "column_list",
                "callout"
            ]:
                children = collect_paginated_api(
                    self.notion_client.blocks.children.list,
                    block_id=block["id"]
                )
                child_content = self._blocks_to_md(children, depth + 1)
                if child_content:
                    lines.append(child_content)
        
        # Clean up any excessive blank lines
        result = []
        for i, line in enumerate(lines):
            if line.strip() or (i > 0 and i < len(lines) - 1):  # Keep single blank lines between content
                result.append(line)
            
        return "\n".join(line.rstrip() for line in result if line is not None).rstrip() + "\n"
    
    def _is_admonition(self, block: Dict[str, Any]) -> bool:
        """Determine if a block should be treated as an admonition.
        
        Args:
            block: The Notion block to check
            
        Returns:
            True if the block should be treated as an admonition
        """
        block_type = block["type"]
        
        # Callouts are always admonitions
        if block_type == "callout":
            return True
        
        # Toggles are admonitions if they have a specific structure:
        # - Start with bold text
        # - Have child content
        if block_type == "toggle":
            rich_text = block[block_type].get("rich_text", [])
            if not rich_text:
                return False
            
            # Check if the toggle starts with bold text
            first_segment = rich_text[0]
            annotations = first_segment.get("annotations", {})
            return annotations.get("bold", False) and block.get("has_children", False)
        
        return False

    def convert_page(self, page: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Optional[str]:
        """Convert a Notion page and its blocks to markdown with proper frontmatter.
        
        Args:
            page: The Notion page block containing page properties
            blocks: List of child blocks from the page
            
        Returns:
            Formatted markdown string with frontmatter, or None if invalid/missing frontmatter
        """
        # Get title and frontmatter
        title = self._get_text_from_rich_text(page["properties"]["title"]["title"])
        yaml_raw = self.frontmatter.extract_from_blocks(blocks, self.notion_client)
        
        # Only proceed if we have valid frontmatter
        if not yaml_raw:
            print(f"Skip (no valid frontmatter): {title}")
            return None
            
        # Filter out blocks that contain the frontmatter or duplicate title
        filtered_blocks = []
        for block in blocks:
            # Skip metadata toggle
            if block["type"] == "toggle":
                rich_text = block["toggle"].get("rich_text", [])
                text = self._get_text_from_rich_text(rich_text)
                if any(pattern.lower() in text.strip().lower() 
                      for pattern in self.frontmatter.metadata_patterns):
                    continue
            
            # Skip YAML code blocks that match our frontmatter
            if block["type"] == "code" and block["code"]["language"].lower() == "yaml":
                rich_text = block["code"].get("rich_text", [])
                text = self._get_text_from_rich_text(rich_text).strip()
                if text == yaml_raw.strip():
                    continue
            
            # Skip title blocks (heading_1) that match our page title
            if block["type"] == "heading_1":
                rich_text = block["heading_1"].get("rich_text", [])
                text = self._get_text_from_rich_text(rich_text).strip()
                if text == title or text == f"{title} [WIP]":
                    continue
            
            # Skip bulleted list items that are metadata markers
            if block["type"] == "bulleted_list_item":
                rich_text = block["bulleted_list_item"].get("rich_text", [])
                text = self._get_text_from_rich_text(rich_text)
                if any(pattern.lower() in text.strip().lower() 
                      for pattern in self.frontmatter.metadata_patterns):
                    continue
            
            filtered_blocks.append(block)
            
        # Remove any trailing empty blocks
        while filtered_blocks and filtered_blocks[-1]["type"] == "paragraph":
            rich_text = filtered_blocks[-1]["paragraph"].get("rich_text", [])
            if not self._get_text_from_rich_text(rich_text).strip():
                filtered_blocks.pop()
            else:
                break
            
        # Construct the markdown document with title at the top
        parts = [
            "---",
            yaml_raw.strip(),
            "---",
            "",  # Empty line after frontmatter
            f"# {title}",  # Title as first heading
            "",  # Empty line after title
            self._blocks_to_md(filtered_blocks)
        ]
        
        return "\n".join(parts)