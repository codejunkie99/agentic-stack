# Container sandbox profiles

The Agentic Stack service runs as UID 1000 with `no-new-privileges` and Docker's
normal capability set. Codex applies its requested filesystem and network sandbox
to agent commands inside the container. Claude permission modes are not an OS sandbox.
Use one deployment per owner, with trusted projects and a dedicated Linux VM.

`seccomp.json` derives from Moby's default allowlist at:
https://raw.githubusercontent.com/moby/profiles/61eaf32614c7c71b60bd8927d3e6a4ffc8ff1f31/seccomp/default.json

The final rule permits `clone`, `unshare`, `setns`, `mount`, `umount2` and
`pivot_root` so bubblewrap can construct child namespaces. All other default
syscall restrictions remain. Linux capability checks still restrict these calls;
we add no capabilities and do not run the service as root. Moby's Apache 2.0
license is included in MOBY-LICENSE.

`agentic-stack-bwrap.apparmor` is a named profile applied only to this container.
It allows user namespaces and the mounts required by Codex while denying writes
to kernel control paths. This avoids Ubuntu's fallback `unprivileged_userns`
profile, which can deny namespace capabilities even when a container is labeled
`unconfined`. It does not modify Docker's global default profile or any sysctl.
The host must load the named profile before starting the container.

The setup script supports Linux with AppArmor and a parser that recognizes
`userns` (tested on Ubuntu 24.04 in the validation VM). It fails on unsupported
hosts rather than disabling a protection. The compose file also fails if the
profile is absent. Run `python3 sandbox-check.py` inside the image to validate
read-only and edit mode, writes outside the project, protected .git/.codex paths,
network denial, and the non-root/no-new-privileges configuration. No login or
model API call is needed for this check.
