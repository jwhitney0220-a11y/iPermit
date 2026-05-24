# Vendored Agent Skills

This directory vendors two third-party Claude Code plugins so they are available
in ephemeral cloud sessions and to anyone working on iPermit.

| Plugin | Upstream | Commit | License |
|--------|----------|--------|---------|
| `superpowers/` | https://github.com/obra/superpowers | `f2cbfbefebbfef77321e4c9abc9e949826bea9d7` | MIT |
| `caveman/` | https://github.com/JuliusBrussee/caveman | `655b7d9c5431f822264b7732e9901c5578ac84cf` | MIT |

Vendored on 2026-05-24. Upstream `LICENSE` files are preserved at the root of
each plugin directory.

## How it loads

`.claude/hooks/install-vendored-plugins.sh` runs on every `SessionStart` and
symlinks each plugin into `~/.claude/plugins/` (or `$CLAUDE_CONFIG_DIR/plugins/`
if set). The hook is idempotent — it skips any plugin name that already exists
at the target path, so a user's local global install always wins.

If you work on iPermit from your own machine and prefer the upstream installs:

- Superpowers: `/plugin install superpowers@claude-plugins-official`
- Caveman: `curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash`

Either will pre-populate `~/.claude/plugins/<name>/` and the session hook will
become a no-op for that plugin.

## Local patches

### Caveman — auto-activation removed

Upstream caveman ships `SessionStart` and `UserPromptSubmit` hooks that turn the
mode on automatically and a `SKILL.md` description that says it auto-triggers
"when token efficiency is requested." The iPermit fork removes both, because
caveman compression is incompatible with iPermit's mandatory advisory language,
citations, and explainability standards (see `/AGENTS.md`).

Patches applied:

1. `caveman/.claude-plugin/plugin.json` — `hooks` section removed entirely.
2. `caveman/skills/caveman/SKILL.md` — frontmatter description rewritten to
   require explicit `/caveman` invocation. Auto-trigger language removed.
3. `caveman/plugins/caveman/skills/caveman/SKILL.md` — same patch as #2
   (this is the mirrored copy under the plugin distribution dir).

Result: caveman mode only activates when the user types `/caveman`,
`/caveman lite|full|ultra`, or explicitly says "caveman mode" / "talk like
caveman". It is intended for direct user-facing chat only — never for repo
content, code, commits, PR bodies, AGENTS.md changes, permit rules, or
user-facing output.

## Updating

When pulling a new upstream version:

1. `git clone` the upstream repo into `/tmp/<name>` at the desired tag/commit.
2. Re-copy: `cp -r /tmp/<name>/* tools/agents/<name>/` then delete the copied
   `.git/` directory.
3. For caveman, re-apply the three patches above (diff against this commit if
   needed).
4. Update the commit SHA in the table at the top of this file.
5. Verify the SessionStart hook still resolves the symlinks: delete
   `~/.claude/plugins/<name>` and re-run `bash
   .claude/hooks/install-vendored-plugins.sh`.

## Why vendor instead of install globally?

Cloud sessions in Claude Code on the web run in ephemeral containers — the
filesystem is reclaimed when the session ends. A global `/plugin install` would
not persist. Vendoring + a session-start install hook makes the plugins
available the moment any cloud session starts, with no manual setup.
