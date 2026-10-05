#!/usr/bin/env python3
"""Bundle the server without Git history, credentials, or local runtime data."""
import argparse
from pathlib import Path
import tempfile
import zipfile

from package_payload import build as stage_payload, output_path


def build(destination):
    root = Path(__file__).resolve().parents[1]
    destination = output_path(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='agentic-server-payload-') as temporary:
        payload = stage_payload(root, Path(temporary)/'agentic-stack')
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(payload.rglob('*')):
                if path.is_file() and not path.is_symlink():
                    archive.write(path, 'agentic-stack/'+path.relative_to(payload).as_posix())
            archive.writestr('agentic-stack/START-HERE.md',
                '# Host Agentic Stack\n\nOpen deploy/agentic-stack/README.md. '
                'This package includes the server, stack templates, agent adapters, Docker Compose and Caddy HTTPS configuration. '
                'It contains no account credentials or imported desktop memory.\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    print(build(parser.parse_args().output))
