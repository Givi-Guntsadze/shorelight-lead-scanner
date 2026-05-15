# Lead Scanner (Event Scaffold)

A reusable lead retrieval scaffold for education events. Originally built for Shorelight, now used for multiple events (info sessions, fairs, partner visits). Each event gets its own Google Sheet + Web App URL; the scanner app and post-event script are shared.

**Events run so far:** Shorelight fair (Mar 2026), Budget-Friendly Universities info session (May 2026)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         REGISTRATION PHASE                          │
├─────────────────────────────────────────────────────────────────────┤
│  User → CF7 Form → n8n generates ticket_id → Google Sheet + Email w/QR  │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           EVENT DAY                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Volunteer opens ?uni=HARVARD → Scans QR → localStorage → Sheet     │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          POST-EVENT                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Download CSVs → Run Python script → leads_HARVARD.csv per uni      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
shorelight-lead-scanner/
├── index.html                    # Scanner PWA (deploy to GitHub Pages)
├── Code.gs                       # Google Apps Script (deploy as Web App)
├── email-templates/
│   └── confirmation-email.html   # Email template with QR code
├── scripts/
│   └── process_leads.py          # Post-event lead splitting
├── requirements.txt              # Python dependencies
└── .gitignore
```

## Setup Guide

### Phase 1: Registration System (WordPress & n8n)

#### 1.1 Send Data to n8n
Configure your Contact Form 7 or WordPress integration to send a webhook to your n8n workflow when a user registers.

#### 1.2 Generate Ticket ID
Inside your n8n workflow, use a **Set node** after the webhook receives the data to generate a unique `ticket_id`. This uses the last 4 digits of the timestamp combined with 4 random alphanumeric characters:

```javascript
{{ $now.toMillis().toString().slice(-4) }}{{ Math.random().toString(36).substring(2, 6).toUpperCase() }}
```

#### 1.3 Update Google Sheets
Send the user's registration details along with the newly generated `ticket_id` to your Google Sheet. Your sheet should have these columns:
| full_name | email | phone | school | Grade | intake_year | consent_text | submission_time | ticket_id |
|-----------|-------|-------|--------|-------|-------------|--------------|-----------------|-----------|

#### 1.4 Configure Confirmation Email
In your n8n email node, generate the dynamic QR code image using QuickChart.io by injecting the `ticket_id` into the URL:

```html
<img src="https://quickchart.io/qr?text={{ $json.ticket_id }}&size=250" alt="QR Code" />
```

See `email-templates/confirmation-email.html` for a full template.

---

### Phase 2: Scanner App (Event Day)

#### 2.1 Deploy Google Apps Script

1. Open your Google Sheet
2. **Extensions → Apps Script**
3. Paste contents of `Code.gs`
4. **Deploy → New deployment → Web App**
   - Execute as: Me
   - Access: Anyone
5. Copy the Web App URL

#### 2.2 Configure the Scanner for the Event

Each event has its own Google Sheet and therefore its own Web App URL.

1. Open `index.html`
2. Line ~239: Replace the existing Web App URL with the new event's URL
3. Commit and push to GitHub

GitHub Pages serves the latest commit, so updating the URL redeploys instantly.

#### 2.3 Create Booth Links

Booth links use the `?uni=` parameter to tag each scan with the scanning institution:

| Event | Booth | URL |
|-------|-------|-----|
| Shorelight fair | Shorelight | `https://givi-guntsadze.github.io/shorelight-lead-scanner/?uni=SHORELIGHT` |
| Budget-friendly info session | General | `https://givi-guntsadze.github.io/shorelight-lead-scanner/?uni=budgetfriendly` |

---

### Phase 3: Post-Event Processing

#### 3.1 Export Data

Each event has its own Google Sheet. Export from the correct sheet for the event you're processing:

1. From the event's Registration Sheet → Download as `registrations.csv`
2. From the same sheet's `Raw_Scans` tab → Download as `raw_scans.csv`

Place both files in the project root.

#### 3.2 Run the Script

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Process leads (default: reads registrations.csv + raw_scans.csv)
python scripts/process_leads.py

# Or pass filenames explicitly
python scripts/process_leads.py registrations.csv Raw_Scans.csv
```

#### 3.3 Output

One CSV per `Uni_ID` value found in the scans:

```
reports/
├── leads_SHORELIGHT.csv
├── leads_budgetfriendly.csv
└── leads_<UNI_ID>.csv
```

#### 3.4 Registration Column Flexibility

Different events may use different form field names. `process_leads.py` normalizes common variations automatically. Supported aliases (all case-insensitive):

| Form field name(s) | Normalized to |
|--------------------|---------------|
| `fullName`, `fullname`, `name`, `full_name` | `fullName` in output |
| `email` | `email` |
| `phone` | `Phone` |
| `school` | `School` |
| `grade`, `Grade` | `Grade` |
| `intake_year`, `intake year` | `intake_year` |
| `consent`, `consent_text` | `consent` |
| `time`, `submission_time` | `time` |
| `UUID`, `ticket_id`, `uuid` | join key (not in output) |

Columns not in this list are collected but excluded from the output CSV. If a field is missing from the registration form entirely, that column is simply absent from the report.

---

## Testing

See [TESTING.md](TESTING.md) for:
- Automated test results
- Manual testing steps
- Troubleshooting guide

---

## Key Features

- **Offline-First**: Scans saved to device, sync when online
- **Concurrent-Safe**: LockService handles 30+ simultaneous writers
- **Zero Server Cost**: GitHub Pages + Google Sheets
- **Dynamic QR**: No image storage, QuickChart renders on-the-fly
