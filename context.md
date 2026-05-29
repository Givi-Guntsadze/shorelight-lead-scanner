# traQRecord Handoff Context

Last updated: 2026-05-29
Working directory at update time: `C:\Users\user\Documents\LEAF\shorelight-lead-scanner`
Git branch: `main`
Git remote after rename: `origin https://github.com/Givi-Guntsadze/traqrecord.git`

## Current Status

This repo was originally named and documented around a Shorelight event. It is now being made tenant-agnostic and rebranded as `traQRecord`.

The GitHub repository has been renamed by the user to `Givi-Guntsadze/traqrecord`. The local git remote has been updated to:

```text
https://github.com/Givi-Guntsadze/traqrecord.git
```

The local folder is still:

```text
C:\Users\user\Documents\LEAF\shorelight-lead-scanner
```

An attempted local folder rename to `C:\Users\user\Documents\LEAF\traqrecord` failed because Windows reported the directory was being used by another process. No files were moved. The next agent should not assume the folder has been renamed locally unless it verifies the path.

## Key Decisions

1. Product and user-facing brand is `traQRecord`.
2. Technical identifiers, repo name, URL path, storage keys, and examples use `traqrecord`.
3. The app remains reusable per event. For each event, update `API_URL` in `index.html` to that event's Google Apps Script Web App URL.
4. Keep `?uni=` as the URL parameter for booth/institution tagging. It is a historical compatibility name and can represent a university, booth, partner, counselor, or general scanning station.
5. Keep `Uni_ID` in the Google Sheet `Raw_Scans` contract and CSV processing. Do not rename it casually; `Code.gs`, `scripts/process_leads.py`, and existing sheets depend on it.
6. Do not scaffold a new repo per event. Reuse this repo by changing the Apps Script URL, creating event-specific booth links, and exporting that event's CSVs after the event.
7. The public GitHub Pages URL should no longer mention Shorelight after Pages updates for the renamed repo:

```text
https://givi-guntsadze.github.io/traqrecord/
```

## Mental Stack

The system has three phases:

1. Registration phase
   - External form/n8n creates a registration row and a unique ticket/UUID.
   - Confirmation email sends a QR code containing that ticket/UUID.
   - `email-templates/confirmation-email.html` is a reusable starter template, not an active deployment source of truth.

2. Event-day scan phase
   - Volunteers open the GitHub Pages scanner with `?uni=<BOOTH_OR_INSTITUTION_ID>`.
   - `index.html` reads `?uni=`, stores scans in browser localStorage under `traqrecord_scan_queue`, and syncs to the configured Apps Script URL.
   - `Code.gs` receives `uni`, `uuid`, and optional `timestamp`, then appends to the active spreadsheet's `Raw_Scans` tab with columns `Timestamp`, `Uni_ID`, `UUID`.
   - Each event should have its own Google Sheet and Apps Script Web App URL. `API_URL` controls which sheet receives raw scans.

3. Post-event processing phase
   - Export the event registration sheet as `registrations.csv`.
   - Export the same event's `Raw_Scans` tab as `raw_scans.csv`.
   - Run `python scripts\process_leads.py registrations.csv raw_scans.csv`.
   - Output is one file per `Uni_ID` under `reports\`, for example `reports\leads_GENERAL.csv`.

Edited surfaces in this rebrand:

- `index.html`: title is `traQRecord`; storage key is `traqrecord_scan_queue`; configuration comment and example URL are neutral.
- `README.md`: rewritten around reusable `traQRecord` workflow, repo rename, neutral booth examples, and `traqrecord` Pages URL.
- `TESTING.md`: neutralized examples and expected GitHub Pages URL.
- `Code.gs`: header changed to `traQRecord Lead Receiver`.
- `scripts/process_leads.py`: CLI header/output and comments now use booth/institution language while preserving `Uni_ID`.
- `scripts/load_test_scanner.py`: load-test wording neutralized.
- `requirements.txt`: comment neutralized.
- `email-templates/confirmation-email.html`: document title neutralized.
- `output/playwright/multi_device_exact.js`: test helper now reads `traqrecord_scan_queue`.

## Verification Already Run

The following checks were run before writing this handoff:

```text
rg -n "Shorelight|shorelight|SHORELIGHT|HARVARD|YALE|Budget-friendly|budgetfriendly|shorelight-lead-scanner|shorelight_scan_queue|Live Scanner"
```

Result: no matches after removing the legacy storage-key compatibility shim.

```text
python -m py_compile scripts\process_leads.py scripts\load_test_scanner.py
```

Result: exit code 0.

```text
python scripts\process_leads.py registrations.csv raw_scans.csv
```

Result: exit code 0. It loaded 336 registrations and 51 scans, generated one `srhuni` report with 51 leads, and wrote `reports\leads_srhuni.csv`. It also emitted the existing Pandas 4 deprecation warning at `scripts\process_leads.py:107` for `select_dtypes(include=['object'])`.

```text
git diff --check
```

Result: exit code 0. Git printed CRLF normalization warnings for edited files, but no whitespace errors.

Browser smoke test:

- Served `index.html` locally on `http://127.0.0.1:8765/index.html?uni=BOOTH_A`.
- Mocked `html5-qrcode` and the Google Script endpoint.
- Confirmed `document.title` is `traQRecord`.
- Confirmed visible booth/institution label is `BOOTH_A`.
- Confirmed `localStorage` key is `traqrecord_scan_queue`.
- Confirmed mocked scan sync reached `All synced`.

## Known Caveats

1. The local folder still has the old name because Windows locked the directory during the rename attempt.
2. GitHub Pages may need a short redeploy window after the repo rename and push.
3. The current `API_URL` in `index.html` still points to the last configured Apps Script Web App URL. For the next event, replace it with that event's Web App URL.
4. The Pandas deprecation warning is not caused by the rebrand. It is safe for the current run but should be cleaned up later.
5. `reports\leads_srhuni.csv` was regenerated during verification, but its content did not show as modified in git status at the time of the handoff.

## Next Steps

1. After commit and push, verify the renamed GitHub Pages URL in a browser:

```text
https://givi-guntsadze.github.io/traqrecord/?uni=TEST
```

Expected result: page title `traQRecord`, top-left scan target `TEST`, camera permission prompt or scanner widget.

2. If the Pages URL 404s, check GitHub repo settings:

```text
Repository: Givi-Guntsadze/traqrecord
Settings -> Pages
Source: main branch, / (root)
```

Wait 1-2 minutes after saving or after the push, then retest.

3. Once Codex/terminal file locks are gone, optionally rename the local folder:

```powershell
Rename-Item -LiteralPath "C:\Users\user\Documents\LEAF\shorelight-lead-scanner" -NewName "traqrecord"
```

Then reopen Codex in:

```text
C:\Users\user\Documents\LEAF\traqrecord
```

4. For the next event, create or open that event's Google Sheet, paste `Code.gs` into Apps Script, deploy a new Web App with access set to `Anyone`, and copy the Web App URL.

5. Replace `API_URL` in `index.html` with the new event's Web App URL, commit, push, and wait for GitHub Pages to redeploy.

6. Create booth/institution links in the form:

```text
https://givi-guntsadze.github.io/traqrecord/?uni=GENERAL
https://givi-guntsadze.github.io/traqrecord/?uni=BOOTH_A
```

Use stable IDs because each distinct `uni` value becomes a separate post-event report file.

7. Before event day, run a live smoke:

```text
Open the Pages URL with ?uni=TEST
Scan a disposable QR code
Confirm a row appears in that event sheet's Raw_Scans tab
Delete the disposable row if needed
```

8. After the event, export `registrations.csv` and `raw_scans.csv` from the same event sheet, place them in the repo root, and run:

```powershell
python scripts\process_leads.py registrations.csv raw_scans.csv
```

9. Optional cleanup for a future patch: silence the Pandas warning in `scripts/process_leads.py` by replacing the deprecated `select_dtypes(include=['object'])` usage with an explicit object/string-safe approach and rerun the CSV processing workflow.
