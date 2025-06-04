# Notion Git Sync

Synchronize Notion pages to markdown files with frontmatter support.

## Features
- Converts Notion pages to markdown
- Supports YAML frontmatter
- Handles nested content
- Git integration
- Rich block type support
- Automatic change detection
- GitHub Actions integration

## Installation
```bash
pip install notion-git-sync
```

## Usage

### As a Python Library (Recommended)
```python
from notion_git_sync.sync import NotionSync, Config

# Create config from environment variables
config = Config.from_env()
# Or create config manually
config = Config(
    notion_client=notion_client,
    parent_ids=["page_id_1", "page_id_2"],
    output_dir="path/to/output",
    required_frontmatter={"title", "owner"}
)

# Initialize and run sync
syncer = NotionSync(config)
changed_files = syncer.sync()  # Returns list of changed files
```

### As a Command Line Tool
The package includes a CLI script for simple use cases:

```bash
# Set environment variables
export NOTION_TOKEN="your_notion_token"
export NOTION_PARENT_IDS="page_id_1,page_id_2"

# Run the sync
python -m notion_git_sync.sync
```

### GitHub Actions Integration
The package includes a GitHub Actions workflow for automated syncing:

```yaml
name: notion-sync
on:
  schedule: [{ cron: '5 2 * * *' }]  # nightly 02:05 UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    env:
      NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
      NOTION_PARENT_IDS: ${{ secrets.NOTION_PARENT_IDS }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install notion-git-sync
      - run: python -m notion_git_sync.sync
```

#### Repository Configuration
The GitHub Actions workflow will push changes to the same repository where the workflow is running. Make sure to:

1. Configure repository permissions to allow the workflow to push changes:
   - Go to your repository's Settings > Actions > General
   - Under "Workflow permissions", select "Read and write permissions"
   - Save the changes

2. If you want to push to a different repository:
   - Add a Personal Access Token (PAT) with repo scope as a repository secret
   - Configure the remote URL in your workflow to use the PAT:
     ```yaml
     - name: Configure Git
       run: |
         git config --global user.name "GitHub Actions"
         git config --global user.email "actions@github.com"
         git remote set-url origin https://${{ secrets.PAT }}@github.com/username/repo.git
     ```

## Configuration

### Environment Variables
- `NOTION_TOKEN`: Your Notion integration token
- `NOTION_PARENT_IDS`: Comma-separated list of parent page IDs

### Config Object
The `Config` class accepts the following parameters:
- `notion_client`: A configured Notion client instance
- `parent_ids`: List of Notion page IDs to sync
- `output_dir`: Directory where markdown files will be saved
- `required_frontmatter`: Set of required frontmatter fields

## Development
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## License
MIT
