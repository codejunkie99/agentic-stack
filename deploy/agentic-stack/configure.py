#!/usr/bin/env python3
"""Create deployment configuration without printing the generated credential."""
import argparse
import os
import re
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", help="DNS name pointing to your server, for example stack.example.com")
    args = parser.parse_args()
    labels = args.domain.split('.')
    if len(args.domain) > 253 or len(labels) < 2 or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels):
        parser.error("Enter a DNS hostname without a scheme, path or port.")
    target = Path(__file__).resolve().parent / ".env"
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.error("A .env file already exists. Edit it directly to preserve your current token.")
    with os.fdopen(fd, "w") as handle:
        handle.write(f"STACK_DOMAIN={args.domain}\nAGENTIC_CONTROL_TOKEN={secrets.token_urlsafe(48)}\n")
    print("Created private .env configuration. Its control token was not printed.")


if __name__ == "__main__":
    main()
