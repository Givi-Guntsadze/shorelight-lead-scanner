"""
traQRecord - Post-Event Processing Script
=========================================
This script performs the "Split & Delivery" operation after the event ends.

INPUTS:
  - registrations.csv: Export from your "Lead Registrations" Google Sheet
  - raw_scans.csv: Export from the "Raw_Scans" tab

OUTPUT:
  - leads_BOOTH_A.csv, leads_BOOTH_B.csv, etc. (one per booth/institution)
"""

import pandas as pd
import os
import sys

REGISTRATION_COLUMN_ALIASES = {
    'full_name': 'full_name',
    'fullname': 'full_name',
    'name': 'full_name',
    'email': 'email',
    'phone': 'phone',
    'school': 'school',
    'grade': 'Grade',
    'age': 'Age',
    'intake_year': 'intake_year',
    'consent_text': 'consent_text',
    'consent': 'consent_text',
    'submission_time': 'submission_time',
    'time': 'submission_time',
}

REPORT_COLUMN_LABELS = {
    'full_name': 'fullName',
    'school': 'School',
    'Grade': 'Grade',
    'Age': 'Age',
    'phone': 'Phone',
    'email': 'email',
    'intake_year': 'intake_year',
    'consent_text': 'consent',
    'submission_time': 'time',
    'UUID': 'UUID',
}

def load_data(reg_file: str, scans_file: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and validate the input CSV files."""
    
    # Check files exist
    if not os.path.exists(reg_file):
        print(f"ERROR: {reg_file} not found")
        print("   Export your Registration Sheet from Google Sheets as CSV")
        sys.exit(1)
        
    if not os.path.exists(scans_file):
        print(f"ERROR: {scans_file} not found")
        print("   Export the Raw_Scans tab from Google Sheets as CSV")
        sys.exit(1)
    
    registrations = pd.read_csv(reg_file)
    scans = pd.read_csv(scans_file)
    
    print(f"Loaded {len(registrations)} registrations")
    print(f"Loaded {len(scans)} scans")
    
    return registrations, scans

def clean_data(registrations: pd.DataFrame, scans: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Standardize column names and clean data."""
    
    # Normalize column names (strip whitespace, lowercase)
    registrations.columns = registrations.columns.str.strip()
    scans.columns = scans.columns.str.strip()
    
    # Find the UUID column in registrations (might be 'ticket_id', 'UUID', 'uuid', etc.)
    uuid_col = None
    for col in registrations.columns:
        if col.lower() in ['ticket_id', 'uuid', 'ticketid', 'id']:
            uuid_col = col
            break
    
    if not uuid_col:
        print("ERROR: Could not find UUID column in registrations")
        print(f"   Available columns: {list(registrations.columns)}")
        sys.exit(1)
    
    # Standardize UUID column name
    registrations = registrations.rename(columns={uuid_col: 'UUID'})

    normalized_names: dict[str, str] = {}
    for col in registrations.columns:
        normalized = col.strip().lower().replace(' ', '_')
        canonical = REGISTRATION_COLUMN_ALIASES.get(normalized)
        if canonical and canonical not in registrations.columns:
            normalized_names[col] = canonical

    if normalized_names:
        registrations = registrations.rename(columns=normalized_names)
    
    # Ensure UUID columns are strings
    registrations['UUID'] = registrations['UUID'].astype(str).str.strip().str.upper()
    scans['UUID'] = scans['UUID'].astype(str).str.strip().str.upper()
    
    # Remove unicode replacement characters (common encoding issue)
    for df in [registrations, scans]:
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(lambda x: str(x).replace('\ufffd', '') if pd.notna(x) else x)
    
    print(f"Cleaned data (UUID column: '{uuid_col}')")
    if normalized_names:
        print(f"Normalized registration columns: {normalized_names}")
    
    return registrations, scans

def merge_data(registrations: pd.DataFrame, scans: pd.DataFrame) -> pd.DataFrame:
    """Join scans with registration data."""
    
    merged = pd.merge(
        scans,
        registrations,
        on='UUID',
        how='left'
    )
    
    # Check for unmatched scans
    match_column_candidates = ['full_name', 'email', 'phone', 'school', 'Grade']
    unmatched_col = next((col for col in match_column_candidates if col in merged.columns), None)
    unmatched = merged[merged[unmatched_col].isna()] if unmatched_col else pd.DataFrame()
    if len(unmatched) > 0:
        print(f"WARNING: {len(unmatched)} scans could not be matched to registrations")
    
    print(f"Merged data: {len(merged)} records")
    
    return merged

def generate_reports(merged: pd.DataFrame, output_dir: str = 'reports'):
    """Generate one CSV file per booth or institution."""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get unique booth/institution IDs from the historical Uni_ID column.
    if 'Uni_ID' not in merged.columns:
        print("ERROR: 'Uni_ID' column not found in scans data")
        sys.exit(1)
    
    scan_targets = merged['Uni_ID'].dropna().unique()
    print(f"\nGenerating reports for {len(scan_targets)} booth/institution IDs...\n")
    
    # Define columns to include in reports
    # Prioritize common registration fields, exclude internal IDs
    priority_columns = [
        'full_name', 'school', 'Grade', 'Age', 'phone',
        'email', 'intake_year', 'consent_text', 'submission_time', 'UUID'
    ]
    
    # Find which columns actually exist
    export_columns = [col for col in priority_columns if col in merged.columns]
    
    if not export_columns:
        # Fallback: use all columns except internal ones
        exclude = ['UUID', 'Uni_ID', 'Timestamp', 'uuid', 'ticket_id']
        export_columns = [col for col in merged.columns if col not in exclude]
    
    print(f"   Exporting columns: {export_columns}\n")

    match_column_candidates = ['full_name', 'email', 'phone', 'school', 'Grade']
    report_match_column = next((col for col in match_column_candidates if col in merged.columns), None)
    
    # Generate report for each booth/institution.
    total_leads = 0
    for uni in sorted(scan_targets):
        uni_data = merged[merged['Uni_ID'] == uni]
        
        # Clean filename
        uni_clean = str(uni).strip().replace(' ', '_').replace('/', '-')
        filename = os.path.join(output_dir, f"leads_{uni_clean}.csv")
        
        # Export
        if report_match_column:
            uni_data = uni_data[uni_data[report_match_column].notna()]

        report = uni_data[export_columns].drop_duplicates()
        report = report.rename(columns=REPORT_COLUMN_LABELS)
        report.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"   OK {uni}: {len(report)} leads -> {filename}")
        total_leads += len(report)
    
    print(f"\nDone. Generated {len(scan_targets)} reports with {total_leads} total leads.")
    print(f"   Output folder: {os.path.abspath(output_dir)}")

def main():
    print("\n" + "="*60)
    print("  traQRecord - Post-Event Processing")
    print("="*60 + "\n")
    
    # Default file names
    reg_file = 'registrations.csv'
    scans_file = 'raw_scans.csv'
    
    # Allow command-line override
    if len(sys.argv) >= 3:
        reg_file = sys.argv[1]
        scans_file = sys.argv[2]
    
    print(f"Registration file: {reg_file}")
    print(f"Scans file: {scans_file}\n")
    
    # Process
    registrations, scans = load_data(reg_file, scans_file)
    registrations, scans = clean_data(registrations, scans)
    merged = merge_data(registrations, scans)
    generate_reports(merged)

if __name__ == "__main__":
    main()
