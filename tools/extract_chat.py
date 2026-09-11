#!/usr/bin/env python3
"""Extract one visible conversation branch from YOUR official ChatGPT JSON export.

This does not fetch ChatGPT data or create an official account export. It reads
an already downloaded JSON file, lists matching chats, and optionally creates
Markdown. Tool/system/developer and non-final assistant messages are excluded.
Attachments are referenced where possible, not downloaded or embedded.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def conversations(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('conversations'), list):
        return data['conversations']
    if isinstance(data, dict) and isinstance(data.get('mapping'), dict):
        return [data]
    raise ValueError('Unrecognised JSON structure; use a conversations JSON export.')


def branch(chat: dict) -> list[dict]:
    mapping = chat.get('mapping', {})
    node_id = chat.get('current_node')
    if not node_id or node_id not in mapping:
        raise ValueError('No current_node: refusing to guess which branch is active.')
    result, seen = [], set()
    while node_id:
        if node_id in seen:
            raise ValueError('Cycle in export mapping')
        seen.add(node_id)
        node = mapping.get(node_id)
        if node is None:
            raise ValueError(f'Missing parent node {node_id}')
        message = node.get('message')
        if message:
            result.append(message)
        node_id = node.get('parent')
    return list(reversed(result))


def visible_text(message: dict) -> str | None:
    role = message.get('author', {}).get('role')
    if role not in ('user', 'assistant'):
        return None
    metadata = message.get('metadata', {}) or {}
    if metadata.get('is_visually_hidden_from_conversation'):
        return None
    if role == 'assistant':
        # Exclude internal/non-final content even when present in an export.
        if message.get('channel') not in (None, '', 'final'):
            return None
        if message.get('recipient') not in (None, '', 'all'):
            return None
    content = message.get('content', {}) or {}
    pieces = []
    for part in content.get('parts', []):
        if isinstance(part, str):
            pieces.append(part)
        elif isinstance(part, dict) and isinstance(part.get('text'), str):
            pieces.append(part['text'])
        else:
            pieces.append('[Non-text content: consult the original export.]')
    if not pieces and isinstance(content.get('text'), str):
        pieces.append(content['text'])
    if not pieces:
        return None
    return '\n\n'.join(pieces)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file', type=Path)
    parser.add_argument('--title', help='Case-insensitive title fragment; lists matches')
    parser.add_argument('--id', help='Exact conversation id to export')
    parser.add_argument('--output', type=Path, help='New Markdown output; never overwritten')
    args = parser.parse_args()
    all_chats = conversations(args.json_file)
    matches = [chat for chat in all_chats
               if (not args.title or args.title.casefold() in chat.get('title', '').casefold())
               and (not args.id or str(chat.get('id', chat.get('conversation_id', ''))) == args.id)]
    if not args.output:
        for chat in matches:
            print(chat.get('id', chat.get('conversation_id', '<no id>')), '|', chat.get('title', 'Untitled'))
        return
    if not args.id:
        raise SystemExit('Choose an exact --id before writing an export.')
    if len(matches) != 1:
        raise SystemExit(f'Expected exactly one conversation; found {len(matches)}.')
    chat = matches[0]
    lines = ['# ' + chat.get('title', 'Untitled'), '',
             '> Extracted from a user-supplied official account export. Visible text only.',
             '> This is an archive, not a deployment runbook. Earlier advice may be obsolete.', '']
    for message in branch(chat):
        text = visible_text(message)
        if text is None:
            continue
        role = message.get('author', {}).get('role', '')
        stamp = message.get('create_time')
        label = ''
        if isinstance(stamp, (int, float)):
            label = ' | ' + datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        lines += [f'## {role}{label}', '', text, '']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    print('Created:', args.output)
    print('Review/redact it. Do not publish the full conversation automatically.')


if __name__ == '__main__':
    main()
