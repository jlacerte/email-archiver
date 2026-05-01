# Unified Email Classifier — Design Spec

Date: 2026-04-30

## Problem

email-archiver has three independent classification systems that overlap and conflict:

1. **classifier.py** (`should_archive()`) — ~95 regex patterns, returns bool, moves matches to a generic archive folder (`[Gmail]/All Mail`).
2. **organizer.py** (`categorize()`) — ~100 substring patterns, returns folder name, moves matches to specific IMAP folders.
3. **invoice_scanner.py** (`is_invoice()`) — 12 from-patterns + 10 subject-patterns, read-only detection for invoices.

Problems identified:
- `archive` and `organize` are competing CLI commands. Running `archive` first destroys emails that `organize` would have sorted into useful folders.
- ~15 senders exist in both classifier and organizer with contradictory destinations (e.g., `@bnc.ca` → generic archive vs. `Financier/BNC`).
- No defined workflow order. Nothing prevents destructive execution sequences.
- invoice_scanner duplicates detection patterns that already exist in the other two systems.
- ~110 emails remain in Gmail INBOX after organize, suggesting coverage gaps.

## Decision Record

| Question | Decision |
|----------|----------|
| Single system or layered? | **Single unified classifier** — one function, one file, one set of patterns |
| Unmatched emails? | **Stay in INBOX** — safe default, natural discovery queue for new patterns |
| Noise handling? | **Two-level output** — folder name for important emails, `_archive` for noise |
| Invoice scanner? | **Folder-based only** — scans `Factures/*` and `Financier/*`, no own patterns |
| CLI commands? | **`organize` does everything** — `archive` command removed |

## Architecture

### Unified classifier — `classifier.py`

Single entry point:

```python
def classify(from_addr: str, subject: str) -> str:
    """Classify an email into a destination.

    Returns:
      - Folder name (e.g., "Travail/Deslauriers", "Factures/Anthropic") — move to folder
      - "_archive" — move to provider's archive folder
      - "" — leave in INBOX (no match)
    """
```

Evaluation order (first match wins):

1. Self-sent → `Notes-personnelles`
2. Travail → `Travail/X`
3. Gouvernement → `Gouvernement/X`
4. Agriculture → `Agriculture/X`
5. Financier → `Financier/X`
6. Assurance → `Assurance/X`
7. Comptabilité → `Comptabilite`
8. Éducation → `Education`
9. Personnel → `Personnel/X`
10. Factures/Services → `Factures/X`
11. Dev-Tech → `Dev-Tech/X`
12. Formations → `Formations`
13. Social → `Social`
14. Crypto → `Crypto`
15. Newsletters → `Newsletters`
16. Notifications → `Notifications/X`
17. Spam (iCloud relay) → `Spam`
18. Generic noise (noreply@, newsletter@, promo subjects, etc.) → `_archive`
19. Default → `""` (stay in INBOX)

Key principle: specific sender patterns (steps 1–17) have priority over generic noise patterns (step 18). An email from `noreply@bnc.ca` matches `bnc.ca` at step 5 → `Financier/BNC`, not `noreply@` at step 18 → `_archive`.

Matching mechanism:
- **From-address patterns** (steps 1–17): substring matching (`pattern in from_addr`), same as current organizer.py. Fast, readable, sufficient for domain/sender matching.
- **Generic noise from-address patterns** (step 18a): substring matching (`pattern in from_addr`) for patterns like `noreply@`, `@e.`, etc.
- **Subject patterns** (step 18b): compiled regex (`pattern.search(subject)`) for patterns requiring `\d+`, `.` wildcard, etc. Subject patterns only fire for emails NOT already matched by from-address patterns at steps 1–17.
- Step 18 has two sub-steps: (a) generic from-address noise, then (b) subject-based noise. Both return `_archive`.

Legacy wrappers (for backward compatibility during transition):

```python
def should_archive(from_addr: str, subject: str) -> bool:
    """Returns True if classify() would archive."""
    return classify(from_addr, subject) == "_archive"

def categorize(from_addr: str, subject: str) -> str:
    """Returns folder name or '' (excludes _archive)."""
    result = classify(from_addr, subject)
    return "" if result == "_archive" else result
```

### Pattern migration from old classifier.py

Patterns already in organizer (keep organizer destination, remove from noise):
- `@netcoins`, `@coinbase` → `Crypto`
- `@paypal` → `Financier/PayPal`
- `@interac.ca` → `Financier/Interac`
- `@bnc.ca` → `Financier/BNC`
- `@caaquebec` → `Financier/CAA`
- `@cscv.qc.ca`, `@csdraveurs`, `@cssd.gouv` → `Education`
- `@greengeeks` → `Factures/GreenGeeks`
- `@staples` → `Factures/BureauEnGros`
- `@telus` → `Factures/Telus`
- `@facebookmail` → `Social`

Patterns migrated to named folders (were archive-only, now categorized):
- `@equifax`, `@creditkarma`, `@transunion` → `Financier/Credit`
- `@fondsftq` → `Financier/FondsFTQ`
- `@linode`, `@cloudflare`, `@gitguardian` → `Dev-Tech`
- `@coupa.com` → `Travail/Fournisseurs`
- `@mozilla.com` → `Dev-Tech`
- `@vargacombat`, `@howtofightnow` → `Formations`
- `@maudeperron`, `@lc.maudeperron` → `Personnel/Coaching`
- `@claris.com` → `Dev-Tech`
- `@enom.com`, `@name-services` → `Dev-Tech/Domaines`
- `cpanel@` → `Dev-Tech`

Patterns that become `_archive` (pure noise):
- Generic senders: `noreply@`, `no-reply@`, `notification`, `newsletter@`, `marketing@`, `promo@`, `donotreply@`, `mailer-daemon@`, `bounce@`, `news@`, `info@`, `nepasrepondre`, `ne-pas-repondre`
- Bulk subdomains: `@e.`, `@email.`, `@mail.`, `@newsletter.`
- Promo subjects: `unsubscribe`, `save \d+%`, `off today`, `limited time`, `special offer`, `act now`, `don.t miss`, `last call`, `hours left`, `days left`
- Transactional subjects: `your order`, `your receipt`, `shipping`, `delivery notification`, `password reset`, `verify your email`, `confirm your`, `welcome to`, `your weekly`, `your monthly`
- Feedback subjects: `how was your`, `rate your`, `review your`, `feedback`, `vos commentaires`, `votre opinion`, `comment pouvons`
- Security notifications: `security alert`, `incident detected`, `trusted device`, `events notification`
- French promo: `offre sp`, `rabais`, `solde`, `aubaine`, `economisez`, `prix r`, `jour de prime`, `prolongation`, `ailes gratuites`, `chasse aux cocos`, `menu enfant`, `infolettre`, `webinaires`
- Mixed/other subjects: `podcast`, `episode`, `mot de passe`, `app password`, `alerte.*pointage`, `alerte.*cr.dit`
- Other from-addresses: `@cegep-heritage` → `_archive`, `@privaterelay.appleid` → `_archive`
- Remaining old-classifier-only senders: `@cooperativeplacedumarche`, `@chefsplate`, `@clubcage`, `@opinion.panalyticsgroup`, `@mail-corpo.ia.ca` → `_archive` (food/promo/surveys with no folder value)
- Old classifier Yahoo/iCloud newsletter senders already covered by organizer (no action needed — they already map to named folders via organizer patterns): `@hello.teachable.com` → Dev-Tech, `@sitepoint.com` → Dev-Tech, `@livecode.com` → Dev-Tech, `@insideapple.apple.com` → Notifications/Apple, `@go.sage.com` → Dev-Tech, `accounts@firefox.com` → Dev-Tech, `@gitcoin.co` → Dev-Tech, `@filemaker.com` → Dev-Tech, `@cfcpc.ca` → Travail/APCHQ, `@koolreport.com` → Dev-Tech, `@monkeybreadsoftware` → Dev-Tech, `@xojo.com` → Dev-Tech, `@intercom-mail.com` → Newsletters, `@hello.scribd.com` → Dev-Tech, `@stackblitz.com` → Dev-Tech, `@lists.quebecloisirs.com` → Newsletters, `@eff.org` → Newsletters, `loyalty@shinybud` → Newsletters, `@info.intact.ca` → Assurance, `@tommorrison.uk` → Newsletters, `communication@apchq` → Travail/APCHQ, `infolettre@renaud-bray` → Newsletters, `aws-marketing.*@amazon` → Dev-Tech, `@info.pentoncem.com` → Newsletters

### organizer.py — simplified

- `run_organize()` calls `classify()` instead of `categorize()`
- Single pass over INBOX:
  - `classify()` returns folder name → COPY+DELETE to that folder
  - `classify()` returns `"_archive"` → COPY+DELETE to `provider["archive_folder"]`
  - `classify()` returns `""` → skip (stays in INBOX)
- Local `categorize()` function removed — all logic in classifier.py

### archiver.py — reduced

- `run_archive()` → removed (organize does this now)
- `run_preview()` → updated to use `classify()`, shows destination folder:
  - `[Factures/Anthropic] From: ... | Subject: ...`
  - `[_archive] From: ... | Subject: ...`
  - `[KEEP] From: ... | Subject: ...`
- `show_stats()` → unchanged
- Stats tracking updated: organize now saves stats in the same format

### invoice_scanner.py — simplified

- `is_invoice()` → removed
- `INVOICE_FROM_PATTERNS`, `INVOICE_SUBJECT_STRINGS`, `_INVOICE_SUBJECT_PATTERNS` → removed
- `_scan_inbox()` → removed (no more pattern-based INBOX scanning)
- `run_scan()` → only discovers and scans `Factures/*` and `Financier/*` folders
- `_scan_folder()`, `extract_pdf_info()`, `build_report()`, `_write_reports()` → unchanged
- `resolve_provider()`, `PROVIDER_MAP` → unchanged (still needed for display names)

### cli.py — updated

- `archive` subcommand → removed
- `organize` subcommand → unchanged (now does both sorting and archiving)
- `preview` subcommand → shows unified classify() output with destinations
- `invoices` and `stats` subcommands → unchanged

## Safety Invariants (unchanged)

1. COPY-verified-before-DELETE: no email deleted without confirmed copy
2. Circuit breaker: 3 consecutive FETCH errors → stop entirely
3. UIDs only: never sequence numbers
4. Credentials via Keychain only
5. iCloud STORE quoting: parenthesized flags and quoted folder names

## Testing Strategy

1. Unit tests for `classify()` — every pattern returns the expected destination
2. Coverage audit: run `classify()` against the full list of old classifier + organizer patterns, verify no pattern is lost
3. Overlap detection test: ensure no from-address can match both a named folder AND `_archive` (specific patterns must shadow generic ones)
4. Preview-first validation: run `preview gmail` with new classifier, compare output against old `preview` + old `organize` to verify consistency
5. Existing tests for imap_client, invoice_scanner, invoice_downloader updated as needed

## Files Changed

| File | Action |
|------|--------|
| `classifier.py` | Rewrite — unified `classify()` with all patterns |
| `organizer.py` | Simplify — use `classify()`, remove local `categorize()` |
| `archiver.py` | Remove `run_archive()`, update `run_preview()` |
| `invoice_scanner.py` | Remove `is_invoice()` and INBOX scanning |
| `cli.py` | Remove `archive` command |
| `CLAUDE.md` | Update commands and architecture docs |
| `tests/test_classifier.py` | Rewrite for `classify()` |
| `tests/test_cli.py` | Update for removed `archive` command |
| `tests/test_invoice_scanner.py` | Update for removed `is_invoice()` |
