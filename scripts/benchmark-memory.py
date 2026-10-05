#!/usr/bin/env python3
"""Run isolated, offline production retrieval with separate input/gold artifacts."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.memory_benchmark import adapt_longmemeval, run, compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--longmemeval', type=Path, help='Explicit local public dataset; never downloaded automatically')
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--gold', type=Path)
    parser.add_argument('--split', choices=['dev', 'held-out', 'all'], default='held-out')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--token-budget', type=int, default=4000)
    parser.add_argument('--variant', choices=['local', 'jev', 'jev-fast'], default='local')
    parser.add_argument('--public-live-jev', action='store_true', help='Explicitly permit provider requests with this public LongMemEval corpus only')
    parser.add_argument('--provider-root', type=Path, help='Configured provider root; read only with public live opt-in')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if bool(args.longmemeval) == bool(args.inputs) or bool(args.inputs) != bool(args.gold):
        parser.error('Provide --longmemeval OR both --inputs and --gold')
    if args.longmemeval:
        inputs, gold = adapt_longmemeval(json.loads(args.longmemeval.read_text()))
    else:
        inputs, gold = json.loads(args.inputs.read_text()), json.loads(args.gold.read_text())
    provider = None
    if args.public_live_jev or args.provider_root:
        if not args.public_live_jev or not args.provider_root or not args.longmemeval or args.variant == 'local':
            parser.error('Live requires --public-live-jev, --provider-root, --longmemeval and a Jev variant')
        from harness_manager.workspaces.jev_settings import ConfiguredJevProvider, JevSettings
        provider = ConfiguredJevProvider(JevSettings(args.provider_root))
        if not provider.available:
            parser.error('Configured public evaluation provider is unavailable')
    report = run(inputs, gold, split=args.split, repeats=args.repeats, token_budget=args.token_budget, variant=args.variant, provider=provider)
    if args.longmemeval:
        import hashlib
        report['dataset_file_sha256'] = hashlib.sha256(args.longmemeval.read_bytes()).hexdigest()
        report['dataset_name'] = args.longmemeval.name
    if args.baseline:
        report = compare(json.loads(args.baseline.read_text()), report)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'cases': len(report.get('split_ids', report.get('change', {}).get('split_ids', []))) }))


if __name__ == '__main__':
    main()
