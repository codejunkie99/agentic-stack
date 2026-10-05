# Host Agentic Stack

The native Agentic Stack app can manage a stack on your Mac or connect to a persistent server. The server owns its projects, agent sign-ins, skills, memory and task history. Closing the desktop does not stop a hosted service. Switching hosts does not copy data or credentials between them.

This is a single-owner service. Its control token grants administrative access, including running agents and modifying projects. It is not a multi-tenant SaaS login or a public browser application.

## Docker Compose with HTTPS

Use **Hosting → Export server package** in the desktop, then unzip that package
on the server. It includes the runtime and deployment files. The source checkout
works too. Your desktop knowledge graph and account credentials are not included.

Prerequisites: an Ubuntu 24.04 server (or a compatible Linux host with AppArmor
user-namespace support), Docker Engine and Compose, a DNS hostname pointing to it,
and inbound ports 80 and 443. Use a dedicated VM for this single-owner service.
The included Caddy proxy handles certificate issuance and renewal when these
prerequisites are met. See [Caddy's automatic HTTPS requirements](https://caddyserver.com/docs/automatic-https).

From this checkout:

```sh
cd deploy/agentic-stack
sudo sh install-sandbox.sh
python3 configure.py stack.example.com
docker compose up --build -d
docker compose ps
docker compose exec stack python3 /app/sandbox-check.py
```

`configure.py` creates a private `.env` file containing a random control token. It refuses to overwrite an existing configuration. Open that file in your trusted editor and copy the token into the desktop's **Hosting → Connect a server** form. Enter `https://stack.example.com` and select **Test and connect**. Do not paste the token into a chat or commit `.env`.

The API port is exposed only to the Compose network; public traffic enters through HTTPS. The service rejects browser-origin requests. Bearer tokens are removed from the server process environment before agent subprocesses are launched. Docker administrators can still inspect deployment environment variables; treat server access as administrative access.

The image includes the official Codex and Claude Code CLIs. Authenticate on the server:

```sh
docker compose exec stack codex login --device-auth
docker compose exec stack claude auth login
```

Follow the official CLI's instructions to finish browser sign-in, then select **Agents → Refresh agents** in the desktop. For Claude callbacks that require localhost, use the forwarding instructions in its CLI or authenticate from an interactive server session. The app does not export sign-ins from your Mac or implement a separate provider OAuth client.

The sandbox preflight makes no model API call. It checks both read-only and
project-edit modes, protected Git/Codex paths, writes outside the project and
direct network denial. It also verifies the service is non-root with no effective
capabilities, seccomp filtering, no-new-privileges and its named AppArmor profile.
Run it after deployment and CLI upgrades, before starting agent tasks.

Docker's stock policies block Codex's nested sandbox on some hosts. This package
uses a dedicated AppArmor profile and Moby's default seccomp allowlist with six
namespace/mount calls enabled. It adds no capabilities, does not disable Codex's
sandbox, and does not change host sysctls or Docker's global default profile.
The named profile persists across host restarts. Unsupported hosts fail the
setup or preflight instead of falling back to unrestricted execution. See the
[profile details and source attribution](SECURITY-PROFILES.md) and OpenAI's
[container documentation](https://github.com/openai/codex/blob/main/.devcontainer/README.md).

Clone a project on the server:

```sh
docker compose exec stack git clone https://github.com/OWNER/REPO.git /data/projects/my-project
```

Use **Open project** in the desktop and enter `/data/projects/my-project`. Authentication for a private Git repository must be configured on the server separately. The desktop's project picker is restricted to `/data/projects` for attached repositories. New managed projects live in the service's persistent data directory.

Named volumes retain the database, projects, agent configuration and Caddy certificates across container restarts. Back them up along with your private deployment configuration. `docker compose down` stops the service; **do not add `-v` unless you intend to delete its data**. Updates use `docker compose up --build -d` from your updated checkout. Running local-agent tasks are interrupted by a server restart and are reported as interrupted after recovery.

## Private server through an SSH tunnel

Docker and a public domain are optional. On a server with Python 3.10+, this checkout, and the official agent CLIs installed:

```sh
python3 -c 'import os,secrets; fd=os.open("control-token",os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.write(fd,secrets.token_urlsafe(48).encode()); os.close(fd)'
python3 -m harness_manager.cli serve --data-root ./server-data --project-root /srv/projects --token-file ./control-token --port 8765
```

Keep that service running with your server's process manager. On the Mac:

```sh
ssh -N -L 8765:127.0.0.1:8765 user@your-server
```

Connect the desktop to `http://127.0.0.1:8765` with that token. The client permits plain HTTP only on localhost and refuses redirects so it does not forward credentials to a different endpoint. The server defaults to localhost. A network bind requires `--allow-network`; put TLS in front of it.

## Scope and verification

The desktop uses the same RPC operations locally and remotely. Project selection, adapter installation, skill editing, memory inspection, maintenance and agent tasks run on the selected host. Codex uses its requested sandbox mode; Claude uses its plan or accept-edits permission mode. Container support for the CLI's own sandbox must be validated on your host; the app never silently disables that sandbox.

Box remains an optional execution provider, separate from hosting the stack service. Appllama is optional design research, not a runtime dependency.

The image was built and tested in a local Linux VM: non-root startup, authenticated
readiness, invalid-token rejection, initialized-project persistence after restart,
both CLI versions, and HTTPS through Caddy with an explicit test CA passed.
The final profiles also passed the actual Codex sandbox preflight in both modes,
including denied operations. Public TLS issuance and signed-in agent runs still
require validation on the deployment host.
The application is currently ad-hoc signed, not Apple-notarized.
