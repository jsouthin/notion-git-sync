"""
Frontmatter handling for Notion pages.

This module provides functionality to extract and validate YAML frontmatter
from Notion blocks, supporting multiple formats and validation rules.
"""

from typing import Optional, Set, Dict, Any
import yaml
from notion_client.helpers import collect_paginated_api

class FrontmatterHandler:
    """Handles extraction and validation of YAML frontmatter from Notion blocks.
    
    The handler supports multiple formats for frontmatter:
    1. YAML in a toggle block marked with metadata markers (preferred)
    2. YAML in a code block immediately after title
    3. YAML in any code block if no other valid YAML found
    """
    
    def __init__(self, required_keys: Set[str]):
        """Initialize the frontmatter handler.
        
        Args:
            required_keys: Set of keys that must be present in the frontmatter
        """
        self.required_keys = required_keys
        self.metadata_patterns = [
            "!! Metadata",
            "!!Metadata",
            "!! Meta",
            "!!Meta",
            "Metadata",
            "Meta"
        ]
    
    def is_valid(self, raw: str) -> bool:
        """Check if YAML frontmatter contains all required keys with non-empty values.
        
        Args:
            raw: Raw YAML string to validate
            
        Returns:
            True if the YAML is valid and contains all required keys
        """
        if not raw:
            return False
            
        try:
            data = yaml.safe_load(raw)
            if not data:
                return False
                
            # Check for required keys and non-empty values
            missing_keys = self.required_keys - set(data.keys())
            empty_keys = [k for k in self.required_keys if not data.get(k)]
            
            return not (missing_keys or empty_keys)
            
        except yaml.YAMLError:
            return False
    
    def extract_from_blocks(self, blocks: list, notion_client) -> Optional[str]:
        """Extract YAML frontmatter from Notion blocks.
        
        Args:
            blocks: List of Notion blocks to search
            notion_client: Initialized Notion client for API calls
            
        Returns:
            Extracted YAML string if found and valid, None otherwise
        """
        def clean_yaml(text: str) -> str:
            """Clean YAML text by removing fence lines and extra whitespace."""
            lines = []
            for line in text.splitlines():
                line = line.strip()
                if line and line != '---':
                    lines.append(line)
            return "\n".join(lines)

        def is_metadata_toggle(text: str) -> bool:
            """Check if text matches any metadata pattern."""
            text = text.strip().lower()
            return any(pattern.lower() in text for pattern in self.metadata_patterns)

        def get_text_from_rich_text(rich_text: list) -> str:
            """Extract plain text from Notion's rich text format."""
            return "".join(t["plain_text"] for t in rich_text) if rich_text else ""

        def check_blocks_for_yaml(blocks: list) -> tuple[Optional[str], bool]:
            # First pass: Look for YAML in metadata toggle
            for block in blocks:
                block_type = block["type"]
                if block_type == "toggle":
                    rich_text = block["toggle"].get("rich_text", [])
                    toggle_text = get_text_from_rich_text(rich_text)
                    if is_metadata_toggle(toggle_text):
                        if block.get("has_children"):
                            children = collect_paginated_api(
                                notion_client.blocks.children.list,
                                block_id=block["id"]
                            )
                            for child in children:
                                if child["type"] == "code" and child["code"]["language"].lower() == "yaml":
                                    rich_text = child["code"].get("rich_text", [])
                                    yaml_text = clean_yaml(get_text_from_rich_text(rich_text))
                                    if self.is_valid(yaml_text):
                                        return yaml_text, True

            # Second pass: Look for YAML code block right after title
            found_title = False
            for block in blocks:
                if block["type"].startswith("heading_1"):
                    found_title = True
                    continue
                if found_title and block["type"] == "code" and block["code"]["language"].lower() == "yaml":
                    rich_text = block["code"].get("rich_text", [])
                    yaml_text = clean_yaml(get_text_from_rich_text(rich_text))
                    if self.is_valid(yaml_text):
                        return yaml_text, False

            # Final pass: Look for any valid YAML code block
            for block in blocks:
                if block["type"] == "code" and block["code"]["language"].lower() == "yaml":
                    rich_text = block["code"].get("rich_text", [])
                    yaml_text = clean_yaml(get_text_from_rich_text(rich_text))
                    if self.is_valid(yaml_text):
                        return yaml_text, False
                # Check children of blocks
                if block.get("has_children"):
                    children = collect_paginated_api(
                        notion_client.blocks.children.list,
                        block_id=block["id"]
                    )
                    yaml_text, in_toggle = check_blocks_for_yaml(children)
                    if yaml_text:
                        return yaml_text, in_toggle
            return None, False

        yaml_text, _ = check_blocks_for_yaml(blocks)
        return yaml_text
