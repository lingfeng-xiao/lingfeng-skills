---
name: obsidian
description: Read, search, and create notes in the Obsidian vault.
---

# Obsidian Vault

**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g. in `~/.hermes/.env`).

If unset, defaults to `~/Documents/Obsidian Vault`.

## Preferred Hermes workflow

When working with an Obsidian vault from Hermes:

- Use **`read_file`** to read notes
- Use **`search_files(target='files')`** to list notes/folders
- Use **`search_files(target='content')`** to search note contents
- Use **`write_file`** to create a note from scratch
- Use **`patch`** for targeted edits to an existing note
- Use **`terminal`** only for filesystem/git operations that file tools do not cover

This avoids conflicting with Hermes tool-use rules (`cat`, `find`, `ls`, `grep`, `echo >>` should not be the default approach here).

## Practical setup notes

- Vault paths may contain spaces, so quote them in shell commands.
- If you are creating a new vault for long-term use, prefer **lowercase names without spaces** when possible (for example `~/Documents/obsidian-vault/english-diary`) to make git sync, shell scripting, and automation simpler.
- If using shell mkdir with brace expansion, **do not quote the brace expression itself**. Quoting something like `"$vault/{daily,templates,reviews}"` creates a literal directory named `{daily,templates,reviews}` instead of three folders.

## Common tasks

### Read a note
Use `read_file(path)`.

### List notes
Use `search_files(pattern="*.md", target="files", path=<vault>)`.

### Search note content
Use `search_files(pattern=<regex>, target="content", path=<vault>, file_glob="*.md")`.

### Create a note
Use `write_file(path, content)`.

### Update a note
Use `patch(...)` for targeted edits.

## Git-backed vault pattern

A useful default for a personal vault:

1. Create the vault directory and subfolders such as `daily/`, `templates/`, `reviews/`
2. Add starter templates and a small `readme.md`
3. Initialize git in the vault root
4. Create the GitHub repo (often private)
5. If a token is needed to create the repo over HTTPS, use it only for repo creation/push, then switch the remote back to **SSH** so the token is not left in `origin`
6. Update `OBSIDIAN_VAULT_PATH` in `~/.hermes/.env`

## Wikilinks

Obsidian links notes with `[[note-name]]` syntax. Use them when linking related notes.
