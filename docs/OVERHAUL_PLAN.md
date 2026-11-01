# Multi-Group Overhaul Plan

Branch: `feature/multi-group-overhaul`

## Goal

Turn the Mzugoss-only welfare system into a single deployment that serves
many independent welfare groups. Each group has its own officers, members,
reports, settings, branding, rules and contribution terms. Also improve the
parsing logic, the UI and the overall flow.

## Decisions

| Area             | Decision |
| ---------------- | -------- |
| Tenancy          | One app, many groups. Every tenant-owned row carries `group_id`. Groups are fully independent and never share data. |
| Accounts         | Only **officers** have accounts (treasurer, secretary, chair, and so on). Contributing members have **no accounts**. |
| Roles            | Permission-based. Each group defines its own named roles and chooses their permissions. The superadmin manages groups. |
| Identity         | An account belongs to exactly one group. Email is unique **within a group**. The same person may hold separate, unrelated accounts in different groups. Login is per group. |
| Data source      | Spreadsheets (Excel or Google Sheets) stay the source of truth. A new **standard workbook template** is the recommended layout. A column mapping per group still supports older layouts. Each sync's results are **stored** in the DB to support history and public pages. |
| Payouts          | Recorded in the workbook's **Payouts** sheet, one row per payout, with date, beneficiary, purpose, amount and approver. Payout purposes are configured per group in the app. |
| Balances         | Carry-overs and balances are **calculated**, never typed. The app recalculates them on every sync and warns when the sheet's own figures disagree. |
| Public pages     | A public paid-members page per group. **Defaulters are never shown publicly.** |
| Member history   | Two routes to a member's history, both without accounts: a **personal private link**, and a **name + PIN lookup**. |
| Group config     | Branding, welfare rules, contribution terms, own Google Sheet, and public page settings. |
| Payments         | Members do not pay through the platform. The system only reports contributions. |
| UI               | Server-rendered Jinja with Tailwind (shared design system) and htmx for interactivity. |

## Current state (problems to fix)

- "Mzugoss" / "MZUGOSS CLASS OF 2018" is hard-coded in about 30 templates,
  2 JS files, `pdf_service.py`, `report_generator.py` and `report_controller.py`.
- Welfare rules are hard-coded HTML (`welfare_rules.html`,
  `welfare_rules_pdf.html`) and also in `pdf_service.py`.
- `ExcelParser` assumes the Mzugoss layout: one sheet per year, a month
  header row, and name and month columns found heuristically.
- Parsed data is thrown away after each report is generated, so there is no history.
- `Setting` is global (`google_sheets_url`, `report_retention_days`).
- The roles `admin`, `clerk` and `viewer` are fixed. Viewers self-register publicly.
- `User.email` is unique across the whole system. `User` and `GeneratedReport`
  have no group ownership.
- No migrations: the schema is created with `db.create_all()`.
- Two PDF engines produce the same report (fpdf2 in `report_generator.py`,
  reportlab in `pdf_service.py`).
- One CSS file and one JS file per page, with no shared design system.
- No tests. `requirements.txt` is UTF-16. The README's run instructions are wrong.

---

## Phase 0: Foundations

Everything later depends on this phase.

- [x] Re-encode `requirements.txt` as UTF-8. Add Flask-Migrate (Alembic).
      pytest goes in `requirements-dev.txt`. Flask-Limiter is moved to
      Phase 1, where it is first used.
- [x] Set up Flask-Migrate. Create a baseline migration (`365dc0d4aa41`)
      that matches the current schema. Existing databases run
      `flask db stamp 365dc0d4aa41` once. `db.create_all()` is removed from
      startup.
- [x] Add a pytest suite: an app fixture with an isolated in-memory DB (the
      instance config is ignored under test), synthetic Mzugoss workbooks,
      characterisation tests for the parser, and an end-to-end upload test.
- [x] Rebuild the synthetic fixture to mirror the real MGSS.xlsx layout, using
      invented names. Add an optional test against the real workbook
      (`MZUGOSS_WORKBOOK=MGSS.xlsx pytest`), which is skipped unless the file
      is present. Real workbooks are git-ignored and never committed.
- [x] Keep a single PDF engine (reportlab) and remove fpdf. This also fixes
      the uploaded PDF listing zero-amount members as paid.
- [x] Clean up small issues: `_safe_col` (fixes a `NameError` on the
      missing-month error path), the unused `_read_version`, and the README.

## Phase 1: Multi-tenancy, officers and permissions

Delivered in steps: **1a** models and data migration (done), **1b** login
and permissions (done), **1c** tenant scoping, **1d** management screens,
**1e** per-group files and settings.

Step 1a delivered:
- `Group`, `GroupSettings`, `Role` (fixed permission list, preset roles),
  and `group_id` / `role_id` / `is_superadmin` on users. Reports and access
  logs require a `group_id`. Email is unique per group.
- Migration `808c6b6f7843` moves an existing install into a "Mzugoss"
  group (admin → Chairperson, clerk → Treasurer, viewer → deactivated) and
  copies the sheet URL and retention days into its settings.
- CLI: `create-group`, `create-admin --group`, `create-superadmin`.
- Public registration removed (pulled forward from 1b so no account can
  be created without a group).
- Transitional: the legacy `User.role` string still drives permission
  checks; 1b switches to `group_role` and drops the column. Until 1b adds
  per-group login, the CLI rejects an email already used by any account.
- Fixed while testing: the admin cleanup page (wrong template path,
  missing `intcomma` filter, missing `storage_stats`), and broken redirects
  to `main.report_preview*` endpoints that don't exist.

Step 1b delivered:
- Permissions come from the officer's group role. `role_required` and the
  legacy `User.role` column are gone (migration `eecde90015d7`; its
  downgrade rebuilds the column from the roles).
- Logins: officers at `/g/<slug>/login` (email looked up within that group
  only), superadmins at `/platform/login`, and `/auth/login` is a group
  finder that remembers the last group. Logout returns to the right page.
  A suspended group's officers are signed out.
- `next` redirects only accept paths on this site. Login POSTs share one
  rate limit per IP (`LOGIN_RATE_LIMIT`, default 10/min and 50/hour);
  unknown emails take as long as wrong passwords.
- Officer management is one screen gated by `manage_users`, with the grant
  guardrail and the last-manager rule. The clerk "viewer" screens are removed.
- Officers with `view_reports` see all of their group's reports; archived
  reports need `manage_reports`. Report statistics and export cover only the
  officer's group. `CLERKS_SEE_ALL_REPORTS` is removed.
- File cleanup, storage status and bulk report cleanup are superadmin-only
  until 1e makes them per-group (they currently act on every group's files).
- Platform area at `/platform/` (read-only list of groups for now). This
  replaces the `/admin/login` idea, since `/admin/...` holds group pages.
- Tests: each test request now gets its own app context, as in production.

- [ ] New `Group` model: `id`, `name`, `slug`, `is_active`, `created_at`.
- [ ] New `GroupSettings` model, one per group, holding:
  - Branding: display name, short name, logo path, primary colour, report title.
  - Contribution terms: monthly amount, currency, due day, grace days, and the
    rule for when a member counts as paid (full amount, any amount, or at
    least X).
  - Data source: Google Sheet URL, upload enabled, and the column mapping
    (see Phase 2).
  - Public page options (see Phase 4).
  - Retention days.
- [ ] Permissions are a fixed list defined by the platform:
      `upload_data`, `generate_reports`, `manage_reports`, `view_reports`,
      `manage_members`, `edit_rules`, `edit_settings`, `manage_users`.
- [ ] New `Role` model scoped to a group: `group_id`, `name` (for example
      "Treasurer"), and its set of permissions. New groups are seeded with
      preset roles (Chairperson, Treasurer, Secretary), which the group can
      rename, edit or delete.
- [ ] Rework `User` (officers only):
  - Add `group_id`, which is nullable only for superadmins, and `role_id`.
  - Replace the global email uniqueness with `UNIQUE(group_id, email)`.
  - Add an `is_superadmin` flag for platform operators.
- [x] Guardrail: a user can only grant permissions they hold themselves, and
      the last user holding `manage_users` in a group cannot be removed or demoted.
- [x] Replace `role_required` with a `permission_required` decorator
      everywhere, and add a `superadmin_required` decorator.
- [x] Remove public self-registration and the viewer role.
- [x] Per-group login at `/g/<slug>/login`, with the group's branding on the page.
      The superadmin logs in at `/platform/login`.
- [x] Fix the open redirect in login: only follow a `next` URL that points
      to this site. Add Flask-Limiter rate limits on login.
- [ ] Tenant scoping:
  - Resolve the current group from `current_user.group_id`, and store it in `g.group`.
  - Add a query helper (`Model.for_group(g.group)`) and use it in every controller.
  - Add tests that check one group's data is never visible to another group.
- [ ] Superadmin tooling: create, suspend and edit groups, create a group's
      first officer, and switch into a group's context for support.
- [ ] Group-aware file storage: `uploads/<group_slug>/...` and
      `reports/<group_slug>/...`. Cleanup respects each group's retention.
      Retention covers files only. Stored contribution data is kept forever.
- [ ] Data migration:
  - Create the "Mzugoss" group.
  - Map the existing users: `admin` → Chairperson-like role with all
    permissions, `clerk` → Treasurer, `viewer` → deactivated (or deleted after review).
  - Attach all existing reports to the group.
  - Copy the existing settings and branding into its `GroupSettings`.

## Phase 2: Standard workbook, configurable parsing and stored data

### Findings from the real Mzugoss workbook (MGSS.xlsx)

- The current parser matches the sheet's own Total row in all 48 months of 2023–2026.
- Payouts have no date, purpose or approver. Each is just an amount in a
  "DISPENSED TO" column, and a repeat payout needs a new column (P).
- **Confirmed mistakes** caused by hand-maintained totals:
  - Three 2025 payouts (36,760) were repeated in 2026.
  - The carry-overs disagree with the previous year's closing balance:
    +2,000 into 2024, and −16,000 into 2026.
  - The 2023 carry-over row is mislabelled "2024 Carry Over".
  - The 2025 dispensed formula only sums rows 7–49, but members run to row 59.
- The rate changed from 500 to 1,000 in 2025. Any amount above 0 counts as
  paid today, so partial payments are reported as paid.
- Members are counted as defaulters for months before they joined.
- Name spellings drift between years (for example, double spaces and short forms).

### Standard workbook template

| Sheet | One row per | Columns |
| ----- | ----------- | ------- |
| `Members` | member | Member ID, Name, Phone (optional), Joined (month), Left (month), Notes |
| `Contributions YYYY` | member | Member ID, Name (lookup), January … December. Payments only, with no totals or financial rows. |
| `Payouts` | payout | Date, Member ID / beneficiary, Purpose (dropdown), Amount, Approved by, Notes |
| `Rates` | rate change | Effective from, Monthly amount |
| `Summary` | year | Opening balance (= previous closing), contributions, payouts by purpose, closing balance. Formulas only. |

- [ ] Per-group payout purposes, managed in the app (for example funeral
      condolence, wedding gift, sick patient grant).
- [ ] The app generates a blank template for a group, with data-validation
      dropdowns (purposes, member IDs) and the Summary formulas filled in.
- [ ] A parser for the standard template.
- [ ] Sync-time checks with clear warnings:
  - The opening balance must equal the previous closing balance.
  - The sheet's Summary must equal the app's calculation.
  - Payouts must have a known purpose, a known member and a date inside the year.
  - Duplicate payouts (same beneficiary, amount and date).
  - Contributions recorded before a member joined or after they left.
- [ ] Payment status uses the rate for the period: paid / partial / unpaid,
      and "not a member yet" before the joined month.
- [ ] **Convert MGSS.xlsx** to the standard template with a one-off script:
  - Correct the confirmed mistakes.
  - Older payouts with no date or purpose import as
    "Unspecified (year)", for the treasurer to fill in.
  - Produce a name-merge list for the user to confirm.
  - The user reviews the converted workbook before Mzugoss switches over.

### Parsing and storage

- [ ] Split `ExcelParser` into two parts:
  - A layout reader driven by a per-group `SheetMapping`.
  - A calculator that applies the group's contribution terms.
- [ ] `SheetMapping` options:
  - Sheet selection: one sheet per year (name pattern), a single sheet, or a
    named sheet.
  - Header row: a fixed row number, or auto-detect.
  - Member name column.
  - Month columns: by header name, or by the column index of January.
  - Location of the financial summary cells (money dispensed, book balance),
    or "not present".
- [ ] Add a mapping wizard (htmx): upload a sample, preview the detected
      headers, pick columns, see a live parse preview, then save.
- [ ] Save the Mzugoss layout as the default preset, so existing behaviour is
      unchanged.
- [ ] Return validation errors that say which row or column is wrong, instead
      of a generic failure.
- [ ] Google Sheets: each group uses its own URL, and the cache is keyed per
      group. Credentials stay platform-wide: each group shares its sheet with
      the platform service account, and the UI shows that account's email.
- [ ] Store each sync's results. The spreadsheet remains the source of truth,
      and the DB holds a read-model of it.
  - `Member`: `group_id`, `display_name`, `normalised_name`, `is_active`,
    `history_token` (unguessable, can be revoked), `pin_hash`,
    `pin_failed_attempts`, `pin_locked_until`.
  - `MemberAlias`: alternative spellings that map to one `Member`.
  - `Contribution`: `group_id`, `member_id`, `year`, `month`, `amount`,
    `status` (paid / partial / unpaid), `synced_at`.
    Unique on `(member_id, year, month)`.
  - `PeriodSummary`: `group_id`, `year`, `month`, totals, money dispensed,
    book balance, `synced_at`.
- [ ] A sync updates the stored contributions and summary for that period,
      and can backfill all years present in the workbook.
- [ ] Member matching: exact match on the normalised name, then on aliases.
      Names that don't match are listed for an officer to either "merge into
      an existing member" or "create a new member".
- [ ] Members screen (`manage_members`): list, rename, merge, deactivate,
      copy a personal link, regenerate the link, and set or reset the PIN.
- [ ] Reports (PDF and PNG) are generated from the stored data, not straight from the file.

## Phase 3: Group-configurable content

- [ ] Welfare rules stored per group as sections in the DB (title, body in
      Markdown), edited by officers with `edit_rules`. The rules page and the
      rules PDF are both rendered from this one source.
- [ ] Mzugoss rules seeded from the current hard-coded content.
- [ ] Branding used everywhere: the layout header, page titles, PDF and PNG
      report headers, download filenames and error pages. No hard-coded
      group names should remain (enforced by a test that greps for them).

## Phase 4: Public member-facing pages (no accounts)

All public pages live under `/g/<slug>/`. They show the group's branding,
send `noindex` to search engines, and display when the data was last updated.

- [ ] **Group landing** at `/g/<slug>`: group name, links to the rules, the
      paid list and "check my contributions".
- [ ] **Rules** at `/g/<slug>/rules`.
- [ ] **Paid members** at `/g/<slug>/paid?year=&month=`:
  - Shows paid members only. **Defaulters and unpaid members are never shown
    on any public page.**
  - Group options: enabled or disabled; show names only, or names and
    amounts; show or hide group totals; how many past months can be browsed.
  - A **group access code**, **on by default** for new groups and
    generated when the group is created: one shared code that the officers
    post in the group chat, entered once and remembered in the visitor's
    session. Officers can change it or turn it off.
- [ ] **Personal history link** at `/g/<slug>/m/<history_token>`:
  - Shows that member's month-by-month status and amounts for every stored
    year, with yearly totals.
  - The token is long and random. Officers can copy it or regenerate it,
    which cancels the old link.
- [ ] **Name + PIN lookup** at `/g/<slug>/check`:
  - The member enters their name (matched against the name and aliases) and
    a PIN set by an officer. Success shows the same history view.
  - The PIN is stored hashed and is never derived from spreadsheet data.
  - Protections: rate limits per IP and per member, a lock after 5 failed
    attempts that lasts 15 minutes and grows on repeat lockouts, and the
    same error message whether the name or the PIN was wrong.
  - Members without a PIN cannot use this route, only the personal link.
- [ ] Neither route reveals which other names exist (there is no
      autocomplete on public pages).

## Phase 5: UI and flow overhaul

- [ ] Add Tailwind (standalone CLI, no Node build in production) and htmx.
- [ ] Build a component library of Jinja macros: buttons, cards, tables,
      forms, flash messages, empty states and modals.
- [ ] Rebuild `base.html` with a responsive sidebar navigation that changes
      by permission, and show the group's branding.
- [ ] Use a separate, lighter public layout for the `/g/<slug>/` pages,
      designed for phones first.
- [ ] Replace the 23 per-page CSS/JS pairs with shared components.
- [ ] Flows to redesign:
  - **Onboarding:** the superadmin creates the group and its first officer.
    The officer then goes through setup: branding → contribution terms →
    data source and mapping → first sync and member matching → rules →
    public page options → add officers.
  - **Monthly cycle:** pick a month → sync the sheet or upload a file →
    resolve unmatched names → preview → confirm → reports and public page
    update → share.
  - **Officer management:** create an officer, assign a role, and edit roles
    and permissions.
- [ ] One permission-aware dashboard replaces the admin, clerk and viewer
      dashboards. It shows: the latest period summary, sync status, unmatched
      names, recent reports and quick actions.

## Phase 6: Hardening and release

- [ ] Use a Postgres-ready config. Check the migrations on SQLite and Postgres.
- [ ] Add audit log entries for settings, mapping, rules, role and member
      changes, PIN resets and link regeneration.
- [ ] Rate limiting on all login and public lookup endpoints.
- [ ] Make the scheduler safe with multiple workers (a lock, or move it to a CLI cron job).
- [ ] Docker setup (an old `dockerize` branch exists and is worth reviewing).
- [ ] Write the migration runbook for the live Mzugoss deployment.
- [ ] Bump the major version to 3.0.0.

---

## Working conventions

- Each phase is developed on a short-lived branch off
  `feature/multi-group-overhaul` and merged back into it after review.
  The overhaul branch goes into `develop` only when a phase leaves the app
  working end-to-end.
- Mzugoss must keep working after every phase. This is the regression baseline.
- Every schema change ships as an Alembic migration.

## Resolved questions

- **Sharing PINs and links:** officers share them by copying only, with a
  copy button on the Members screen. There is no bulk export or printable list.
- **Group access code:** it is **on by default** for new groups. A code is
  generated when the group is created, and officers can change it or turn it off.
- **Contribution history retention:** kept **forever**. Retention cleanup
  applies only to generated report files and uploads, and never to `Member`,
  `Contribution` or `PeriodSummary` rows.
