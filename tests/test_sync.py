"""Tests for the notion_sync package."""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from notion_git_sync.sync import NotionSync, Config, FrontmatterHandler, MarkdownConverter

@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client."""
    client = Mock()
    
    # Mock page retrieval
    client.pages.retrieve.return_value = {
        "properties": {
            "title": {
                "title": [{"plain_text": "Test Page"}]
            }
        }
    }
    
    # Mock blocks retrieval
    client.blocks.children.list.return_value = {
        "results": [
            {
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"plain_text": "!! Metadata"}],
                    "has_children": True
                },
                "id": "metadata-toggle"
            },
            {
                "type": "code",
                "code": {
                    "language": "yaml",
                    "rich_text": [{
                        "plain_text": """
title: Test Page
owner: test@example.com
last_reviewed: 2024-01-01
next_review_due: 2024-12-31
"""
                    }]
                },
                "id": "yaml-block"
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Test content"}]
                },
                "id": "content-block"
            }
        ]
    }
    
    return client

@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "docs" / "notion"
    output_dir.mkdir(parents=True)
    return output_dir

@pytest.fixture
def config(mock_notion_client, temp_output_dir):
    """Create a test configuration."""
    return Config(
        notion_client=mock_notion_client,
        parent_ids=["test-parent"],
        output_dir=temp_output_dir,
        required_frontmatter={"title", "owner", "last_reviewed", "next_review_due"}
    )

def test_frontmatter_validation():
    """Test frontmatter validation."""
    handler = FrontmatterHandler({"title", "owner"})
    
    # Test valid frontmatter
    valid_yaml = """
    title: Test
    owner: test@example.com
    extra: value
    """
    assert handler.is_valid(valid_yaml)
    
    # Test invalid frontmatter
    invalid_yaml = """
    title: Test
    extra: value
    """
    assert not handler.is_valid(invalid_yaml)
    
    # Test empty frontmatter
    assert not handler.is_valid("")
    assert not handler.is_valid(None)
    
    # Test invalid YAML
    assert not handler.is_valid("invalid: yaml: :")
    
    # Test empty values
    assert not handler.is_valid("""
    title: Test
    owner: 
    """)

def test_frontmatter_extraction():
    """Test frontmatter extraction from different locations."""
    handler = FrontmatterHandler({"title", "owner"})
    client = Mock()
    
    # Ensure client.blocks.children.list returns the correct structure
    def mock_blocks_children_list(**kwargs):
        block_id = kwargs.get("block_id")
        if block_id == "metadata-toggle":
            return {
                "results": [
                    {
                        "type": "code",
                        "code": {
                            "language": "yaml",
                            "rich_text": [{
                                "plain_text": "title: Test Page\nowner: test@example.com"
                            }]
                        }
                    }
                ]
            }
        return {"results": []}
    client.blocks.children.list.side_effect = mock_blocks_children_list

    # Mock collect_paginated_api
    with patch("notion_client.helpers.collect_paginated_api") as mock_collect:
        def mock_collect_side_effect(func, **kwargs):
            return func(kwargs["block_id"])['results']
        mock_collect.side_effect = mock_collect_side_effect
        
        # Test metadata toggle
        blocks = [
            {
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"plain_text": "!! Metadata"}]
                },
                "has_children": True,
                "id": "metadata-toggle"
            }
        ]
        
        yaml_text = handler.extract_from_blocks(blocks, client)
        assert yaml_text is not None
        assert "title: Test Page" in yaml_text
        assert "owner: test@example.com" in yaml_text
        
        # Test YAML after title
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"plain_text": "Test Page"}]
                }
            },
            {
                "type": "code",
                "code": {
                    "language": "yaml",
                    "rich_text": [{
                        "plain_text": "title: Test Page\nowner: test@example.com"
                    }]
                }
            }
        ]
        
        yaml_text = handler.extract_from_blocks(blocks, client)
        assert yaml_text is not None
        assert "title: Test Page" in yaml_text
        
        # Test no valid frontmatter
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "No frontmatter here"}]
                }
            }
        ]
        
        yaml_text = handler.extract_from_blocks(blocks, client)
        assert yaml_text is None

def test_markdown_conversion(mock_notion_client):
    """Test markdown conversion."""
    handler = FrontmatterHandler({"title", "owner"})
    converter = MarkdownConverter(handler, mock_notion_client)
    
    page = {
        "properties": {
            "title": {
                "title": [{"plain_text": "Test Page"}]
            }
        }
    }
    
    blocks = [
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"plain_text": "!! Metadata"}],
                "has_children": True
            },
            "id": "metadata-toggle"
        },
        {
            "type": "code",
            "code": {
                "language": "yaml",
                "rich_text": [{
                    "plain_text": """
title: Test Page
owner: test@example.com
"""
                }]
            },
            "id": "yaml-block"
        },
        {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"plain_text": "Test Page"}]
            }
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Test content"}]
            }
        }
    ]
    
    result = converter.convert_page(page, blocks)
    assert result is not None
    assert "# Test Page" in result
    assert "Test content" in result

def test_block_types(mock_notion_client):
    """Test conversion of different block types."""
    handler = FrontmatterHandler({"title", "owner"})
    converter = MarkdownConverter(handler, mock_notion_client)
    
    # Mock collect_paginated_api
    with patch("notion_client.helpers.collect_paginated_api") as mock_collect:
        mock_collect.side_effect = lambda func, **kwargs: func(**kwargs)["results"]
        
        # Test bulleted list
        blocks = [
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"plain_text": "Item 1"}]
                },
                "has_children": True,
                "id": "list-1"
            }
        ]
        
        mock_notion_client.blocks.children.list.return_value = {
            "results": [
                {
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"plain_text": "Nested item"}]
                    }
                }
            ]
        }
        
        result = converter._process_block(blocks[0])
        assert "* Item 1" in result
        assert "  * Nested item" in result
        
        # Test numbered list
        blocks = [
            {
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"plain_text": "Item 1"}]
                },
                "has_children": True,
                "id": "list-1"
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "1. Item 1" in result
        
        # Test todo list
        blocks = [
            {
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"plain_text": "Task 1"}],
                    "checked": True
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "- [x] Task 1" in result
        
        # Test code block
        blocks = [
            {
                "type": "code",
                "code": {
                    "language": "python",
                    "rich_text": [{"plain_text": "print('hello')"}]
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "```python" in result
        assert "print('hello')" in result
        
        # Test quote
        blocks = [
            {
                "type": "quote",
                "quote": {
                    "rich_text": [{"plain_text": "Quoted text"}]
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "> Quoted text" in result
        
        # Test callout
        blocks = [
            {
                "type": "callout",
                "callout": {
                    "rich_text": [{"plain_text": "Callout text"}],
                    "icon": {"emoji": "ℹ️"}
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "> **ℹ️** Callout text" in result
        
        # Test image
        blocks = [
            {
                "type": "image",
                "image": {
                    "type": "file",
                    "file": {"url": "https://example.com/image.jpg"},
                    "caption": [{"plain_text": "Image caption"}]
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "![Image caption](https://example.com/image.jpg)" in result
        
        # Test bookmark
        blocks = [
            {
                "type": "bookmark",
                "bookmark": {
                    "url": "https://example.com",
                    "caption": [{"plain_text": "Bookmark caption"}]
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "[Bookmark caption](https://example.com)" in result
        
        # Test equation
        blocks = [
            {
                "type": "equation",
                "equation": {
                    "rich_text": [{"plain_text": "E = mc^2"}]
                }
            }
        ]
        
        result = converter._process_block(blocks[0])
        assert "$$E = mc^2$$" in result

def test_sync_process(config):
    """Test the full sync process."""
    syncer = NotionSync(config)
    
    # Mock page retrieval
    def mock_page_retrieve(*args, **kwargs):
        if kwargs.get("page_id") == "child-page-1":
            return {
                "properties": {
                    "title": {
                        "title": [{"plain_text": "Child Page 1"}]
                    }
                }
            }
        return {
            "properties": {
                "title": {
                    "title": [{"plain_text": "Test Page"}]
                }
            }
        }
    
    config.notion_client.pages.retrieve.side_effect = mock_page_retrieve
    
    # Mock blocks retrieval for parent page
    def mock_blocks_list(*args, **kwargs):
        if kwargs.get("block_id") == "test-parent":
            return {
                "results": [
                    {
                        "type": "child_page",
                        "id": "child-page-1",
                        "child_page": {
                            "title": "Child Page 1"
                        }
                    }
                ]
            }
        elif kwargs.get("block_id") == "child-page-1":
            return {
                "results": [
                    {
                        "type": "toggle",
                        "toggle": {
                            "rich_text": [{"plain_text": "!! Metadata"}],
                            "has_children": True
                        },
                        "id": "metadata-toggle"
                    },
                    {
                        "type": "code",
                        "code": {
                            "language": "yaml",
                            "rich_text": [{
                                "plain_text": """
title: Child Page 1
owner: test@example.com
last_reviewed: 2024-01-01
next_review_due: 2024-12-31
"""
                            }]
                        },
                        "id": "yaml-block"
                    },
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"plain_text": "Test content"}]
                        },
                        "id": "content-block"
                    }
                ]
            }
        return {"results": []}
    
    config.notion_client.blocks.children.list.side_effect = mock_blocks_list
    
    # Mock collect_paginated_api to return the same results as blocks.children.list
    with patch("notion_client.helpers.collect_paginated_api") as mock_collect:
        mock_collect.side_effect = lambda func, **kwargs: func(**kwargs)["results"]
        
        # Mock git commands
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1  # Indicate changes detected
            
            # Run sync
            changed_files = syncer.sync()
            
            # Verify files were created
            assert len(changed_files) > 0
            assert all(f.exists() for f in changed_files)
            
            # Verify git commands were called
            mock_run.assert_called()

def test_error_handling(config):
    """Test error handling during sync."""
    syncer = NotionSync(config)
    
    # Make API call fail
    config.notion_client.pages.retrieve.side_effect = Exception("API Error")
    
    # Should handle error gracefully
    result = syncer.process_page("test-page")
    assert result is None

def test_content_change_detection(config, tmp_path):
    """Test that only changed content is updated."""
    syncer = NotionSync(config)
    
    # Create an existing file
    test_file = config.output_dir / "test-page.md"
    test_file.write_text("# Existing content")
    
    # Process page - should update file
    with patch("subprocess.run"):
        result = syncer.process_page("test-page")
        assert result is not None
        assert result.exists()
        
        # Content should be different
        assert test_file.read_text() != "# Existing content"

