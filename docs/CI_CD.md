# CI and deployment

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push
to `main`, `develop`, `feature/**`, `overhaul/**`, `fix/**` and `ci/**`, and
on every pull request. It runs four checks:

| Job | Checks |
|---|---|
| Tests (Python 3.12, 3.13) | The test suite on SQLite. 3.12 is the Oracle server's Python, 3.13 is Docker's. |
| Tests on Postgres | The same suite on Postgres 17, as the Docker setup runs it. |
| Migrations match the models | A new database built by `flask db upgrade` passes `flask db check`. |
| Docker image builds | `docker build` succeeds. |

To stop untested code reaching `main`: **Settings → Branches → Add rule** for
`main`, with *Require status checks to pass* (pick the four jobs).

## Deployment

[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) deploys
to the Oracle server:

```bash
git tag -a v3.0.1 -m "What changed" && git push origin v3.0.1
```

A deploy can also start from **Actions → Deploy → Run workflow**, with a tag
or branch. It:
1. runs CI
2. waits for approval, if the environment asks for it
3. runs [`deploy/update.sh`](../deploy/update.sh) on the server: back up, install, upgrade the database, restart, check health
4. checks the live site's `/api/health`

The first installation is done by hand ([DEPLOY_VPS.md](DEPLOY_VPS.md)); the
workflow only updates an installed site.

### One-time setup on the server

**1. Let `tgk` restart the service without a password**

Only that one command is allowed:

```bash
echo 'tgk ALL=(root) NOPASSWD: /usr/bin/systemctl restart welfare3' | sudo tee /etc/sudoers.d/welfare3
sudo chmod 440 /etc/sudoers.d/welfare3 && sudo visudo -cf /etc/sudoers.d/welfare3
```

**2. GitHub's deploy key, limited to updating**

Add one line to `/home/tgk/.ssh/authorized_keys`: the public key, behind a
forced command. Whatever GitHub sends is only ever passed to `update.sh` as
the version name, and `update.sh` rejects anything that isn't one. The key
can't open a shell or forward ports.

```
command="cd /home/tgk/projects/welfare-3 && sh deploy/update.sh \"$SSH_ORIGINAL_COMMAND\"",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA… github-actions deploy welfare_system
```

### One-time setup on GitHub

**Settings → Environments → New environment → `production`**:
- **Required reviewers:** yourself. Each deploy then waits for your
  approval. Optional, but recommended.
- **Deployment branches and tags:** *Selected*, adding `v*` (tags) and
  `main`.
- **Environment secrets:**
  - `VPS_SSH_KEY`: the deploy key's private half, the whole file including
    the `BEGIN` and `END` lines.
  - `VPS_KNOWN_HOSTS`: the output of `ssh-keyscan -t ed25519 145.241.103.17`,
    run from a machine you trust, or copied from your own `known_hosts`.
    Deploys refuse to connect to anything else.
- **Environment variables:**
  - `VPS_HOST`: `145.241.103.17`
  - `VPS_USER`: `tgk`
  - `SITE_URL`: `https://mzugoss.duckdns.org`

### If a deploy fails

The log shows each step. If the server step failed, `update.sh` already
printed the version to go back to. Run it again with that version, from
**Run workflow** or on the server:

```bash
cd /home/tgk/projects/welfare-3 && sh deploy/update.sh <previous version>
```

If a migration changed the database, restore the backup that `update.sh`
made first (`backups/`, newest file); see the end of `deploy/backup.sh`.
