#!/usr/bin/env python3
"""Sign a macOS bundle, including embedded Python and Sparkle code."""

import argparse
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess


MACHO = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"}
FAT = {b"\xca\xfe\xba\xbe": ">I", b"\xbe\xba\xfe\xca": "<I",
       b"\xca\xfe\xba\xbf": ">Q", b"\xbf\xba\xfe\xca": "<Q"}
BUNDLES = {".app", ".xpc", ".framework", ".bundle", ".appex"}


def is_macho(path):
    with path.open("rb") as stream:
        header = stream.read(24)
        if header[:4] in MACHO:
            return True
        if len(header) < 24 or header[:4] not in FAT:
            return False
        # FAT_MAGIC also starts Java class files; require a real Mach-O slice.
        format = FAT[header[:4]]
        count = struct.unpack(format[0] + "I", header[4:8])[0]
        if not 0 < count <= 128:
            return False
        offset = struct.unpack(format, header[16:16 + struct.calcsize(format)])[0]
        if offset > os.fstat(stream.fileno()).st_size - 4:
            return False
        stream.seek(offset)
        return stream.read(4) in MACHO


def developer_identity(identity):
    result = subprocess.run(["security", "find-identity", "-v", "-p", "codesigning"],
                            check=True, capture_output=True, text=True)
    matches = {digest for digest, name in re.findall(
        r'^\s*\d+\)\s+([0-9A-Fa-f]{40})\s+"([^"]+)"\s*$', result.stdout, re.MULTILINE)
        if name.startswith("Developer ID Application: ")
        and (identity == name or identity.casefold() == digest.casefold())}
    if len(matches) != 1:
        raise ValueError("Signing identity must uniquely match a valid Developer ID Application "
                         "certificate name or full SHA-1 in the keychain.")
    return matches.pop()


def signing_targets(app):
    """Preflight the whole tree before signing, without following directory links."""
    app = Path(app).resolve(strict=True)
    binaries, bundles = set(), [app]

    def contained(path):
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(app):
            raise ValueError(f"Bundle symlink escapes app: {path}")
        return resolved

    def walk_error(error):
        raise error

    for directory, dirs, files in os.walk(app, followlinks=False, onerror=walk_error):
        parent = Path(directory)
        for name in sorted(dirs + files):
            path = parent / name
            if path.is_symlink():
                contained(path)
            elif path.is_dir() and path.suffix in BUNDLES:
                bundles.append(path)
            elif path.is_file() and is_macho(path):
                binaries.add(path)
        dirs[:] = sorted(name for name in dirs if not (parent / name).is_symlink())

    targets = set(binaries)
    executables = set()
    for bundle in bundles:
        info_path = bundle / ("Resources/Info.plist" if bundle.suffix == ".framework"
                              else "Contents/Info.plist")
        if not info_path.exists():
            info_path = bundle / "Info.plist"
        if not info_path.exists():
            if bundle == app:
                raise ValueError(f"Missing app Info.plist: {bundle}")
            continue
        info = plistlib.loads(contained(info_path).read_bytes())
        name = info.get("CFBundleExecutable")
        if not name:
            if bundle == app:
                raise ValueError(f"Missing app CFBundleExecutable: {bundle}")
            continue  # Resource-only bundles are sealed by their enclosing app.
        if not isinstance(name, str) or name in {".", ".."} or Path(name).name != name:
            raise ValueError(f"Invalid CFBundleExecutable: {info_path}")
        executable = bundle / "Contents" / "MacOS" / name
        if not executable.exists():
            executable = bundle / name
        executable = contained(executable)
        if executable not in binaries or not executable.is_relative_to(bundle):
            raise ValueError(f"Bundle executable is not contained Mach-O code: {bundle}")
        if executable in executables:
            raise ValueError(f"Multiple bundles share an executable: {executable}")
        executables.add(executable)
        targets.add(bundle)
    # Signing a container signs its main executable. Never change it afterwards.
    targets.difference_update(executables)
    sparkle_order = {"Installer.xpc": 0, "Downloader.xpc": 1, "Autoupdate": 2, "Updater.app": 3}
    return sorted(targets, key=lambda path: (-len(path.parts),
                                           sparkle_order.get(path.name, 4), str(path)))


def sign(app, identity):
    app = Path(app).resolve(strict=True)
    if not app.is_dir() or app.suffix != ".app":
        raise ValueError(f"Not an app bundle: {app}")
    if not identity or identity == "-":
        # Keep preview signing unchanged: hardened ad-hoc code breaks Sparkle.
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    else:
        identity = developer_identity(identity)
        targets = signing_targets(app)
        for target in targets:
            command = ["codesign", "--force", "--sign", identity, "--timestamp", "--options", "runtime"]
            # Sparkle >= 2.6 may ship optional Downloader sandbox entitlements.
            # https://sparkle-project.org/documentation/sandboxing/#code-signing
            if target.name == "Downloader.xpc" and any(
                    parent.name == "Sparkle.framework" for parent in target.parents):
                command.append("--preserve-metadata=entitlements")
            subprocess.run([*command, str(target)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


def self_check():
    """Exercise planning and failure behavior without accessing signing credentials."""
    import tempfile
    from types import SimpleNamespace
    from unittest.mock import patch

    with tempfile.TemporaryDirectory(prefix="agentic-sign-check-") as temporary:
        app = Path(temporary).resolve() / "Space Name.app"

        def binary(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xcf\xfa\xed\xfe" + bytes(28))
            return path

        def bundle(path, name):
            binary(path / "Contents/MacOS" / name)
            (path / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": name}))
            return path

        bundle(app, "Main")
        framework = app / "Contents/Frameworks/Sparkle.framework"
        version = framework / "Versions/B"
        binary(version / "Sparkle")
        (version / "Resources").mkdir()
        (version / "Resources/Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "Sparkle"}))
        (framework / "Versions/Current").symlink_to("B")
        (framework / "Sparkle").symlink_to("Versions/Current/Sparkle")
        (framework / "Resources").symlink_to("Versions/Current/Resources")
        installer = bundle(version / "XPCServices/Installer.xpc", "Installer")
        downloader = bundle(version / "XPCServices/Downloader.xpc", "Downloader")
        updater = bundle(version / "Updater.app", "Updater")
        autoupdate = binary(version / "Autoupdate")
        python = app / "Contents/Resources/python"
        extension = binary(python / "lib/native module.so")
        library = binary(python / "lib/libpython.dylib")
        executable = binary(python / "bin/python3.11")
        (python / "bin/python3").symlink_to("python3.11")
        probe = Path(temporary) / "header-probe"
        for magic, format in FAT.items():
            probe.write_bytes(magic + struct.pack(format[0] + "I", 1) + bytes(8)
                              + struct.pack(format, 32) + bytes(32 - 16 - struct.calcsize(format))
                              + b"\xcf\xfa\xed\xfe" + bytes(28))
            assert is_macho(probe)
        probe.write_bytes(b"\xca\xfe\xba\xbe" + struct.pack(">I", 65) + bytes(16))
        assert not is_macho(probe)  # Java class header.
        targets = signing_targets(app)
        assert set(targets) == {app, framework, installer, downloader, updater, autoupdate,
                                extension, library, executable}
        assert targets.index(installer) < targets.index(downloader) < targets.index(autoupdate)
        assert targets.index(autoupdate) < targets.index(updater) < targets.index(framework) < targets.index(app)
        identity, digest = "Developer ID Application: Test (TEAM)", "A" * 40
        valid = SimpleNamespace(stdout=f'  1) {digest} "{identity}"\n')
        with patch.object(subprocess, "run", return_value=valid) as run:
            sign(app, identity)
            commands = [call.args[0] for call in run.call_args_list]
            assert commands[0] == ["security", "find-identity", "-v", "-p", "codesigning"]
            assert [command[-1] for command in commands[1:-1]] == list(map(str, targets))
            assert all("--timestamp" in command and "runtime" in command and "--deep" not in command
                       for command in commands[1:-1])
            assert [command[-1] for command in commands if "--preserve-metadata=entitlements" in command] == [str(downloader)]
            assert all(call.kwargs["check"] for call in run.call_args_list)
            assert developer_identity(digest.lower()) == digest
        with patch.object(subprocess, "run") as run:
            sign(app, "-")
            assert [call.args[0] for call in run.call_args_list] == [
                ["codesign", "--force", "--deep", "--sign", "-", str(app)],
                ["codesign", "--verify", "--deep", "--strict", str(app)]]
        with patch.object(subprocess, "run", return_value=SimpleNamespace(stdout="")) as run:
            try:
                sign(app, "Apple Development: Test")
                raise AssertionError("Invalid identity accepted")
            except ValueError:
                assert run.call_count == 1
        with patch.object(subprocess, "run", side_effect=[valid, subprocess.CalledProcessError(1, "codesign")]) as run:
            try:
                sign(app, identity)
                raise AssertionError("Signing failure ignored")
            except subprocess.CalledProcessError:
                assert run.call_count == 2
        (python / "outside").symlink_to(temporary)
        try:
            signing_targets(app)
            raise AssertionError("Escaping symlink accepted")
        except ValueError:
            pass
    print("Signing self-check passed (mocked codesign; no credentials used).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", type=Path)
    parser.add_argument("--identity", default=os.environ.get("AGENTIC_SIGNING_IDENTITY") or "-")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    elif args.app is None:
        parser.error("app is required unless --self-check is used")
    else:
        try:
            sign(args.app, args.identity)
        except (OSError, ValueError, RuntimeError, plistlib.InvalidFileException, subprocess.CalledProcessError) as error:
            parser.exit(1, f"Signing failed: {error}\n")
