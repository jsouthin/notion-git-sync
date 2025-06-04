import pytest
from unittest.mock import Mock, patch
from notion_git_sync.converter import MarkdownConverter
from notion_git_sync.frontmatter import FrontmatterHandler

@pytest.fixture
def handler():
    return FrontmatterHandler({"title", "owner"})

@pytest.fixture
def converter(handler):
    client = Mock()
    return MarkdownConverter(handler, client)

def test_render_table(converter):
    table_block = {
        "type": "table",
        "id": "table-1"
    }
    rows = [
        {"table_row": {"cells": [[{"plain_text": "Header1"}], [{"plain_text": "Header2"}]]}},
        {"table_row": {"cells": [[{"plain_text": "A"}], [{"plain_text": "B"}]]}},
        {"table_row": {"cells": [[{"plain_text": "C"}], [{"plain_text": "D"}]]}},
    ]
    converter.notion_client.blocks.children.list.return_value = {"results": rows}
    with patch("notion_client.helpers.collect_paginated_api") as mock_collect:
        mock_collect.side_effect = lambda func, **kwargs: func(**kwargs)["results"]
        md = converter._render_table(table_block)
        assert "| Header1 | Header2 |" in md
        assert "| A       | B       |" in md
        assert "| C       | D       |" in md

def test_render_toggle(converter):
    toggle_block = {
        "type": "toggle",
        "id": "toggle-1",
        "toggle": {"rich_text": [{"plain_text": "Show more"}]},
        "has_children": True
    }
    children = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hidden content"}]}},
    ]
    converter.notion_client.blocks.children.list.return_value = {"results": children}
    with patch("notion_client.helpers.collect_paginated_api") as mock_collect:
        mock_collect.side_effect = lambda func, **kwargs: func(**kwargs)["results"]
        md = converter._render_toggle(toggle_block, 0)
        assert "<details><summary>Show more</summary>" in md
        assert "Hidden content" in md
        assert "</details>" in md

def test_is_admonition_callout(converter):
    block = {"type": "callout", "callout": {"rich_text": [{"plain_text": "Note"}]}}
    assert converter._is_admonition(block)

def test_is_admonition_toggle(converter):
    block = {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"plain_text": "Bold!", "annotations": {"bold": True}}]
        },
        "has_children": True
    }
    assert converter._is_admonition(block)

def test_is_not_admonition_toggle(converter):
    block = {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"plain_text": "Not bold", "annotations": {"bold": False}}]
        },
        "has_children": True
    }
    assert not converter._is_admonition(block)

def test_blocks_to_md_empty(converter):
    assert converter._blocks_to_md([]) == "\n"

def test_blocks_to_md_mixed(converter):
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Para"}]}},
        {"type": "code", "code": {"language": "python", "rich_text": [{"plain_text": "print(1)"}]}}
    ]
    md = converter._blocks_to_md(blocks)
    assert "# Title" in md
    assert "Para" in md
    assert "```python" in md

def test_process_block_unknown_type(converter):
    block = {"type": "unknown", "unknown": {"rich_text": [{"plain_text": "???"}]}}
    assert converter._process_block(block) == "" 