#!/usr/bin/env python3
"""
Migration script to convert SQLite database back to JSONL message storage.

This script:
1. Exports messages to per-channel JSONL files (db/channels/*.json)
2. Exports thread messages to JSONL files (db/threadMessages/*.jsonl)
3. Exports channels metadata to db/channels.json
4. Exports roles to db/roles.json (preserving new role system with id, position, permissions list)
5. Exports threads metadata to db/threads/*.json
6. Exports webhooks to db/webhooks.json
7. Merges reactions into message objects

Usage:
    python scripts/migrate_to_jsonl.py [--backup] [--dry-run]

Options:
    --backup    Create backup of SQLite database before migration
    --dry-run   Show what would be migrated without actually doing it
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_DIR = Path(__file__).parent.parent / "db"
DB_PATH = DB_DIR / "originchats.db"
CHANNELS_DIR = DB_DIR / "channels"
THREADS_DIR = DB_DIR / "threads"
THREAD_MESSAGES_DIR = DB_DIR / "threadMessages"


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to JSONL")
    parser.add_argument("--backup", action="store_true", help="Create backup of SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without doing it")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"SQLite database not found at {DB_PATH}")
        print("Nothing to migrate - already using JSONL storage?")
        return

    print("=" * 60)
    print("SQLite to JSONL Migration Script")
    print("=" * 60)
    print()

    # Create backup if requested
    if args.backup:
        backup_path = DB_DIR / f"originchats_backup_{int(time.time())}.db"
        print(f"Creating backup at {backup_path}...")
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup created: {backup_path}")
        print()

    if args.dry_run:
        print("DRY RUN - No files will be modified")
        print()

    # Connect to SQLite
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Get counts
    message_count = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
    channel_count = conn.execute("SELECT COUNT(*) as cnt FROM channels").fetchone()["cnt"]
    role_count = conn.execute("SELECT COUNT(*) as cnt FROM roles").fetchone()["cnt"]
    thread_count = conn.execute("SELECT COUNT(*) as cnt FROM threads").fetchone()["cnt"]
    reaction_count = conn.execute("SELECT COUNT(*) as cnt FROM reactions").fetchone()["cnt"]
    webhook_count = conn.execute("SELECT COUNT(*) as cnt FROM webhooks").fetchone()["cnt"]

    print("Database Statistics:")
    print(f"  Messages:  {message_count:,}")
    print(f"  Channels:  {channel_count}")
    print(f"  Roles:     {role_count}")
    print(f"  Threads:   {thread_count}")
    print(f"  Reactions: {reaction_count:,}")
    print(f"  Webhooks:  {webhook_count}")
    print()

    if args.dry_run:
        print("Would create:")
        print(f"  - {CHANNELS_DIR}/ directory with {channel_count} channel files")
        print(f"  - {THREADS_DIR}/ directory with {thread_count} thread files")
        print(f"  - {THREAD_MESSAGES_DIR}/ directory")
        print(f"  - db/channels.json")
        print(f"  - db/roles.json")
        print(f"  - db/webhooks.json")
        conn.close()
        return

    # Create directories
    CHANNELS_DIR.mkdir(exist_ok=True)
    THREADS_DIR.mkdir(exist_ok=True)
    THREAD_MESSAGES_DIR.mkdir(exist_ok=True)

    # 1. Migrate channels metadata
    print("Migrating channels...")
    channels = conn.execute("SELECT * FROM channels ORDER BY position").fetchall()
    channels_list = []
    for ch in channels:
        channel_obj = {
            "name": ch["name"],
            "type": ch["type"] or "text",
            "description": ch["description"],
            "permissions": json.loads(ch["permissions"]) if ch["permissions"] else {},
        }
        if ch["display_name"]:
            channel_obj["display_name"] = ch["display_name"]
        if ch["size"]:
            channel_obj["size"] = ch["size"]
        channels_list.append(channel_obj)

    channels_json_path = DB_DIR / "channels.json"
    with open(channels_json_path, "w") as f:
        json.dump(channels_list, f, indent=2)
    print(f"  Migrated {len(channels_list)} channels to channels.json")

    # 2. Migrate roles (preserving new system with id, position, permissions as list)
    print("Migrating roles...")
    roles = conn.execute("SELECT * FROM roles ORDER BY position").fetchall()
    roles_dict = {}
    for r in roles:
        perms = json.loads(r["permissions"]) if r["permissions"] else []
        # Ensure permissions is a list (new system)
        if isinstance(perms, dict):
            perms = list(perms.keys())

        role_obj = {
            "id": r["id"],
            "description": r["description"],
            "color": r["color"],
            "hoisted": bool(r["hoisted"]),
            "permissions": perms,
            "self_assignable": bool(r["self_assignable"]),
            "category": r["category"],
            "position": r["position"] or 0
        }
        roles_dict[r["name"]] = role_obj

    roles_json_path = DB_DIR / "roles.json"
    with open(roles_json_path, "w") as f:
        json.dump(roles_dict, f, indent=2)
    print(f"  Migrated {len(roles_dict)} roles to roles.json")

    # 3. Get all reactions grouped by message
    print("Loading reactions...")
    reactions_by_msg = {}
    reactions = conn.execute("SELECT * FROM reactions").fetchall()
    for r in reactions:
        msg_id = r["message_id"]
        if msg_id not in reactions_by_msg:
            reactions_by_msg[msg_id] = {}
        emoji = r["emoji"]
        if emoji not in reactions_by_msg[msg_id]:
            reactions_by_msg[msg_id][emoji] = []
        reactions_by_msg[msg_id][emoji].append(r["user_id"])
    print(f"  Loaded {len(reactions_by_msg)} messages with reactions")

    # 4. Migrate messages per channel
    print("Migrating messages...")
    channel_names = [ch["name"] for ch in channels_list]
    total_messages = 0

    for channel_name in channel_names:
        messages = conn.execute(
            "SELECT * FROM messages WHERE channel = ? AND thread_id IS NULL ORDER BY timestamp",
            (channel_name,)
        ).fetchall()

        if not messages:
            continue

        channel_file = CHANNELS_DIR / f"{channel_name}.json"
        with open(channel_file, "w") as f:
            for msg in messages:
                msg_obj = {
                    "id": msg["id"],
                    "user": msg["user_id"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                }

                # Add optional fields
                if msg["edited"]:
                    msg_obj["edited"] = True
                if msg["pinned"]:
                    msg_obj["pinned"] = True

                # Add reply_to if exists
                if msg["reply_to_id"] or msg["reply_to_user"]:
                    msg_obj["reply_to"] = {
                        "id": msg["reply_to_id"],
                        "user": msg["reply_to_user"]
                    }

                # Add attachments
                if msg["attachments"]:
                    try:
                        msg_obj["attachments"] = json.loads(msg["attachments"])
                    except json.JSONDecodeError:
                        pass

                # Add embeds
                if msg["embeds"]:
                    try:
                        msg_obj["embeds"] = json.loads(msg["embeds"])
                    except json.JSONDecodeError:
                        pass

                # Add webhook
                if msg["webhook"]:
                    try:
                        msg_obj["webhook"] = json.loads(msg["webhook"])
                    except json.JSONDecodeError:
                        pass

                # Add interaction
                if msg["interaction"]:
                    try:
                        msg_obj["interaction"] = json.loads(msg["interaction"])
                    except json.JSONDecodeError:
                        pass

                # Add reactions
                if msg["id"] in reactions_by_msg:
                    msg_obj["reactions"] = reactions_by_msg[msg["id"]]

                f.write(json.dumps(msg_obj, separators=(',', ':'), ensure_ascii=False) + "\n")
                total_messages += 1

        print(f"    {channel_name}: {len(messages)} messages")

    print(f"  Total: {total_messages:,} messages migrated")

    # 5. Migrate threads
    print("Migrating threads...")
    threads = conn.execute("SELECT * FROM threads").fetchall()
    thread_count = 0

    for thread in threads:
        thread_id = thread["id"]

        # Save thread metadata
        thread_meta = {
            "id": thread_id,
            "name": thread["name"],
            "parent_channel": thread["parent_channel"],
            "created_by": thread["created_by"],
            "created_at": thread["created_at"],
        }
        if thread["locked"]:
            thread_meta["locked"] = True
        if thread["archived"]:
            thread_meta["archived"] = True
        if thread["participants"]:
            try:
                thread_meta["participants"] = json.loads(thread["participants"])
            except json.JSONDecodeError:
                thread_meta["participants"] = []

        thread_file = THREADS_DIR / f"{thread_id}.json"
        with open(thread_file, "w") as f:
            json.dump(thread_meta, f, indent=2)
        thread_count += 1

    print(f"  Migrated {thread_count} thread metadata files")

    # 6. Migrate thread messages
    print("Migrating thread messages...")
    thread_msg_count = 0

    for thread in threads:
        thread_id = thread["id"]
        thread_msgs = conn.execute(
            "SELECT * FROM messages WHERE thread_id = ? ORDER BY timestamp",
            (thread_id,)
        ).fetchall()

        if not thread_msgs:
            continue

        thread_msg_file = THREAD_MESSAGES_DIR / f"{thread_id}.jsonl"
        with open(thread_msg_file, "w") as f:
            for msg in thread_msgs:
                msg_obj = {
                    "id": msg["id"],
                    "user": msg["user_id"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                }

                if msg["edited"]:
                    msg_obj["edited"] = True
                if msg["pinned"]:
                    msg_obj["pinned"] = True

                if msg["reply_to_id"] or msg["reply_to_user"]:
                    msg_obj["reply_to"] = {
                        "id": msg["reply_to_id"],
                        "user": msg["reply_to_user"]
                    }

                if msg["attachments"]:
                    try:
                        msg_obj["attachments"] = json.loads(msg["attachments"])
                    except json.JSONDecodeError:
                        pass

                if msg["id"] in reactions_by_msg:
                    msg_obj["reactions"] = reactions_by_msg[msg["id"]]

                f.write(json.dumps(msg_obj, separators=(',', ':'), ensure_ascii=False) + "\n")
                thread_msg_count += 1

    print(f"  Migrated {thread_msg_count:,} thread messages")

    # 7. Migrate webhooks
    print("Migrating webhooks...")
    webhooks = conn.execute("SELECT * FROM webhooks").fetchall()
    webhooks_dict = {}

    for wh in webhooks:
        webhooks_dict[wh["id"]] = {
            "id": wh["id"],
            "channel": wh["channel"],
            "name": wh["name"],
            "token": wh["token"],
            "created_by": wh["created_by"],
            "created_at": wh["created_at"],
        }
        if wh["avatar"]:
            webhooks_dict[wh["id"]]["avatar"] = wh["avatar"]

    webhooks_json_path = DB_DIR / "webhooks.json"
    with open(webhooks_json_path, "w") as f:
        json.dump(webhooks_dict, f, indent=2)
    print(f"  Migrated {len(webhooks_dict)} webhooks")

    # 8. Export pinned messages list (for reference)
    print("Exporting pinned messages reference...")
    pinned = conn.execute("SELECT * FROM pinned_messages ORDER BY pinned_at DESC").fetchall()
    pinned_list = []
    for p in pinned:
        pinned_list.append({
            "message_id": p["message_id"],
            "channel": p["channel"],
            "thread_id": p["thread_id"],
            "pinned_at": p["pinned_at"]
        })

    if pinned_list:
        pinned_json_path = DB_DIR / "pinned_messages.json"
        with open(pinned_json_path, "w") as f:
            json.dump(pinned_list, f, indent=2)
        print(f"  Exported {len(pinned_list)} pinned message references")

    conn.close()

    # Summary
    print()
    print("=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print()
    print("Files created:")
    print(f"  - db/channels.json ({len(channels_list)} channels)")
    print(f"  - db/roles.json ({len(roles_dict)} roles)")
    print(f"  - db/webhooks.json ({len(webhooks_dict)} webhooks)")
    print(f"  - db/channels/*.json ({total_messages:,} messages)")
    print(f"  - db/threads/*.json ({thread_count} threads)")
    print(f"  - db/threadMessages/*.jsonl ({thread_msg_count:,} messages)")
    if pinned_list:
        print(f"  - db/pinned_messages.json ({len(pinned_list)} references)")
    print()
    print("Existing files kept unchanged:")
    print("  - db/users.json")
    print("  - db/attachments.json")
    print("  - db/push_subscriptions.json")
    print("  - db/serverEmojis.json")
    print()
    print("Next steps:")
    print("  1. Update db/channels.py, db/users.py, db/roles.py, db/threads.py, db/webhooks.py")
    print("     to use JSON/JSONL storage instead of SQLite")
    print("  2. Remove db/database.py and other SQLite-specific files")
    print("  3. Update handler imports (remove _async versions)")
    print("  4. Delete db/originchats.db when migration is verified")
    print()
    print("Note: The new roles system (id, position, permissions list) is preserved!")
    print()


if __name__ == "__main__":
    main()
