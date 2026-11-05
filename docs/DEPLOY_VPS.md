# Deploying 3.0.0 on the Oracle Cloud server

## The server

From `deploy/survey.sh` on 5 November 2026:

- **System:** Oracle Linux 9.7, x86_64.
  - 2 CPUs and **498 MB of memory**, with 2 GB of swap (already in use).
  - 19 GB of disk free.
- **nginx 1.20, certbot, firewalld, SELinux:**
  - SELinux is enforcing, and nginx may already connect to local apps.
  - firewalld already allows http, https and port 8080.
- **The old Mzugoss site:**
  - 2.0.2 (`develop`) in `/home/tgk/projects/welfare_system`.
  - Run by `welfare.service` (gunicorn) on `127.0.0.1:5000`.
  - nginx serves it as `http://145.241.103.17:8080/`.
  - Its database is `instance/welfare_dev.db`.
- **Another app:** `itams`, at `https://itams-mbc.duckdns.org`, on `127.0.0.1:8081`.
- **No Docker.**

## The plan

With under 500 MB of memory shared by two apps, Docker, Postgres and Redis
would push the server into heavy swapping. So 3.0.0 runs the way the old
app does: a Python virtual environment, SQLite and a systemd service, with
one gunicorn worker using threads (about 150 MB).

3.0.0 goes **beside** the old app, not over it:

| | Old (2.0.2) | New (3.0.0) |
|---|---|---|
| Folder | `/home/tgk/projects/welfare_system` | `/home/tgk/projects/welfare-3` |
| Service | `welfare.service`, `127.0.0.1:5000` | `welfare3.service`, `127.0.0.1:5001` |
| Address | `http://145.241.103.17:8080` | `https://mzugoss.duckdns.org` |
| Database | `instance/welfare_dev.db` | `instance/welfare.db`, migrated from a copy |

The old site keeps running, untouched, until the switch-over in step 9.
Officers' accounts and passwords carry across. Members and contributions
come from the converted workbook, as in
[MZUGOSS_RUNBOOK.md](MZUGOSS_RUNBOOK.md).

Run everything below as `tgk` on the server, except where it says `sudo`.

---

## 1. Before you start

The code must be on GitHub: the server clones it from there. Note the tag or
branch being deployed (for example `v3.0.0`).

## 2. The domain

1. Sign in at <https://www.duckdns.org> with the account that holds
   `itams-mbc`.
2. Add the subdomain `mzugoss`, or another name if that's taken. Its IP is
   the same server, `145.241.103.17`.
3. Check it: `nslookup mzugoss.duckdns.org` answers `145.241.103.17`.

If you use a different name, change it everywhere below and in
`deploy/nginx-mzugoss.conf`.

Ports 80 and 443 are already open, in firewalld and in Oracle Cloud's
security list (certbot worked for itams), so there is nothing to open.

## 3. The code

```bash
cd /home/tgk/projects
git clone https://github.com/TgkCapture/welfare_system.git welfare-3
cd welfare-3
git checkout v3.0.0
python3.12 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt     # several minutes on this server
```

## 4. Settings

```bash
cp .env.example .env && chmod 600 .env
mkdir -p credentials
cp ../welfare_system/credentials/service_account.json credentials/   # if the old app has one
```

Edit `.env`. It holds `KEY=value` lines, with **no quotes**, and needs:

```
SECRET_KEY=<a new long random string: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:////home/tgk/projects/welfare-3/instance/welfare.db
GOOGLE_CREDENTIALS_PATH=/home/tgk/projects/welfare-3/credentials/service_account.json
TRUSTED_PROXIES=1
```

Delete or comment out the Docker-only lines: `POSTGRES_PASSWORD`, `GUNICORN_WORKERS` and `WEB_PORT`. Also delete the empty `GOOGLE_CREDENTIALS_JSON=` line.

Don't reuse the old app's `SECRET_KEY`. A new one only signs everyone out
once, which is fine.

## 5. The database

Stop officers adding or changing accounts on the old site from here on;
the new site gets a copy of them now.

```bash
# A consistent copy of the live database, while the old app keeps running
venv/bin/python -c "import sqlite3; s = sqlite3.connect('../welfare_system/instance/welfare_dev.db'); d = sqlite3.connect('instance/welfare.db'); s.backup(d); d.close()"

sh deploy/flask.sh db current            # no revision: the copy has no version yet
sh deploy/flask.sh db stamp 365dc0d4aa41 # once only: "this database is at the baseline"
sh deploy/flask.sh db upgrade
sh deploy/flask.sh db check              # "No new upgrade operations detected."
sh deploy/flask.sh list-users            # the old officers, now in the group mzugoss
sh deploy/flask.sh create-superadmin     # the platform account
```

The upgrade creates the group "Mzugoss Class of 2018" (`mzugoss`). It also:
- turns admins into Chairpersons and clerks into Treasurers
- deactivates viewer accounts
- carries over the sheet URL and the report retention setting

If anything fails, delete `instance/welfare.db` and start this step again.
The old database is never changed.

Then start the service:

```bash
sudo cp deploy/welfare3.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now welfare3
systemctl status welfare3 --no-pager
curl -s http://127.0.0.1:5001/api/health   # "status": "healthy", "version": "3.0.0"
```

## 6. nginx and HTTPS

```bash
sudo cp deploy/nginx-mzugoss.conf /etc/nginx/conf.d/mzugoss.conf
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d mzugoss.duckdns.org --redirect
```

certbot renews the certificate by itself, as it already does for itams.

Open `https://mzugoss.duckdns.org/api/health`, then sign in:
- an officer at `https://mzugoss.duckdns.org/g/mzugoss/login`
- the platform account at `/platform/login`

## 7. Set up Mzugoss

Follow runbook sections 4 and 5: the data source, the first sync, payout
purposes, rules, branding, PINs and links, and the checks. Delete
`admin@welfare.org` if `list-users` shows it.

## 8. Backups and updates

```bash
sh deploy/backup.sh        # try it once
crontab -e
# add:
15 1 * * *  cd /home/tgk/projects/welfare-3 && sh deploy/backup.sh >> backups/backup.log 2>&1
```

It keeps 14 days of database copies and file archives in `backups/`. Now
and then, copy them to another machine:

```bash
scp -r tgk@145.241.103.17:projects/welfare-3/backups .
```

To install a later version:

```bash
cd /home/tgk/projects/welfare-3 && sh deploy/update.sh v3.0.1
```

It backs up, installs, upgrades the database, restarts and checks health.
`update.sh` restarts the service with `sudo`, so it may ask for your
password.

## 9. Switching over

When the checks in runbook section 5 pass:

1. Stop the old app:
   `sudo systemctl disable --now welfare`
2. Send the old address to the new one. In `/etc/nginx/nginx.conf`, in the
   `server` block that listens on `8080`, replace the `location / { … }`
   that proxies to `127.0.0.1:5000` with:

   ```nginx
   return 301 https://mzugoss.duckdns.org$request_uri;
   ```

   then run `sudo nginx -t && sudo systemctl reload nginx`.
3. Tell officers and members the new address.
4. Keep `/home/tgk/projects/welfare_system`, including its database, for at least a year.

**Going back:** restore the old `location` block, then run
`sudo systemctl enable --now welfare`. The old database was never changed.

## Everyday commands

```bash
cd /home/tgk/projects/welfare-3
systemctl status welfare3 --no-pager
journalctl -u welfare3 -n 100 --no-pager           # recent log
sudo systemctl restart welfare3
sh deploy/flask.sh list-users --group mzugoss
sh deploy/flask.sh reset-password --group mzugoss --email <email>
free -h                                            # memory and swap
```

## On a bigger server

With 2 GB of memory or more, the Docker setup (app, Postgres and Redis) is
the better choice, because it runs several workers and makes backups with
`pg_dump`. Use `docker compose up -d --build` with the `.env` from
`.env.example`, and the scripts in [`deploy/docker/`](../deploy/docker/).
Oracle Cloud's free tier also offers Ampere (ARM) servers with far more
memory, on which this works unchanged.
