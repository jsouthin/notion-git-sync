"""Tests for the notion_sync package."""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from notion_sync import NotionSync, Config, FrontmatterHandler, MarkdownConverter

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

def test_sync_process(config):
    """Test the full sync process."""
    syncer = NotionSync(config)
    
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

