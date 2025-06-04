#!/usr/bin/env python3

from notion_git_sync.sync import NotionSync, Config

def main():
    config = Config.from_env()
    syncer = NotionSync(config)
    changed_files = syncer.sync()
    return 0 if changed_files else 1

if __name__ == "__main__":
    exit(main()) 