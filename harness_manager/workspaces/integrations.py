"""Read-only discovery of coding tools and their portable knowledge files.

Only named knowledge locations are searched automatically. Credentials, binary
editor databases and executable configuration are never migrated as settings.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# (display name, executable, app, home knowledge paths, project knowledge paths, skill roots)
TOOLS = {
    'codex': ('Codex', 'codex', 'Codex.app', ['.codex/memories', '.codex/AGENTS.md'], ['AGENTS.md', '.codex/AGENTS.md'], ['.codex/skills', '.agents/skills']),
    'claude': ('Claude Code', 'claude', '', ['.claude/CLAUDE.md'], ['CLAUDE.md', '.claude/CLAUDE.md', '.claude/rules', '.claude/commands'], ['.claude/skills']),
    'cursor': ('Cursor', 'cursor', 'Cursor.app', ['.cursor/rules'], ['.cursorrules', '.cursor/rules', '.cursor/commands'], ['.cursor/skills']),
    'windsurf': ('Windsurf', 'windsurf', 'Windsurf.app', ['.codeium/windsurf/memories', '.codeium/windsurf/global_rules.md'], ['.windsurfrules', '.windsurf/rules', '.windsurf/workflows'], ['.codeium/windsurf/skills']),
    'copilot': ('GitHub Copilot', 'copilot', '', ['.copilot/instructions'], ['.github/copilot-instructions.md', '.github/instructions', '.github/prompts', '.github/agents'], ['.copilot/skills']),
    'gemini': ('Gemini CLI', 'gemini', '', ['.gemini/GEMINI.md'], ['GEMINI.md', '.gemini/GEMINI.md', '.gemini/commands'], ['.gemini/skills']),
    'opencode': ('OpenCode', 'opencode', 'OpenCode.app', ['.config/opencode/AGENTS.md', '.config/opencode/commands', '.config/opencode/agents'], ['.opencode/commands', '.opencode/agents'], ['.config/opencode/skills']),
    'cline': ('Cline', 'cline', '', ['Documents/Cline/Rules', 'Documents/Cline/Workflows'], ['.clinerules', '.cline/memory-bank', 'memory-bank'], []),
    'roo': ('Roo Code', '', '', [], ['.roorules', '.roo/rules', '.roo/commands'], []),
    'kilo': ('Kilo Code', 'kilo', '', [], ['.kilocode/rules', '.kilocode/workflows'], ['.kilocode/skills']),
    'aider': ('Aider', 'aider', '', [], ['.aider.chat.history.md', 'CONVENTIONS.md'], []),
    'continue': ('Continue', 'cn', '', ['.continue/rules', '.continue/prompts'], ['.continue/rules', '.continue/prompts'], []),
    'antigravity': ('Antigravity', 'antigravity', 'Antigravity.app', ['.gemini/GEMINI.md'], ['.agent/rules', '.agent/workflows'], ['.gemini/antigravity/skills']),
    'hermes': ('Hermes', 'hermes', '', ['.hermes/memories'], [], ['.hermes/skills']),
    'pi': ('Pi', 'pi', '', ['.pi/agent/AGENTS.md'], ['.pi/prompts'], ['.pi/agent/skills']),
    'openclaw': ('OpenClaw', 'openclaw', '', ['.openclaw/workspace/MEMORY.md', '.openclaw/workspace/memory'], ['.openclaw-system.md'], ['.openclaw/workspace/skills']),
    'autohand': ('Autohand Code', 'autohand', '', [], ['.autohand/skills'], []),
    'zed': ('Zed', 'zed', 'Zed.app', [], ['.rules'], []),
}
PROVIDER_NAMES = {key: row[0] for key, row in TOOLS.items()}
EXTRA_PROVIDERS = set(TOOLS) - {'codex', 'claude'}
EXTENSIONS = {'.md', '.mdc', '.txt', '.json', '.jsonl', '.yaml', '.yml', '.toml', '.instructions'}
DENIED = {'auth.json', 'credentials.json', 'secrets.json', 'tokens.json', 'settings.json', 'config.json', 'mcp.json'}
DESKTOP_TOOLS = {'claude', 'codex', 'opencode', 'cursor'}


def portable_files(path):
    """Bounded traversal; dot roots are explicit, inner hidden trees stay excluded."""
    if path.is_symlink():
        return
    if path.is_file():
        if path.name.lower() not in DENIED and (path.suffix.lower() in EXTENSIONS or path.name in {'.cursorrules', '.windsurfrules', '.clinerules', '.roorules', '.rules'}):
            yield path
        return
    if not path.is_dir():
        return
    count = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in {'node_modules', '__pycache__'} and not (Path(directory)/d).is_symlink())
        count += 1
        if count > 3000:
            return
        for name in sorted(files):
            file = Path(directory)/name
            if not name.startswith('.') and file.suffix.lower() in EXTENSIONS and name.lower() not in DENIED and not file.is_symlink():
                yield file


def knowledge_locations(provider, home, project):
    _, _, _, homes, projects, skills = TOOLS[provider]
    paths = [home/p for p in homes] + [project/p for p in projects] + [home/p for p in skills]
    # A project can have its own skill library, independent of global skills.
    project_skills = {'codex': '.agents/skills', 'claude': '.claude/skills', 'cursor': '.cursor/skills',
                      'windsurf': '.windsurf/skills', 'copilot': '.github/skills', 'gemini': '.gemini/skills',
                      'opencode': '.opencode/skills', 'kilo': '.kilocode/skills', 'antigravity': '.agent/skills', 'pi': '.pi/skills'}
    if provider in project_skills:
        paths.append(project/project_skills[provider])
    return paths


def knowledge_files(provider, home, project):
    seen = set()
    for location in knowledge_locations(provider, home, project):
        if provider == 'codex' and location == home/'.codex/memories':
            continue  # The dedicated memory reader preserves its narrower traversal policy.
        for path in portable_files(location):
            # Reject a symlinked ancestor as well as a symlinked leaf.
            if path.absolute() != path.resolve() or str(path) in seen:
                continue
            seen.add(str(path))
            yield path


def discover(home, project=None):
    home = home.resolve()
    project = project.resolve() if project else home/'.agentic-stack-no-project'
    result = []
    for key, (name, binary, app, homes, projects, skills) in TOOLS.items():
        if key not in DESKTOP_TOOLS:
            continue
        executable = shutil.which(binary) if binary else None
        if binary and not executable:
            executable = next((str(p/binary) for p in [home/'.local/bin', Path('/opt/homebrew/bin'), Path('/usr/local/bin')]
                               if (p/binary).is_file() and os.access(p/binary, os.X_OK)), None)
        application = next((str(p/app) for p in [Path('/Applications'), home/'Applications'] if app and (p/app).is_dir()), '')
        extension_ids = {'cline': 'saoudrizwan.claude-dev', 'roo': 'rooveterinaryinc.roo-cline',
                         'kilo': 'kilocode.kilo-code', 'continue': 'continue.continue', 'copilot': 'github.copilot'}
        extensions = []
        if key in extension_ids:
            for editor in ['.vscode', '.vscode-insiders', '.cursor', '.windsurf']:
                extensions.extend(str(p) for p in (home/editor/'extensions').glob(extension_ids[key]+'-*') if p.is_dir())
        locations = knowledge_locations(key, home, project)
        if key == 'claude':
            locations.extend(sorted((home/'.claude/projects').glob('*/memory'))[:1500])
        paths = [str(p) for p in locations if p.exists() and not p.is_symlink()]
        # Presence checks only: discovery does not open the user's notes or auth files.
        data_roots = {'codex': '.codex', 'claude': '.claude', 'cursor': '.cursor', 'windsurf': '.codeium/windsurf',
                      'opencode': '.local/share/opencode', 'gemini': '.gemini', 'copilot': '.copilot',
                      'continue': '.continue', 'aider': '.aider.conf.yml'}
        configured = bool(paths) or (key in data_roots and (home/data_roots[key]).exists())
        result.append({'id': key, 'name': name, 'installed': bool(executable or application or extensions), 'detected': bool(executable or application or extensions or configured),
                       'executable': executable or '', 'application': application, 'locations': list(dict.fromkeys(paths)),
                       'migration': 'Memory, rules, skills, and conversations',
                       'agentId': {'codex': 'codex', 'claude': 'claude-code'}.get(key, '')})
    return {'tools': result}
