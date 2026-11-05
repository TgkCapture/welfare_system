# Moving Mzugoss to 3.0.0

This runbook moves the live Mzugoss site from 2.0.x (a single group, SQLite,
reading the old MGSS workbook) to 3.0.0 (many groups, its own records of
members and contributions, reading the converted standard workbook).

Both upgrade paths below were rehearsed on databases created by the real
2.0.0 (`origin/main`) and 2.0.2 (`origin/develop`) code. Officers kept their
accounts and passwords, and they signed in afterwards.

**On the Oracle Cloud server, follow [DEPLOY_VPS.md](DEPLOY_VPS.md).** It
installs 3.0.0 beside the old app (Path B on a copy of the database, without
Docker, which that server is too small for) and refers back here for
setting up the group and the checks.

Plan for about two hours, at a quiet time. Members can't look anything up
while the site is down.

---

## 1. Before the day

Everything in this section can be done days ahead, without touching the live
site.

### 1.1 Finish the converted workbook

`conversion/MGSS_standard.xlsx` was made by `flask convert-legacy-workbook`. It
is git-ignored because it holds real member data. Its review report,
`conversion/MGSS_review.md`, lists what still needs a person:

- [ ] **Payouts.** Fill in the real date and purpose of each payout on the
      Payouts sheet. Until then each one is dated 31 December with the purpose
      "Unspecified", and every sync lists it as a warning.
- [ ] **Rates.** Confirm the month the 1,000 rate started. The converter
      guessed January 2025; correct the Rates sheet if that's wrong.
- [ ] **Joined and Left months.** Check the guessed months on the Members
      sheet.
- [ ] Re-run the conversion if you changed the old workbook instead of the
      new one:
      `flask convert-legacy-workbook MGSS.xlsx --merges conversion/MGSS_merges.csv --drop-repeated-payouts --group mzugoss`

### 1.2 Put the workbook where the app can read it

Either:
- **Google Sheets (recommended).** Upload `MGSS_standard.xlsx` to Google
  Drive, open it as a Google Sheet, and share it as a Viewer with the
  service account's email (the `client_email` in the key file). Note the
  sheet's URL.
- **Upload.** Officers upload the `.xlsx` file each month from the Upload
  page instead.

Keep the old MGSS sheet as it is: it's the record of everything before 3.0.0.

### 1.3 Choose a path

| | **A. Docker with Postgres** (recommended) | **B. In place on SQLite** |
|---|---|---|
| What changes | New containers on the server; the old app stays installed until you remove it | The same server and folder, with new code |
| Officers | Recreated in the new app (a few minutes each) | Kept, with their passwords |
| Old report records | Not carried over (their files expire after 7 days anyway; reports are regenerated from stored data) | Kept |
| Several workers, backups | Ready: shared rate limits, `pg_dump` | One server only |
| Undo | Stop the containers and start the old app | Put the database file back and check out the old code |

Members and contributions aren't in the old database either way: they come
from the workbook at the first sync.

### 1.4 Rehearse

Do the whole chosen path once on a copy, on any machine:

- **A:** run `docker compose up` locally with a test `.env` (see section 3),
  then do section 4 against it.
- **B:** copy the live database file, then:

  ```bash
  export DATABASE_URL=sqlite:////path/to/copy.db FLASK_APP=run.py
  flask db stamp 365dc0d4aa41    # once: "this database is at the baseline"
  flask db upgrade
  flask db check                 # "No new upgrade operations detected."
  ```

  Then sign in at `/g/mzugoss/login` with a real officer's email and password.

If anything fails, stop and keep the error. On SQLite a failed upgrade can
leave the copy half changed, so start again from a fresh copy.

### 1.5 Tell people

- Officers: the date, the new sign-in page (`/g/mzugoss/login`), and that
  viewer accounts end (members get PINs and personal links instead).
- Members: the site will be down for a short time.

---

## 2. On the day: freeze and back up

1. Stop the old app (however it's run: `systemctl stop …`, the terminal
   running `python run.py`, and so on).
2. Back up, and copy the backups off the server:
   - the database file, unless `DATABASE_URL` names another:
     `instance/welfare_dev.db` in 2.0.2, `instance/db.sqlite3` in 2.0.0
     (set in `instance/config.py`). On the Oracle server it is
     `/home/tgk/projects/welfare_system/instance/welfare_dev.db`.
   - `uploads/`, `reports/` and `logs/`
   - `instance/config.py`, `.env` and the `credentials/` key file
3. Write down the commit that's running (`git rev-parse HEAD`), so you can
   go back to it.

---

## 3. Path A: Docker with Postgres

On the server (Docker and the Compose plugin installed):

```bash
git clone https://github.com/tgkcapture/welfare_system.git welfare-3
cd welfare-3
git checkout <the 3.0.0 tag or branch>
cp .env.example .env
```

Fill in `.env`:
- `SECRET_KEY` and `POSTGRES_PASSWORD`: long random strings
  (`python3 -c "import secrets; print(secrets.token_hex(32))"`).
- `GOOGLE_CREDENTIALS_JSON`: the key file's JSON on one line. Or mount the
  file instead: see the comment in `docker-compose.yml`.
- `TRUSTED_PROXIES=1` when nginx (or Caddy) on the same server serves the site.

Start it and create the platform account:

```bash
docker compose up -d --build          # upgrades the database, then starts gunicorn
docker compose ps                     # web shows "healthy" after about 30 seconds
docker compose exec web flask create-superadmin
docker compose exec web flask create-group --name "Mzugoss Class of 2018" --slug mzugoss
docker compose exec web flask create-admin --group mzugoss   # the Chairperson
```

Point the web server at `127.0.0.1:8000` over HTTPS. Production cookies are
HTTPS-only, so signing in over plain HTTP won't work. For nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 16m;
}
```

The Chairperson then adds the other officers at **Officers**
(`/admin/users`). Deactivated viewer accounts aren't recreated.

Backups from now on:

```bash
docker compose exec -T db pg_dump -U welfare welfare | gzip > welfare-$(date +%F).sql.gz
```

---

## 3. Path B: in place on SQLite

On the server, in the app's folder, with its virtual environment active:

**Name the live database explicitly.** `instance/config.py` changed in 3.0.0:
without `DATABASE_URL` it points at a different, empty file, and the steps
below would run against that instead.

```bash
git fetch && git checkout <the 3.0.0 tag or branch>
pip install -r requirements.txt
export FLASK_APP=run.py
export DATABASE_URL=sqlite:////full/path/to/instance/welfare_dev.db   # the file backed up in section 2
flask db current                   # no revision listed: the live file has no version yet
sqlite3 "${DATABASE_URL#sqlite:///}" "select count(*) from users"   # your officers are there
flask db stamp 365dc0d4aa41        # once only: before 3.0.0 there were no migrations
flask db upgrade
flask db check                     # "No new upgrade operations detected."
flask move-files-to-groups         # old report files into reports/mzugoss/
flask create-superadmin
```

What the upgrade did:
- created the group "Mzugoss Class of 2018" (`mzugoss`)
- made admins Chairpersons and clerks Treasurers, and deactivated viewers
- copied the sheet URL and retention days into the group's settings
- turned on the members' access code
- added the welfare rules

Run it with gunicorn rather than `python run.py`:

```bash
FLASK_ENV=production gunicorn 'app:create_app()' --bind 127.0.0.1:8000 --workers 2 --timeout 120
```

Production needs `SECRET_KEY` and `DATABASE_URL` set in the environment.
If `git checkout` refuses because `instance/config.py` was edited on the
server, move it aside first (it's in the section 2 backup). 3.0.0 reads
everything it needs from the environment.

---

## 4. Set up Mzugoss in the new app

Sign in as the Chairperson at `/g/mzugoss/login`. The **Setup** page
(`/setup`) lists these steps.

1. **Data source.** In **Settings**, set the Google Sheet URL to the new
   standard workbook from 1.2, not the old MGSS sheet. Path B copied the old
   URL across, so change it.
2. **First sync.** From **Upload**, sync (or upload `MGSS_standard.xlsx`).
   Check:
   - every month's total matches the old sheet; `MGSS_review.md` lists them,
     and all 48 matched in the rehearsal
   - 63 members
   - the only warnings are the ones you expect, such as payouts not yet filled in
3. **Payout purposes** (Settings → Payout purposes): rename or add the
   group's own purposes. There's no fixed list.
4. **Rules** (Settings → Rules): check the welfare rules read correctly.
5. **Branding:** logo, colours and display name.
6. **Public pages** (Settings → Public pages): note the access code that
   members need for the paid list, or set your own.
7. **Members.** For each member, from their page under **Members**:
   - **Make a PIN.** The PIN is shown once, so give it to the member
     privately. They look up their history with their name and PIN at
     `/g/mzugoss/check`.
   - Or send their **personal link** (**Copy link**), which opens their
     history directly. Treat it like a password; **New link** cancels the old one.
8. **Officers.** Check each officer's role, and that everyone who can manage
   officers really should.

---

## 5. Check before telling members

- [ ] `https://<site>/api/health` returns `"status": "healthy"` and
      `"version": "3.0.0"`.
- [ ] Each officer can sign in at `/g/mzugoss/login`.
- [ ] `/g/mzugoss/` opens; the paid list asks for the access code and shows
      no defaulters.
- [ ] A test member can see their history by PIN and by personal link.
- [ ] A report for the latest month generates, and its totals match the sheet.
- [ ] **Audit log** (`/audit`) shows the sign-ins and changes above.
- [ ] Locked out? `flask list-users --group mzugoss` lists the accounts and
      `flask reset-password --group mzugoss --email <email>` sets a new password
      (with Docker, prefix both with `docker compose exec web`).
- [ ] **Remove `admin@welfare.org`** if it exists. 2.0.x created that account
      on its own, with a known password. Delete it under **Officers**.
- [ ] Backups run (section 3).

Then tell members: the address, the access code, and how to get their PIN or link.

---

## 6. If something goes wrong

- **Before members are told:** stop the new app, start the old one, and
  restore what changed:
  - Path A: the old app and its database weren't touched; just start it again.
  - Path B: put the backed-up database file back, `git checkout <old commit>`,
    and `pip install -r requirements.txt`.
- **After:** prefer fixing forward. The workbook is the source of truth, so
  correcting it and syncing again repairs the stored figures.
- Keep the old database backup and the old MGSS sheet for at least a year.

---

## 7. After the move

- [ ] Remove the old app's service and files (Path A), keeping the backups.
- [ ] Each month, officers update the standard workbook and sync. Uploads to
      the old MGSS sheet are no longer read.
- [ ] Platform support: when helping an officer, a superadmin opens a
      read-only support session from the group's page under `/platform/`.
      The group sees it in its audit log.
