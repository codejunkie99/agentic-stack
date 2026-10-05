"""Previewed, approved local exports using the bundled data tools."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading

from .knowledge import clean_text
from ..transfer_bundle import now_iso

MAX_BYTES = 2_000_000
MAX_RECORDS = 2000
METRIC_INPUTS = (
    'memory/episodic/AGENT_LEARNINGS.jsonl', 'data-layer/harness-events.jsonl',
    'data-layer/cron-runs.jsonl', 'runtime/loops/events.jsonl', 'data-layer/category-rules.json',
)
METRIC_FIELDS = set(('timestamp created_at started_at finished_at ended_at skill action workflow phase '
    'run_type result status duration_ms importance pain_score confidence tokens_in_estimate tokens_out_estimate '
    'cost_estimate_usd harness category privacy_level pii_level source id name schedule project agent_id_hash '
    'agent_id run_id profile event loop decision').split())
TRAINING_FIELDS = set(('id created_at timestamp project domain workflow skill agent_skill harness host '
    'human_review_status human_review redaction_status pii_level raw_input_stored trainable input_redacted '
    'output_approved input_summary output_summary instruction context model_used context_tokens_before '
    'context_tokens_after eval_tags failure_modes target_use model_target expected_behavior forbidden_behavior '
    'rubric stable_rules tool_contracts human_approval_required_for goal split source_refs').split())
METRIC_ARTIFACTS = ['export-audit.json', 'dashboard.html', 'dashboard.tui.txt', 'daily-report.md', 'dashboard-summary.json',
    'dashboard-report.json'] + [name + ext for name in ('agent-events', 'cron-runs') for ext in ('.jsonl', '.csv')] + [
    name + ext for name in ('activity-series', 'category-summary', 'harness-summary', 'workflow-summary',
                          'cron-timeline', 'kpi-summary') for ext in ('.json', '.csv')]
TRAINING_ARTIFACTS = ['export-audit.json', 'trace-records.jsonl', 'training-examples.jsonl', 'eval-cases.jsonl',
                      'context-cards.json', 'context-cards/', 'flywheel-metrics.json', 'README.md']
EXISTING_EXPORT_ROOTS = {'metrics': '.agent/data-layer/exports', 'training': '.agent/flywheel/exports'}
MAX_EXPORT_SCAN_ENTRIES = 2000
MAX_EXISTING_ARTIFACTS = 500
MAX_EXPORT_SCAN_BYTES = 32_000_000


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def sanitize(value, depth=0):
    if depth > 20:
        raise ValueError('An input record is nested too deeply.')
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, (dict, list)):
        items, removed = ({} if isinstance(value, dict) else []), 0
        for key, child in (value.items() if isinstance(value, dict) else enumerate(value)):
            safe, count = sanitize(child, depth + 1)
            if isinstance(items, dict):
                safe_key, key_count = clean_text(key)
                items[safe_key] = safe
                count += key_count
            else:
                items.append(safe)
            removed += count
        return items, removed
    return value, 0


def trainable(row):
    # The bundled data_flywheel_export.is_trainable gate; never promote file records.
    review = row.get('human_review') if isinstance(row.get('human_review'), dict) else {}
    status = row.get('human_review_status') or review.get('status')
    return (row.get('trainable') is not False and isinstance(status, str)
        and status in {'accepted', 'edited'}
        and row.get('redaction_status') == 'passed' and row.get('raw_input_stored') is not True
        and isinstance(row.get('input_redacted'), str) and bool(row['input_redacted'].strip())
        and isinstance(row.get('output_approved'), str) and bool(row['output_approved'].strip()))


def guarded(root, relative):
    """Reject links in every component, including links which stay inside the root."""
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid artifact path.')
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symbolic links are not allowed in artifact inputs or outputs.')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Artifact path leaves its selected workspace.')
    return path


def read_bytes(root, relative, *, missing_ok=False):
    """Read beneath a directory handle; no later path lookup can follow a swapped ancestor."""
    root, relative = Path(root), Path(relative)
    if not root.is_absolute() or relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Invalid artifact path.')
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = None
    try:
        # Roots supplied by StackManager/Store are canonical. Anchor their entire
        # path as well, so a replaced ancestor cannot redirect the initial open.
        directory_fd = os.open(root.anchor, directory_flags)
        for part in root.parts[1:] + relative.parts[:-1]:
            child_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                raise ValueError('Artifact input or output must be a regular file under 2 MB.')
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('Artifact input or output exceeds 2 MB.')
        return content
    except FileNotFoundError as exc:
        if missing_ok:
            return None
        raise ValueError('Artifact input or output is unavailable; refresh before continuing.') from exc
    except OSError as exc:
        raise ValueError('Artifact input or output is unavailable; refresh before continuing.') from exc
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def export_name(kind, relative):
    """Known exporter outputs, directly in exports/ or one dated subdirectory."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in {'.', '..'} or p.startswith('.') for p in parts):
        return None
    supported = METRIC_ARTIFACTS if kind == 'metrics' else TRAINING_ARTIFACTS
    if len(parts) in {1, 2} and parts[-1] in supported:
        return parts[-1]
    cards = parts if parts[0] == 'context-cards' else parts[1:]
    if (kind == 'training' and len(cards) == 3 and cards[0] == 'context-cards'
            and Path(cards[-1]).suffix in {'.json', '.md'}):
        return '/'.join(cards)
    return None


def open_directory(root, relative):
    """Anchor discovery to descriptors, rejecting symlinks in every component."""
    root, relative = Path(root), Path(relative)
    if not root.is_absolute() or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid artifact path.')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root.anchor, flags)
    try:
        for part in root.parts[1:] + relative.parts:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


class Artifacts:
    def __init__(self, stack):
        self.stack, self.store = stack, stack.store
        self.lock = threading.RLock()

    def _root(self, wid):
        self.store.get('workspace', wid)
        if not isinstance(wid, str) or len(wid) != 32 or any(c not in '0123456789abcdef' for c in wid):
            raise ValueError('Invalid workspace identifier.')
        return guarded(self.store.root, 'projects/' + wid + '/artifacts')

    def _tool(self, kind):
        root = Path(__file__).resolve().parents[2]
        return guarded(root, '.agent/tools/' + ('data_layer_export.py' if kind == 'metrics' else 'data_flywheel_export.py'))

    def _runs(self, wid):
        return [r for r in self.store.all('run') if r.get('workspaceId') == wid]

    def _eligible(self, run):
        if run.get('reviewed') is not True or run.get('status') != 'completed':
            return 'Review the completed run in Tasks first.'
        if not isinstance(run.get('task'), str) or not isinstance(run.get('output'), str):
            return 'The run needs input and output text.'
        if not clean_text(run['task'])[0].strip() or not clean_text(run['output'])[0].strip():
            return 'The run needs input and output text.'
        return ''

    def _file(self, root, relative):
        guarded(root, '.agent/' + relative)
        raw = read_bytes(root, '.agent/' + relative, missing_ok=True)
        if raw is None:
            return None, [], 0
        try:
            text = raw.decode('utf-8')
            if relative.endswith('.json'):
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    raise ValueError('Expected a JSON object.')
                return digest(raw), [parsed], 0
            rows, malformed = [], 0
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError('Expected an object.')
                    rows.append(row)
                except ValueError:
                    malformed += 1
                if len(rows) + malformed > MAX_RECORDS:
                    raise ValueError('Select input files containing at most 2,000 records.')
            return digest(raw), rows, malformed
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError('Artifact inputs must contain valid UTF-8 JSON or JSONL.') from exc

    def _collect(self, p):
        wid, kind = p.get('workspaceId'), p.get('kind')
        if not isinstance(kind, str) or kind not in {'metrics', 'training'}:
            raise ValueError('Choose metrics or training artifacts.')
        workspace = self.store.get('workspace', wid)
        root = self.stack.root(wid)
        self._root(wid)
        window, bucket = p.get('window', '30d'), p.get('bucket', 'day')
        if (not isinstance(window, str) or window not in {'7d', '30d', '90d', 'all'}
                or not isinstance(bucket, str) or bucket not in {'hour', 'day', 'week', 'month'}):
            raise ValueError('Choose a supported time window and bucket.')
        ids = p.get('runIds')
        if ids is not None and (not isinstance(ids, list) or not ids or len(ids) > 200
                or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids)):
            raise ValueError('Explicitly select between 1 and 200 unique runs.')
        runs = self._runs(wid)
        if ids is not None:
            by_id = {r['id']: r for r in runs}
            if any(identifier not in by_id for identifier in ids):
                raise ValueError('Selected runs must belong to this workspace.')
            runs = [by_id[identifier] for identifier in ids]
        tool = self._tool(kind)
        tool_root = Path(__file__).resolve().parents[2]
        fingerprints = {'project': str(root), 'workspace': digest(encode(workspace)),
                        'exporter': digest(read_bytes(tool_root, tool.relative_to(tool_root)))}
        files, warnings, redactions, count = {}, [], 0, 0
        if kind == 'training' and ids is not None:
            rows = []
            for run in runs:
                reason = self._eligible(run)
                if reason:
                    raise ValueError(reason)
                fingerprints['run:' + run['id']] = digest(encode(run))
                row, removed = sanitize({'id': run['id'], 'created_at': run['createdAt'],
                    'project': workspace['name'], 'domain': 'software', 'workflow': 'desktop_run',
                    'skill': run.get('agent', 'unknown'), 'harness': run.get('agent', 'unknown'),
                    'model_used': run.get('model', ''), 'input_redacted': run['task'],
                    'output_approved': run['output'], 'human_review_status': 'accepted',
                    'redaction_status': 'passed', 'raw_input_stored': False, 'pii_level': 'reviewed',
                    'source_refs': run.get('sourceRefs', []), 'trainable': True})
                rows.append(row)
                redactions += removed
            files['flywheel/approved-runs.jsonl'] = ''.join(encode(row) + '\n' for row in rows)
            count = len(rows)
        else:
            paths = METRIC_INPUTS if kind == 'metrics' else ('flywheel/approved-runs.jsonl',)
            for relative in paths:
                fingerprint, rows, malformed = self._file(root, relative)
                fingerprints[relative] = fingerprint
                if fingerprint is None:
                    continue
                if malformed:
                    warnings.append(f'{relative}: skipped {malformed} malformed line(s).')
                if kind == 'training':
                    eligible = [row for row in rows if trainable(row)]
                    if len(eligible) != len(rows):
                        warnings.append(f'Excluded {len(rows) - len(eligible)} record(s) without approved, redacted training input.')
                    rows = [{key: value for key, value in row.items() if key in TRAINING_FIELDS} for row in eligible]
                elif not relative.endswith('.json'):
                    rows = [{key: value for key, value in row.items() if key in METRIC_FIELDS} for row in rows]
                    for row in rows:
                        if isinstance(row.get('source'), dict):
                            row['source'] = {k: v for k, v in row['source'].items() if k in {'skill', 'harness', 'profile', 'run_id'}}
                else:
                    config = rows[0]
                    rows = [{key: value for key, value in config.items() if key in {'default_category', 'rules'}}]
                rows, removed = sanitize(rows)
                redactions += removed
                count += len(rows) if not relative.endswith('.json') else 0
                files[relative] = encode(rows[0]) + '\n' if relative.endswith('.json') else ''.join(encode(row) + '\n' for row in rows)
            if kind == 'metrics':
                if len(runs) > MAX_RECORDS:
                    raise ValueError('Select up to 200 desktop runs for this export.')
                rows = []
                for run in runs:
                    metadata = {key: run.get(key) for key in ('id', 'createdAt', 'updatedAt', 'agent', 'status', 'reviewed')}
                    fingerprints['run:' + run['id']] = digest(encode(metadata))
                    row, removed = sanitize({'timestamp': run['createdAt'], 'skill': run.get('agent', 'unknown'),
                        'harness': run.get('agent', 'unknown'), 'action': 'desktop_run', 'workflow': 'desktop_run',
                        'result': 'success' if run.get('status') == 'completed' else run.get('status', 'unknown'),
                        'source': {'run_id': run['id']}, 'privacy_level': 'local_only'})
                    rows.append(row)
                    redactions += removed
                if rows:
                    relative = 'data-layer/harness-events.jsonl'
                    files[relative] = files.get(relative, '') + ''.join(encode(row) + '\n' for row in rows)
                count += len(rows)
        if kind == 'training' and not count:
            raise ValueError('No eligible training input. Select reviewed runs or add approved, redacted records to .agent/flywheel/approved-runs.jsonl.')
        if kind == 'training' and count > 200:
            raise ValueError('Select at most 200 training records per export.')
        project, removed = clean_text(workspace['name'])
        redactions += removed
        text = '\n\n'.join('### .agent/' + name + '\n' + content for name, content in files.items())
        if len(text.encode()) > MAX_BYTES:
            raise ValueError('The sanitized preview exceeds 2 MB. Select fewer inputs.')
        return dict(workspaceId=wid, kind=kind, text=text, files=files, project=project,
            digest=digest(encode({'files': files, 'project': project, 'window': window, 'bucket': bucket})),
            sourceDigest=digest(encode(fingerprints)), recordCount=count, redactions=redactions,
            sourceCount=sum(value is not None for key, value in fingerprints.items() if key not in {'project', 'workspace', 'exporter'}),
            window=window, bucket=bucket, warnings=warnings,
            artifacts=METRIC_ARTIFACTS if kind == 'metrics' else TRAINING_ARTIFACTS)

    def preview(self, p):
        with self.lock:
            collected = self._collect(p)
            collected['warnings'].append('Review the sanitized text for personal or sensitive information before approving this local export.')
            row = self.store.create('artifactPreview', dict(collected, params=p, status='previewed'))
            return {key: value for key, value in dict(row, previewId=row['id']).items()
                    if key not in {'files', 'params', 'sourceDigest'}}

    def _public(self, row):
        return {key: row[key] for key in ('id', 'path', 'name', 'type', 'kind', 'size', 'status')}

    def _existing(self, wid, managed, issues):
        root = self.stack.root(wid)
        managed_paths = {str(Path(row['path'])) for row in managed}
        managed_content = {(row['kind'], row['name'], row.get('digest')) for row in managed}
        found, seen_paths = [], set()
        scanned = total_bytes = 0
        limited = False

        def walk(fd, kind, parts=()):
            nonlocal scanned, total_bytes, limited
            with os.scandir(fd) as entries:
                for entry in entries:
                    if (scanned >= MAX_EXPORT_SCAN_ENTRIES or len(found) >= MAX_EXISTING_ARTIFACTS
                            or total_bytes > MAX_EXPORT_SCAN_BYTES - MAX_BYTES):
                        limited = True
                        return
                    scanned += 1
                    nested = parts + (entry.name,)
                    relative = Path(EXISTING_EXPORT_ROOTS[kind]).joinpath(*nested)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            issues.append(f'{relative}: symbolic links are excluded from existing exports.')
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            # Exporters use date/output names and context-cards/domain/file.
                            descend = len(nested) == 1 or (kind == 'training' and (
                                len(nested) == 2 and 'context-cards' in nested
                                or len(nested) == 3 and nested[1] == 'context-cards'))
                            if descend and not any(p.startswith('.') for p in nested):
                                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                                try:
                                    walk(child, kind, nested)
                                finally:
                                    os.close(child)
                                if limited:
                                    return
                            continue
                        name = export_name(kind, Path(*nested))
                        if name is None:
                            continue
                        path = str(root / relative)
                        if path in seen_paths or path in managed_paths:
                            continue
                        raw = read_bytes(root, relative)
                        total_bytes += len(raw)
                        raw.decode('utf-8')
                        fingerprint = digest(raw)
                        if (kind, name, fingerprint) in managed_content:
                            continue
                        seen_paths.add(path)
                        found.append(dict(id=f'existing:{wid}:{fingerprint}:{relative.as_posix()}', path=path,
                            name='/'.join(nested), type=relative.suffix.lstrip('.') or 'text', kind=kind,
                            size=len(raw), status='existing'))
                    except (ValueError, OSError, UnicodeError) as exc:
                        issues.append(f'{relative}: {exc}')

        for kind, relative in EXISTING_EXPORT_ROOTS.items():
            if limited:
                break
            fd = None
            try:
                fd = open_directory(root, relative)
                walk(fd, kind)
            except FileNotFoundError:
                pass
            except (ValueError, OSError) as exc:
                issues.append(f'{relative}: existing exports unavailable ({exc}).')
            finally:
                if fd is not None:
                    os.close(fd)
        if limited:
            issues.append('Existing export discovery reached its local file or byte limit; narrow the export folders.')
        return sorted(found, key=lambda row: (row['kind'], row['name']))

    def snapshot(self, wid):
        self.store.get('workspace', wid)
        runs = self._runs(wid)
        rows, issues, file_count, metrics_count = [], [], 0, 0
        for run in runs:
            reason = self._eligible(run)
            rows.append(dict(id=run['id'], task=clean_text(run.get('task') or '')[0][:240],
                agent=run.get('agent', ''), model=run.get('model', ''), status=run.get('status', ''),
                reviewed=run.get('reviewed') is True, eligible=not reason, reason=reason, createdAt=run['createdAt']))
        for kind in ('training', 'metrics'):
            try:
                count = self._collect({'workspaceId': wid, 'kind': kind})['recordCount']
                if kind == 'training':
                    file_count = count
                else:
                    metrics_count = count
            except (ValueError, OSError) as exc:
                issues.append(str(exc))
        managed = [row for row in self.store.all('artifact') if row.get('workspaceId') == wid]
        existing = self._existing(wid, managed, issues)
        artifacts = [self._public(row) for row in managed] + existing
        return dict(workspaceId=wid, runs=rows, artifacts=artifacts, issues=issues,
            counts=dict(reviewedRuns=sum(r['reviewed'] for r in rows), eligibleRuns=sum(r['eligible'] for r in rows),
                        approvedFileRuns=file_count, metricsRecords=metrics_count, artifacts=len(artifacts),
                        existingArtifacts=len(existing), generatedArtifacts=len(managed)))

    def generate(self, p):
        if p.get('approved') is not True:
            raise ValueError('Explicit approval of the sanitized preview is required.')
        with self.lock:
            row = self.store.get('artifactPreview', p.get('previewId'))
            if row['workspaceId'] != p.get('workspaceId'):
                raise ValueError('This preview belongs to a different workspace.')
            if row['status'] != 'previewed':
                raise ValueError('This preview has already been generated. Create a new preview.')
            latest = self._collect(row['params'])
            if latest['digest'] != row['digest'] or latest['sourceDigest'] != row['sourceDigest']:
                raise ValueError('The inputs changed since preview. Review a fresh preview before generating.')
            root = self._root(row['workspaceId'])
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination = guarded(root, row['id'])
            if destination.exists():
                raise ValueError('This export already exists. Create a new preview.')
            with tempfile.TemporaryDirectory(prefix='.staging-', dir=root) as temporary:
                stage = Path(temporary)
                for relative, content in row['files'].items():
                    path = guarded(stage, '.agent/' + relative)
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    path.write_text(content, encoding='utf-8')
                    path.chmod(0o600)
                output = stage / 'output'
                command = [sys.executable, '-I', str(self._tool(row['kind'])), '--agent-root', str(stage / '.agent'),
                           '--out', str(output), '--project', row['project']]
                if row['kind'] == 'metrics':
                    command += ['--window', row['window'], '--bucket', row['bucket'], '--timezone', 'UTC']
                try:
                    result = subprocess.run(command, cwd=stage, env={'NO_COLOR': '1'}, capture_output=True,
                                            text=True, timeout=30, check=False)
                except subprocess.TimeoutExpired as exc:
                    raise ValueError('The local exporter timed out. Reduce the input size and preview again.') from exc
                if result.returncode:
                    raise ValueError('The local exporter could not process these inputs. Check the input formats and preview again.')
                audit = dict(previewId=row['id'], workspaceId=row['workspaceId'], kind=row['kind'],
                    approved=True, approvedAt=now_iso(), digest=row['digest'], sourceDigest=row['sourceDigest'],
                    recordCount=row['recordCount'], redactions=row['redactions'], window=row['window'], bucket=row['bucket'],
                    inputs=[dict(path=name, digest=digest(content), size=len(content.encode())) for name, content in row['files'].items()])
                (output / 'export-audit.json').write_text(encode(audit) + '\n', encoding='utf-8')
                produced, total = [], 0
                for path in sorted(output.rglob('*')):
                    checked = guarded(output, path.relative_to(output))
                    if checked.is_dir():
                        continue
                    content = read_bytes(output, path.relative_to(output))
                    total += len(content)
                    if len(produced) >= 500 or total > 32_000_000:
                        raise ValueError('Generated artifacts exceed the local export limit.')
                    checked.chmod(0o600)
                    produced.append((path.relative_to(output), content))
                output.rename(destination)
            artifacts = []
            for relative, content in produced:
                saved = self.store.create('artifact', dict(workspaceId=row['workspaceId'], previewId=row['id'],
                    path=str(destination / relative), relativePath=str(Path(row['id']) / relative), name=str(relative),
                    type=relative.suffix.lstrip('.') or 'text', kind=row['kind'], size=len(content), status='generated', digest=digest(content)))
                artifacts.append(self._public(saved))
            self.store.update('artifactPreview', row['id'], status='generated', approvedAt=audit['approvedAt'])
            return dict(text=f'Generated {len(artifacts)} local artifacts.', artifacts=artifacts, digest=row['digest'], kind=row['kind'])

    def read(self, p):
        identifier = p.get('artifactId')
        if isinstance(identifier, str) and identifier.startswith('existing:'):
            if len(identifier) > 4096:
                raise ValueError('Invalid existing artifact identifier.')
            fields = identifier.split(':', 3)
            if len(fields) != 4 or fields[1] != p.get('workspaceId'):
                raise ValueError('This artifact belongs to a different workspace.')
            _, wid, expected, relative = fields
            self.store.get('workspace', wid)
            if not any(relative.startswith(prefix + '/') and export_name(kind, relative[len(prefix) + 1:])
                       for kind, prefix in EXISTING_EXPORT_ROOTS.items()):
                raise ValueError('Invalid existing artifact path.')
            root = self.stack.root(wid)
            path = guarded(root, relative)
            content = read_bytes(root, relative)
            if digest(content) != expected:
                raise ValueError('This existing export changed. Refresh the export list before reading it.')
            try:
                return dict(text=content.decode('utf-8'), path=str(path), digest=expected,
                            type=path.suffix.lstrip('.') or 'text')
            except UnicodeError as exc:
                raise ValueError('This artifact is not readable UTF-8 text.') from exc
        row = self.store.get('artifact', p.get('artifactId'))
        if row['workspaceId'] != p.get('workspaceId'):
            raise ValueError('This artifact belongs to a different workspace.')
        path = guarded(self._root(row['workspaceId']), row['relativePath'])
        content = read_bytes(self.store.root, path.relative_to(self.store.root))
        if digest(content) != row['digest']:
            raise ValueError('This artifact changed since generation. Generate a new export to review verified content.')
        try:
            return dict(text=content.decode('utf-8'), path=str(path), digest=row['digest'], type=row['type'])
        except UnicodeError as exc:
            raise ValueError('This artifact is not readable UTF-8 text.') from exc
