   # Notion Sync

   Synchronize Notion pages to markdown files with frontmatter support.

   ## Features
   - Converts Notion pages to markdown
   - Supports YAML frontmatter
   - Handles nested content
   - Git integration
   - Rich block type support

   ## Installation
   ```bash
   pip install notion-sync
   ```

   ## Usage
   ```python
   from notion_sync import NotionSync, Config

   config = Config.from_env()
   syncer = NotionSync(config)
   changed_files = syncer.sync()
   ```

   ## Configuration
   Set the following environment variables:
   - NOTION_TOKEN: Your Notion integration token
   - NOTION_PARENT_IDS: Comma-separated list of parent page IDs
