import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIG ---
DATA_FILE = "kilometer_log.xlsx"
LOGO_FILE = "Voltano Metering Logo PNG.png"
CLAIM_START_DAY = 15
COLUMNS = ["Date", "Start_km", "End_km", "Distance_km", "From", "To", "Reason", "User"]

# Google Sheets settings
GS_CRED_JSON = "service_account.json"  # path to your Google service account JSON
GS_USERS_SHEET = "Technicians"         # sheet with columns: Username, Password, LastLogin
GS_KM_SHEET = "Kilometers"             # sheet for logging kilometers

# --- AUTHENTICATION ---
@st.cache_resource
def get_gs_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GS_CRED_JSON, scope)
    return gspread.authorize(creds)

@st.cache_data
def load_users():
    client = get_gs_client()
    sheet = client.open(GS_USERS_SHEET).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def verify_login(username, password):
    users = load_users()
    user = users[users['Username'] == username]
    if not user.empty and user.iloc[0]['Password'] == password:
        # update last login
        client = get_gs_client()
        sheet = client.open(GS_USERS_SHEET).sheet1
        row = user.index[0] + 2  # account for header
        sheet.update_cell(row, 3, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
    return False

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user'] = None

# --- PAGE FUNCTIONS ---
def kilometer_logger():
    """Existing kilometer logger code adapted to include user."""
    df = load_km_data()
    st.header(f"📊 Kilometer Logger for {st.session_state['user']}")
    # ... insert the refactored logger code here, appending 'User' to new_row
    # Placeholder for brevity
    st.write("[Kilometer logger functionality goes here]")

def incident_reports():
    st.header("📝 Incident Reports")
    st.write("[Incident report form goes here]")

def risk_assessments():
    st.header("⚠️ Risk Assessments")
    st.write("[Risk assessment form goes here]")

def google_docs():
    st.header("📄 Company Docs")
    links = {
        "Job Cards": "https://docs.google.com/…",
        "Vehicle Inspections": "https://docs.google.com/…",
        "Meter Installations": "https://docs.google.com/…"
    }
    for name, url in links.items():
        st.markdown(f"- [{name}]({url})")

# --- MAIN APP ---
def main():
    if not st.session_state['logged_in']:
        cols = st.columns([1,2,1])
        with cols[1]:
            if os.path.exists(LOGO_FILE):
                st.image(Image.open(LOGO_FILE), width=150)
            st.title("Voltano Metering Login")
            users = load_users()['Username'].tolist()
            uname = st.selectbox("Username", users)
            pwd = st.text_input("Password", type="password")
            if st.button("Login"):
                if verify_login(uname, pwd):
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = uname
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials")
    else:
        # Sidebar menu
        pages = {
            "Kilometer Logger": kilometer_logger,
            "Incident Reports": incident_reports,
            "Risk Assessments": risk_assessments,
            "Company Docs": google_docs
        }
        st.sidebar.image(LOGO_FILE, width=100)
        choice = st.sidebar.radio("Navigate to", list(pages.keys()))
        pages[choice]()

if __name__ == "__main__":
    main()
