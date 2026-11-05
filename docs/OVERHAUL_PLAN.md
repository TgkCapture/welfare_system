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
and permissions (done), **1c** tenant scoping (done), **1d** management screens
(done), **1e** per-group files and settings (done).

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

Step 1c delivered:
- `TenantScoped` mixin (`app/models/tenancy.py`) on users, roles, reports and
  access logs: `Model.for_group()` and `Model.get_for_group_or_404()`. Other
  groups' rows are always 404, never 403, so their existence isn't revealed.
- `current_group_id()` is the single place the current group is resolved
  (instead of `g.group`); the 1d superadmin "act as group" switch hooks in there.
- Every controller and service query on group-owned tables uses the helpers.
  Raw queries must carry a `# platform-wide` or `# own account` marker; a
  test fails on any unmarked one.
- Leaks fixed: the officer dashboard's recent reports and paid-members count
  covered every group; the freshly generated report kept in the session
  survived logout and could be opened by the next officer on the same
  browser. It is now tagged with its owner and cleared on login and logout.
- Tests: a cross-tenant crawl tries every id route with another group's ids;
  a mutation check confirmed the isolation tests fail if scoping is removed.
- Known limitation, fixed by Phase 2: the session report (member names and
  amounts) lives in Flask's signed, unencrypted cookie, which is near the
  ~4 KB cookie limit for a 50+ member group. Phase 2's stored sync results
  replace it.

Step 1d delivered:
- Platform screens (`/platform/groups/...`): a superadmin creates a group
  together with its first Chairperson, renames it (the slug is fixed, since
  sign-in links and storage folders use it), suspends or reactivates it, and
  adds officers with any of its roles. Adding an officer is also how a group
  that has locked itself out (no active manager) is rescued. Superadmins
  still don't see a group's reports or data. The CLI commands remain.
- Role editor (`/admin/roles`, needs `manage_users`): create, rename, edit
  and delete the group's roles. An officer can only hand out permissions they
  hold, and can only edit or delete roles within their own permissions.
  Removing `manage_users` from the role of the group's last active managers
  is blocked. A role still held by an officer can't be deleted.
- Fixed: 12 POST forms (officer toggle and delete, report archive, restore,
  delete, regenerate and cleanup, file cleanup) had no CSRF token, so they
  failed with 400 in production. Tests run with CSRF off, so a new test
  fails on any POST form without a token.
- Deferred to Phase 6: the superadmin "act as group" support mode. The
  rescue path above covers lock-outs. Viewing a group's data as a superadmin
  needs an audit trail.

Step 1e delivered:
- Files per group: reports are saved in `reports/<slug>/` and uploads in
  `uploads/<slug>/` (`app/services/group_storage.py`). Uploads get a unique
  name, so two groups uploading `contributions.xlsx` at once can't collide.
  They are deleted as soon as the report is generated, since they hold member
  data and nothing reads them again.
- Settings per group: the Google Sheet URL and the report retention period
  are read from and written to `GroupSettings`. The global `Setting` rows for
  them are no longer used (`Setting` still holds officers' profile preferences).
- Cleanup per group: `cleanup_group()` deletes expired files and archives
  (never deletes) the matching reports, using the group's own retention.
  Officers with `manage_reports` get the storage page (`/admin/cleanup`) and
  the "Cleanup Old Reports" button again, for their own group only. Uploading
  only cleans the uploader's group. The nightly job and `flask cleanup-files`
  clean every group, plus logs and loose files. `--group <slug>` limits it to
  one group, and `--days` is gone because retention is a group setting.
- Superadmins have `/platform/storage`: usage per group, with preview and
  cleanup for all groups.
- `flask move-files-to-groups [--dry-run]` moves existing report files into
  their group's folder. It can safely be re-run.
- Removed dead code: `app/utils/helpers.py` (a second copy of the upload code
  that wrote the global sheet URL), the unused storage-status template and the
  old cleanup page's JS and CSS, which called endpoints that don't exist.

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
- [x] Tenant scoping:
  - Resolve the current group from `current_user.group_id` (`current_group_id()`).
  - Add a query helper (`Model.for_group()`) and use it in every controller.
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

Delivered in steps: **2a** stored data and sync (done), **2b** standard
workbook template, parser and sync checks (done), **2c** MGSS.xlsx conversion for
review (done; awaiting the user's review), **2d** Members screen (merge, links, PINs) (done), **2e** (done) column mapping for
older layouts, with reports built from stored data.

Step 2a delivered:
- New tables (migration `80408a6fc2fd`): `members` (with `history_token` and
  PIN fields ready for Phase 4), `member_aliases`, `contributions` (one row per
  member and month, with `paid` / `partial` / `unpaid` status) and
  `period_summaries`. All are tenant-scoped and covered by the static guard.
  A test fails if a tenant model is added without the guard.
- `PeriodStore.sync()` (`app/services/period_store.py`) stores a parsed month.
  It replaces that month's contributions and summary, matches names by
  normalised form (case, spacing and dots ignored) and then by alias, and
  creates members for names that match nobody. The upload reports new names
  and names listed twice in the same month (their amounts are added together).
- Uploads now go parse → sync → PDF built from the stored month. The report
  record's totals come from the stored summary.
- The session-cookie report is gone. The session keeps only the id of the
  officer's latest report. Preview, download and the paid-members list and
  PNG read the stored month, so the paid-members detail now also works for
  older reports, as long as their month has been synced since 2a.
- Without a known rate, any amount above zero counts as paid, as before.
  Partial payments need the Rates sheet (2b).
- Tried on the real MGSS.xlsx (in memory): all 48 months sync, giving 66
  members, no name listed twice in a month, and one likely respelling pair
  for the merge screen.

Step 2b delivered:
- New tables (migration `80433ad3f5cf`): `payout_purposes` (per group; every
  group starts with Funeral condolence, Wedding gift and Sick patient grant),
  `payouts`, `rates`, `year_summaries` (calculated balances beside the sheet's
  own figures) and `sync_runs` (each sync, its warnings and what it stored).
  Members gain a workbook Member ID, phone, and joined/left months.
- Template (`app/services/workbook_template.py`, Workbook page → Download):
  it has Read me, Members, Contributions YYYY, Payouts, Rates, Summary and a
  hidden Lists sheet.
  - It comes pre-filled with the group's members (any member without one is
    given the next free ID, M001 and so on), rates, purposes, and the previous
    year's calculated closing balance as the opening balance.
  - Dropdowns limit Member IDs and purposes to known values.
  - Name lookups and the Summary use `VLOOKUP` and `SUMIFS`, not array
    formulas, so they work in any Excel and in Google Sheets.
  - Not yet checked in a spreadsheet app: the tests confirm the formulas are
    written, not that they calculate.
- Reader (`standard_workbook.py`): columns are found by header, in any order.
  A missing sheet or header is an error. Anything else unusable becomes a
  warning naming the sheet, row and column.
- Sync (`standard_sync.py`):
  - One upload stores every year. Months nobody has paid yet are skipped, so
    blank future months don't create defaulters.
  - Status uses the rate in force that month (paid / partial / unpaid).
  - Months before Joined or after Left aren't counted against a member.
  - Carry-overs are calculated from the first year's opening balance. Monthly
    money dispensed and book balance come from dated payouts.
  - Members match by Member ID, then by name or alias. A renamed member keeps
    the old spelling as an alias.
- Checks (warnings, the sync still stores what it can):
  - Summary figures against the calculation, including each opening balance
    against the previous closing
  - payouts with an unknown purpose or member, a future or missing date, or a
    repeat (same member, amount and date)
  - payments outside Joined / Left
  - unknown or duplicate Member IDs
  - members with no row in a year's sheet, who are counted as unpaid
- Upload detects the layout. The older layout still reads only the chosen
  month, and is recorded as a sync too. The Workbook page shows the template
  download, yearly balances and recent syncs, and each sync has a page
  listing its warnings. Payout purposes are managed under Settings.
- Google Sheets syncs now export the whole spreadsheet (every tab), falling
  back to the single year sheet if the export fails.

Step 2c delivered:
- `flask convert-legacy-workbook SOURCE [--merges CSV] [--drop-repeated-payouts]`
  (`app/services/legacy_conversion.py`). It writes three files to
  `conversion/`, which is git-ignored because they contain real member data:
  - the standard workbook
  - a review report (`*_review.md`)
  - name-merge suggestions (`*_name_suggestions.csv`). Put "yes" in the
    confirm column and re-run with `--merges` to apply them.
- It reads the visible `YYYY` sheets. The `Old` sheet turned out to be an
  exact copy of 2023's August–December, and the hidden month sheets are
  leftovers, so both are ignored.
- The confirmed mistakes are corrected by construction:
  - Only the first year's carry-over is used. Later openings are calculated,
    so the +2,000 into 2024 and the −16,000 into 2026 disappear, and the
    mislabelled 2023 carry-over row no longer matters (it was empty, giving
    an opening of 0).
  - Payouts are read cell by cell, so the 2025 formula that missed rows
    50–59 doesn't matter.
  - `--drop-repeated-payouts` drops the three 2025 payouts (36,760) repeated
    in 2026.
- Decisions listed for review: Joined/Left months guessed from which sheets a
  member is on and their first payment; rates taken as each year's most
  common payment (500 from 2023, 1,000 from January 2025); payouts dated
  31 December (today for the current year) with the purpose "Unspecified";
  and a note found in an unused column.
- Self-check: the converted workbook is synced into a throwaway database.
  Every one of the 48 months' totals matches the old sheet, and the 18
  warnings the treasurer will see are listed in the review.
- Sync rule changed along the way: a member with no row on a year's sheet is
  not counted that year (a warning is still raised). This matches the old
  sheets, where unlisted members never counted as owing.
- Before Mzugoss switches: the user reviews the workbook and report, confirms
  name merges, and then the treasurer fills in real payout dates and purposes.

Step 2c, after the user's review:
- Confirmed merges (`conversion/MGSS_merges.csv`): Steven / Steve Ngoma,
  Agness / Agnes Nomsa, wapozga / wapozga Munyenyembe. A merged member is
  shown under the kept name. MGSS now converts to 63 members.
- **Credit for overpayments.** A note like "1500N" means a member paid that
  much beyond the year's months, to be carried into the next year. The old
  sheet left it out of the book balance.
  - The standard workbook has an **Excess** column after December (migration
    `c4349d6178c3`). Money in the Excess column counts in the year it was
    paid, and becomes credit that covers the member's first months of the next
    year, which show as paid without being typed.
  - With a known rate, paying more than the rate in a month also covers the
    following month(s).
  - Contributions record `credit_used`, and `member_years` keeps each member's
    credit brought in, excess paid and carried out. Reports count
    credit-covered months as paid, while money totals count only money
    received.
  - The converter turns "1500N" notes into the Excess column, which raises
    2026's paid-in by 1,500.
- Rates: the first rate starts in the first month anyone paid (500 from
  August 2023). Rates change whenever the group decides, by adding a row to
  the Rates sheet.
- Payouts must show what they were for and when: the treasurer fills these in
  on the Payouts sheet. Until then each sync lists them as warnings.

Corrections from the user, made at the start of 2d:
- **Payout purposes are each group's own.** New groups start with none; there
  is no built-in list. The converter takes them from `--group <slug>` and/or
  `--purpose` (plus "Unspecified" for old payouts). Existing groups keep the
  three purposes the 2b migration gave them, which can be renamed or retired.
- **A member missing from a year's sheet paid nothing that year.** They are
  still a member: the converter gives them an empty row for any year between
  two sheets they're on, and a sync counts a member with no row as unpaid,
  with a warning (this reverses the 2c rule). MGSS: 11 sync warnings remain,
  all about payouts.

Step 2d delivered (Members screen, `manage_members`):
- List with search by name, alias or Member ID. `?run=<id>` lists a sync's
  new names, linked from the sync page ("Review new members").
- Member page:
  - The contribution history by year, marking unpaid months, months covered
    by credit, excess and credit carried forward.
  - Rename: the old spelling is kept as an alias for matching.
  - Merge into another member, with likely matches suggested by the shared
    name-matching rules (`app/services/name_matching.py`). Contributions,
    credit, payouts and names move across, a month both records have is added
    together, and the month's paid and unpaid counts are recounted. If both
    records have Member IDs, the officer is told to remove the merged one from
    the workbook.
  - Remove an alias, retire or restore the member.
  - Personal link: copy it or make a new one, which cancels the old.
  - PIN: random 6 digits, shown once and not kept anywhere (no-store page),
    stored only as a hash. A new PIN also unlocks a locked member.
- Members with a Member ID are renamed or retired in the workbook too; the
  screen reminds the officer, since a sync follows the workbook.
- Public personal history at `/g/<slug>/m/<token>`, pulled forward from
  Phase 4 so that copied links work. It shows only that member's months and
  credit, sends noindex, no-store and no-referrer headers, and returns 404 for
  a wrong token, another group, a retired member or a suspended group. The
  name + PIN lookup page stays in Phase 4.

Step 2e delivered (other layouts, reports from stored data):
- `SheetMapping` (`app/services/sheet_mapping.py`), stored per group in
  `GroupSettings.sheet_mapping` (migration `6d6c9c1b2177`). Its settings:
  - Sheet: one per year (any name containing the year, or a pattern such as
    "Contrib {year}"), always the first sheet, or a fixed name.
  - Header row number, name column letter, and a January column letter for
    sheets whose month columns aren't titled.
  - Money dispensed and book balance: found by label, read from given cells,
    or absent.

  Every setting left blank is worked out exactly as before, so the Mzugoss
  layout needs none. The parser's output is identical, before and after,
  for all 84 months checked (MGSS.xlsx and the test workbook).
- The parser now also accepts short month headings ("Mar"). Its errors name
  the sheet, row or column. A text amount ("owing", "pending") is still
  counted as unpaid, but becomes a warning naming the cell, recorded on the
  sync.
- Settings → Workbook layout (`edit_settings`): fill in only what differs and
  test it on a sample file. The test shows the sheet and columns read, the
  first rows, the totals and any warnings. The file is deleted and nothing is
  saved until Save. Standard-layout files are recognised and left alone.
  Reset returns to automatic.
- Google Sheets: credentials stay platform-wide, and Settings shows the
  service account's email to share the sheet with (with a copy button). The
  single-sheet cache is keyed per group.
- Reports from stored data: since 2a, uploads build the PDF and PNG from the
  stored month. "Regenerate" now rebuilds the PDF from the latest sync, and
  only copies the file for months synced before contributions were stored.
- Fixed: two reports made in the same second shared one PDF file, so deleting
  either removed the other's file. Report filenames now include a random part.
- Not done (no data source yet): partial-payment status for older-layout
  workbooks, which have no Rates sheet. Any amount above zero still counts as
  paid there. Groups that want partial payments should move to the standard
  template.

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

Delivered:
- **Welfare rules per group.** `rule_sections` (migration `3e07a023d4e8`) hold
  ordered sections, each with a title, an optional subtitle and a body in a
  small formatting syntax (`app/services/rules_markup.py`): lists, numbered
  lists, notes, **bold** and *italic*. Everything is HTML-escaped first, so
  officers can't put HTML on a public page.
  - The rules page, the public page and the PDF are all drawn from this one
    source. The two hard-coded copies (page and PDF) and the unused
    `welfare_rules_pdf.html`, `welfare_rules.js` and `paid_members.js` are gone.
  - Mzugoss is seeded with its old rules, the page and PDF wording merged
    (9 sections).
- Rules pages:
  - Members: `/g/<slug>/rules` and `/rules.pdf` (noindex).
  - Officers: `/welfare-rules`, with a copyable public link.
  - Old shared `/welfare-rules` links go to the visitor's last group, or the
    only group, or else the group finder.
- Rules editor (`edit_rules`, e.g. Secretary): add, edit (with a formatting
  guide and a preview), reorder and delete sections.
- **Branding** (`app/services/branding.py`): templates get `brand`, which is
  the officer's group, the group whose public page is shown, or the platform
  name. It is used in:
  - page titles, the header logo and the footer
  - the brand colour (as `--clr-primary`)
  - currency on every page, PDF and PNG
  - the contribution report's title, the PNG title and download filenames
    (`<slug>_welfare_rules.pdf`)
  - the group login page and the personal history page

  Officers edit it under Settings → Branding: name, short name, report
  title, currency and colour.
- A test parses the templates, scripts and Python string literals and fails
  if a group name is hard-coded again.
- Not done: the logo (`logo_path`) needs file uploads and serving; it moves to
  Phase 5 with the UI work.

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

Delivered (migration `0a94e0dbf35b`):
- Shared public layout (`templates/public/_layout.html`), phone-first, with
  the group's name, colour and links. Every public page sends noindex,
  no-store and no-referrer.
- Home `/g/<slug>/`: links to the rules, who has paid, and my contributions,
  plus when contributions were last updated.
- Who has paid `/g/<slug>/paid`:
  - It lists only members whose month is fully paid, by money or credit.
    Part-paid and unpaid members never appear on any public page.
  - Amounts and totals are off by default, and only months within
    `public_months_back` of the latest synced month can be browsed
    (`?period=YYYY-M`).
- Group access code: on for every group, including existing ones (the
  migration generates a code). It uses 6 characters with no 0/O/1/I/L, is
  checked in constant time, ignores case and spaces, is remembered per group
  in the session, and one group's code never opens another's list.
- Name + PIN lookup `/g/<slug>/check` (`app/services/public_access.py`):
  - It matches the name and aliases of active members, and shows the same
    history page as the personal link.
  - Every failure (unknown name, no PIN, wrong PIN, locked, retired) gives an
    identical page and does the same hashing work.
  - Five wrong PINs lock the name for 15 minutes, then 30, 60 and so on, up
    to 24 hours. A correct PIN or a new PIN from an officer resets it.
- Access code and PIN attempts share one rate limit per IP
  (`PUBLIC_LOOKUP_RATE_LIMIT`, default 10/min and 30/hour). Viewing the pages
  isn't limited.
- Public forms turn off autocomplete, and nothing on a public page suggests
  names.
- Officers (Settings → Public pages, `edit_settings`) can:
  - copy the group page link
  - see, copy, regenerate, set or turn off the code
  - choose whether the paid page exists, whether it shows amounts and
    totals, and how many months can be browsed

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

Delivered in steps: **5a** foundation (done), **5b** one dashboard, **5c**
monthly cycle flow, **5d** setup checklist for new groups, **5e** logo upload
and moving the remaining pages onto the components.

Step 5a delivered:
- Tailwind 3.4.17. The standalone CLI download (about 100 MB) was too slow
  here, and Node is installed, so it is a dev dependency (`package.json`,
  `npm run build:css`). The built `app/static/css/app.css` (about 38 KB) is
  committed, so production never needs Node. `node_modules/` is git-ignored.
- htmx 2.0.4 vendored in `static/vendor`.
- `app/static/src/app.css`: tokens, plus the shared component classes
  (`btn`, `card`, `page-header`, `stat-card`, `data-table`, form controls,
  badges, flashes, modals, empty and error states) rebuilt on Tailwind, so
  every existing page took on the new look without rewriting. The old
  `--clr-*` variables are kept for inline styles.
- `brand` follows each group's colour through `--brand-rgb`, which the
  layouts set per request, so `bg-brand`, `text-brand` and the rest are on
  brand.
- Component macros (`templates/components/ui.html`): page_header, card,
  stat, button, badge, status, empty_state, field (WTForms), copy_field,
  flashes.
- New `base.html`:
  - A sidebar grouped by task (Contributions, Group, Platform), showing only
    what the officer's permissions allow, with the active page highlighted
    and the officer's name, role and log-out at the bottom.
  - On small screens, a top bar opens it as a drawer.
  - Visitors who aren't signed in get a slim header.
- The public layout uses the same stylesheet.
- Removed dead code: 16 per-page CSS files and 14 per-page JS files that no
  template loaded, `base.css`, and the unused `main/dashboard.html`
  (about 14,000 lines in all).
- A test checks that every `static` file a template references exists.
- Checked by rendering the main pages with sample data and screenshotting
  them with headless Chrome.

Step 5b delivered:
- One dashboard at `/` replaces the admin, clerk and viewer dashboards.
  `/admin`, `/clerk-dashboard` and `/viewer-dashboard` redirect to it for old
  bookmarks. Its figures come from `app/services/dashboard.py`, and each part
  is only worked out and shown if the officer's permissions allow it.
  - The latest synced month: who paid out of how many, who didn't (linked to
    Members), money received and paid out, and the year's calculated closing
    balance (or the sheet's book balance for older layouts).
  - The last six months as bars of the share who paid, with money received.
  - Needs attention:
    - sync warnings
    - new names from the last sync to check for respellings
    - members without a PIN
    - no payout purposes yet
    - the group code switched off
  - The last sync (when, which layout, warnings) and recent reports.
  - The members' page link to copy, and shortcuts filtered by permission.
- Without any synced data, it says so and points to the workbook template
  and the upload page.
- Removed the three old dashboard templates and their controller helpers.
- Fixed a 5a build gap: Tailwind dropped component variants whose names are
  built in templates (`flash--{{ category }}`, `stat-card__icon--{{ tone }}`,
  and so on), so flash messages had lost their colours. Those class patterns
  are now safelisted in `tailwind.config.js`.

Step 5c delivered (the monthly cycle: upload or sync, check, share):
- Upload page:
  - It suggests the month after the last one synced, but never a month
    still to come, and says which month was last synced.
  - The Google Sheet and file upload choices are tabs, with drag and drop for
    files and a "Reading the workbook…" state while it works.
  - For standard workbooks it explains that the whole workbook is stored and
    the month only chooses the report.
- After an upload, the report page (`/reports/preview`) becomes Check and
  Share:
  - Check lists the sync's new names, each with likely matches from the
    name-matching rules. Merging happens in place with htmx (the merge
    endpoint returns a small fragment for htmx requests). It also lists the
    first warnings, with a link to all of them. This part needs
    `manage_members`.
  - Share has a ready-to-paste group chat message: the paid page for that
    month, the group code if on, and the "check your own" link. It has copy
    and WhatsApp buttons, plus the PNG and PDF. It notes that the PDF lists
    who hasn't paid, so it stays among officers.
- The session remembers the sync behind the report (`last_run_id`, cleared
  on login and logout with the report). The upload's flash messages are gone,
  since the Check step shows the same things.

Step 5d delivered (setup checklist, migration `191c98a5790f`):
- `/setup` (`app/services/setup.py`) walks a new group through seven steps:
  branding, payout purposes, workbook and data source, first sync, welfare
  rules, the members' page, and other officers.
- Most steps tick themselves from the group's data:
  - a purpose exists
  - a sheet link, a sync or a synced month exists
  - a month is synced
  - a rule section exists
  - there are two or more active officers

  The two that can't be inferred are recorded in `setup_marks`: branding
  ticks when the branding form is saved, and the members' page when an
  officer opens its settings.
- Each step links to where it's done, names the permission it needs, and
  tells officers without it to ask someone whose role allows it. The next
  step is highlighted, with a progress bar.
- The dashboard shows a progress card ("Set up your group: 2 of 7 done", next
  step, Continue) until setup is complete or an officer who manages officers
  or settings hides it. It can be shown again from `/setup`, which is linked
  from Settings.
- New groups (including those created on the platform) start with the
  checklist showing. Existing groups like Mzugoss are already running, so the
  migration hides theirs.

Step 5e delivered (logo and the remaining pages):
- Group logo (`app/services/logo.py`), uploaded under Settings → Branding:
  - Pillow opens it and checks it: PNG, JPEG, WebP or GIF, under 2 MB, up
    to 25 megapixels. SVG is refused, because it can carry scripts.
  - It is turned upright, shrunk to 256 px and saved again as PNG, so only
    the pixels are kept.
  - It is stored in `BRANDING_FOLDER/<slug>/` (`instance/branding`,
    git-ignored), apart from uploads and reports, which expire. It gets a new
    file name each time and the old file is removed.
  - It is served at `/g/<slug>/logo.png` with a week's caching (the URL
    carries the file name), and shown in the sidebar, the public header, the
    group login page and at the top of both PDFs. It can be removed. Logos are
    per group.
- No per-page CSS is left:
  - The seven remaining `<style>` blocks (settings, profile, activity log,
    reports list, report page, paid members, sign-in pages) moved into
    `app.css`, and `auth/_auth_styles.html` was deleted.
  - The rules section styles and the public layout's header styles moved too.
  - Every fixed inline `style=""` in the templates became Tailwind classes
    (193 of them). Only computed widths (progress bars)
    stay inline.
- A test fails if a template gains a `<style>` block (other than the
  per-request brand colour) or a fixed inline style.

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

Steps: **6a** Postgres readiness, the audit log and platform support
sessions; **6b** rate limits and a scheduler safe with several workers;
**6c** Docker, the Mzugoss runbook and 3.0.0.

Step 6a delivered (Postgres, audit log, support sessions):
- Postgres:
  - `psycopg[binary]` 3 is the driver. `DATABASE_URL` values starting
    `postgres://` or `postgresql://` are pointed at it (`database_url()` in
    `app/config.py`), and connections are checked before use (`pool_pre_ping`).
  - Every migration now runs on Postgres 18, up from empty, down to base and
    up again, with no difference between the migrated schema and the models.
    One fix was needed: `users.is_superadmin` had an integer default, which
    Postgres refuses for a boolean. A test now checks every boolean default.
  - `TEST_DATABASE_URL` runs the whole suite on another database; it passes
    on Postgres as well as SQLite.
  - Deleting an officer who had made reports or synced data failed on
    Postgres. Reports, report access records, syncs and period summaries now
    keep the record and clear the link (`ON DELETE SET NULL`, migration
    `5b7e2d9c4a10`).
  - SQLite now enforces foreign keys, as Postgres does, so development
    catches the same broken links. Migrations turn enforcement off while
    they rebuild SQLite tables (`migrations/env.py`); a test checks that
    every migration is committed with no temporary tables left behind.
- Audit log (`AuditEvent`, `app/services/audit.py`, migration `1c2392acf221`):
  - Recorded with who, when, the IP address and a plain summary: sign-ins
    (and failed ones), password and email changes, settings (data source,
    branding and logo, public pages, access code), workbook layout and
    template downloads, payout purposes, syncs, rules (the previous wording
    is kept so an edit can be undone), members (rename, retire, merge,
    spellings, links and PINs), officers, roles, reports and storage cleanup,
    and platform actions on a group.
  - Secrets are never written: not the access code, a PIN or a password.
  - The officer's email is copied onto each entry, so entries still read
    correctly after the account is deleted. Entries are never edited.
  - Officers with `manage_users` read their group's log at `/audit`, filtered
    by area. Each officer's **Your activity** page (from their profile) now
    shows their own entries; it used to be built from two timestamps.
    Superadmins read every group's log at `/platform/audit`.
- Platform support sessions (`app/services/support.py`), deferred from
  Phase 1:
  - Started from the group's platform page, with a reason the group will see.
  - The superadmin sees the group's screens as an officer with every
    permission would, under a banner, for `SUPPORT_SESSION_MINUTES` (60).
  - **Read-only**: every form post is refused, and looking doesn't tick
    setup checklist steps.
  - The start (with the reason), every page opened and the end (ended,
    logged out or ran out) go in the group's audit log, marked
    *Platform support*.
  - Reports and the reports API now check the current group rather than the
    officer's own, so they work in a support session.

Step 6b delivered (rate limits, multi-worker scheduler):
- Rate limits (`app/services/limits.py`), per client IP, counting **failed
  attempts only**, so members sharing a mobile network address don't use up
  each other's budget. Once spent, every attempt from that address gets 429
  until it recovers.
  - `login` budget: group and platform sign-ins, wrong current passwords on
    the password change form (new), and unknown codes in the group finder (new).
  - `public-lookup` budget: the access code, member PINs and wrong personal
    history links (new).
- `TRUSTED_PROXIES` (default 0) wraps the app in Werkzeug's `ProxyFix`, so
  behind nginx or a load balancer the limits and the audit log see the
  visitor's address, not the proxy's. Forwarded headers are ignored otherwise.
- A Postgres URL from any config source, including `instance/config.py`,
  now uses psycopg 3 (it had to come from `DATABASE_URL` before).
- Daily jobs (`JobRun`, `app/services/jobs.py`, migration `2dce51ee491c`):
  the runner claims `(job, day)` with a unique key before working, so only
  one worker or cron entry does the day's cleanup; the row records the
  outcome. Checked on Postgres with four processes started together.
  - The scheduler now runs once the time has passed (it used to need a
    worker awake within two minutes of it), so a restart doesn't skip a day.
  - `flask daily-cleanup` is the cron alternative (`ENABLE_AUTO_CLEANUP=false`).

Step 6c delivered (Docker, runbook, 3.0.0):
- Upgrading a live 2.0.x database was broken. Those installs made their
  tables with `db.create_all()`: 2.0.0 has no index on `users.email` and
  no named constraints, so the first multi-group migration failed. It was
  found by rehearsing on databases created by the real `origin/main` (2.0.0)
  and `origin/develop` (2.0.2) code.
  - New migration `4f1e9a7c2b6d`, right after the baseline, rebuilds the
    four original tables as the baseline makes them. It copies every row,
    fills values that 2.0.0 left empty, and drops access records pointing at
    deleted users.
  - New installs and databases already past it never run it.
  - Tests build both old schemas, upgrade them and check the officers,
    reports and links.
  - Both rehearsals end at head with no drift, and officers sign in with
    their old passwords.
- Docker (`Dockerfile`, `docker/entrypoint.sh`, `docker-compose.yml`,
  `.env.example`), written fresh. The `dockerize` branch ran the Flask
  development server on SQLite with no migrations. Now:
  - Python 3.13 and gunicorn, running as a non-root user.
  - Migrations run on start.
  - Postgres 17 and Redis 7, which shares rate-limit counts between workers.
  - Volumes for uploads, reports, logs and logos.
  - The app is published on 127.0.0.1 only, for a proxy.
  - Member workbooks, keys and `instance/` are kept out of the image.
- Built and run locally:
  - migrations ran on Postgres and the container became healthy
  - the 4th failed sign-in from one forwarded address got 429 across both
    workers, while another address could still try
  - the audit log recorded each visitor's own address
  - the scheduler ran the day's cleanup once
- `/api/health` now checks the database and returns 503 when it can't
  reach it.
- `requirements.txt`:
  - gunicorn and redis added
  - numpy and zopfli updated to the versions the tests already ran on;
    the old pins have no Python 3.13 wheels
- `docs/MZUGOSS_RUNBOOK.md`: the cutover from 2.0.x. It covers:
  - what to finish in the converted workbook first
  - Docker with Postgres (recommended) or in place on SQLite
  - backups and setting up the group
  - PINs and links
  - checks, including removing the `admin@welfare.org` account that 2.0.x
    created on its own, and how to undo the move
- Version 3.0.0.

- [x] Use a Postgres-ready config. Check the migrations on SQLite and Postgres.
- [x] Add audit log entries for settings, mapping, rules, role and member
      changes, PIN resets and link regeneration.
- [x] Superadmin support mode ("act as group"), with an audit trail.
- [x] Rate limiting on all login and public lookup endpoints.
- [x] Make the scheduler safe with multiple workers (a lock, or move it to a CLI cron job).
- [x] Docker setup (an old `dockerize` branch exists and is worth reviewing).
- [x] Write the migration runbook for the live Mzugoss deployment.
- [x] Bump the major version to 3.0.0.

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
