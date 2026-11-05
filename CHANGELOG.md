# Changelog

What changed in each version, newest first. Versions follow
[semantic versioning](https://semver.org): `3.0.1` fixes bugs, `3.1.0` adds
or changes how something works, `4.0.0` needs officers or the server to do
something different. How to release: [docs/CI_CD.md](docs/CI_CD.md#releasing).

## Unreleased

### Added
- CI on every push and pull request (tests on Python 3.12 and 3.13, on
  Postgres, migrations, Docker build), and deploys to the Oracle server from
  `v*` tags.
- `deploy/nginx-mzugoss-8008.conf`: the site on the bare IP until it has a
  domain.

### Changed
- `deploy/update.sh` relabels the venv's programs for SELinux after
  installing, and accepts only a version name.

## 3.0.0 — 2026-11-05

Many groups on one site, each with its own officers, members, workbook,
reports, rules and branding.

### Added
- Groups, a platform account that manages them, and per-group officers
  (Chairperson, Treasurer) with editable roles.
- Contributions and payouts stored per member and month, synced from the
  standard workbook or a mapped layout, with per-group payout purposes.
- Conversion of the old Mzugoss workbook (`convert-legacy-workbook`).
- Member management: rename, merge, history, PINs.
- Public pages for members, with access codes and PIN lockout.
- Welfare rules, branding and a logo per group, a setup checklist for new
  groups.
- Reports show the opening balance, money paid in and dispensed in the year
  so far, and the book balance.
- Officers' passwords can be set by the Chairperson or the platform, or with
  `flask reset-password`.
- Audit log, support sessions, rate limits on every secret check.
- Docker setup, and a no-Docker setup for small servers
  ([DEPLOY_VPS.md](docs/DEPLOY_VPS.md)).

### Fixed
- Excess counts in the book balance from January, not only December.
- "Find your group" opens the finder instead of the remembered group.
