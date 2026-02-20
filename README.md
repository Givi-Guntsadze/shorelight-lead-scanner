# Shorelight Lead Scanner

A complete lead retrieval system for education fairs. Enables 30+ universities to digitally collect leads from 3000+ attendees using their smartphones.

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

#### 2.2 Configure the Scanner

1. Open `index.html`
2. Line ~239: Paste your Web App URL
3. Commit and push to GitHub
4. Enable GitHub Pages (Settings → Pages → main branch)

#### 2.3 Create University Links

| University | URL |
|------------|-----|
| Harvard | `https://yoursite.github.io/shorelight-lead-scanner/?uni=HARVARD` |
| Yale | `https://yoursite.github.io/shorelight-lead-scanner/?uni=YALE` |
| MIT | `https://yoursite.github.io/shorelight-lead-scanner/?uni=MIT` |

---

### Phase 3: Post-Event Processing

#### 3.1 Export Data

1. From your Registration Sheet → Download as `registrations.csv`
2. From `Raw_Scans` tab → Download as `raw_scans.csv`

#### 3.2 Run the Script

```bash
# Install dependencies
pip install -r requirements.txt

# Process leads
python scripts/process_leads.py
```

#### 3.3 Output

```
reports/
├── leads_HARVARD.csv
├── leads_YALE.csv
├── leads_MIT.csv
└── ...
```

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
