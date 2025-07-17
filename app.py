import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="Voltano Field App", layout="wide", initial_sidebar_state="collapsed")

# --- CONFIG ---
DATA_FILE = "kilometer_log.xlsx"
LOGO_FILE = "Voltano Metering Logo PNG.png"
GS_CRED_JSON = "creds.json"
GS_USERS_SHEET = "Technicians"
GS_KM_SHEET = "Kilometers"

# --- AUTH HELPERS ---
@st.cache_resource
def get_gs_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GS_CRED_JSON, scope)
    return gspread.authorize(creds)

@st.cache_data
def load_users():
    client = get_gs_client()
    sheet = client.open(GS_USERS_SHEET).sheet1
    return pd.DataFrame(sheet.get_all_records())

def verify_login(username, password):
    users = load_users()
    row = users[users['Username']==username]
    if not row.empty and str(row.iloc[0]['Password']).strip()==str(password).strip():
        # update last login
        client = get_gs_client()
        sheet = client.open(GS_USERS_SHEET).sheet1
        idx = row.index[0]+2
        col = users.columns.get_loc('LastLogin')+1
        sheet.update_cell(idx, col, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
    return False

# --- SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in=False
    st.session_state.username=None
    st.session_state.nickname=None
if 'page' not in st.session_state:
    st.session_state.page='Home'

# --- PAGE STRUCTURES ---
def draw_logo_center(width=300):
    if os.path.exists(LOGO_FILE):
        cols = st.columns([1,2,1])
        with cols[1]: st.image(Image.open(LOGO_FILE), width=width)

# Home page
def home_page():
    draw_logo_center(300)
    st.markdown(f"<h2 style='text-align:center;'>Welcome, {st.session_state.nickname}</h2>", unsafe_allow_html=True)
    st.write("")
    # Navigation buttons with explicit mapping
    btns = [
        ("📊 Kilometer Logger", 'Kilometer Logger'),
        ("📝 Incident Reports", 'Incident Reports'),
        ("⚠️ Risk Assessments", 'Risk Assessments'),
        ("📄 Company Docs", 'Company Docs')
    ]
    cols = st.columns([1,1,1,1,1])
    for i, (label, page_key) in enumerate(btns):
        with cols[i+1]:
            if st.button(label, key=label):
                st.session_state.page = page_key
                return

# Kilometer Logger stub
def kilometer_logger():
    draw_logo_center(200)
    st.markdown(f"<h3 style='text-align:center;'>Kilometer Logger for {st.session_state.nickname}</h3>", unsafe_allow_html=True)
    # TODO: implement logger UI

# Incident Reports stub
def incident_reports():
    draw_logo_center(200)
    st.markdown(f"<h3 style='text-align:center;'>Incident Reports</h3>", unsafe_allow_html=True)
    # TODO: implement incident report UI

# Risk Assessments stub
def risk_assessments():
    draw_logo_center(200)
    st.markdown(f"<h3 style='text-align:center;'>Risk Assessments</h3>", unsafe_allow_html=True)
    # TODO: implement risk assessment UI

# Company Docs page
def company_docs():
    draw_logo_center(200)
    st.markdown(f"<h3 style='text-align:center;'>Company Docs</h3>", unsafe_allow_html=True)
    docs = {
        "Job Cards": "https://docs.google.com/forms/d/e/1FAIpQLSdYgwhqsrFNH3r3mohsokOLeYFd8ASNgFnxHdGLVP5llcFMhA/viewform?pli=1",
        "Meter Installations": "https://docs.google.com/forms/d/e/1FAIpQLScpU4mgRMCvnpa7yrfCZlTmH3dUEKLhdZz0KOFM8QOUwyLkvQ/viewform",
        "Kiosk/DB Inspections": "https://docs.google.com/forms/d/e/1FAIpQLSdLhFeITjCkq0HksHvBl0GqmuyKJAVStc4IVTmFyJbdyqwaLw/viewform"
    }
    cols = st.columns([1,2,1])
    with cols[1]:
        for name, url in docs.items():
            html = f"<div style='text-align:center; margin:10px;'>"
            html += f"<a href='{url}' target='_blank'>"
            html += f"<button style='padding:12px 24px; font-size:16px; border-radius:8px;'>{name}</button></a></div>"
            st.markdown(html, unsafe_allow_html=True)

# --- MAIN APP ---
def main():
    if not st.session_state.logged_in:
        cols = st.columns([1,2,1])
        with cols[1]:
            draw_logo_center(250)
            st.markdown("<h2 style='text-align:center;'>Voltano Metering Login</h2>", unsafe_allow_html=True)
            users = load_users()
            nickname = st.selectbox("Select User", users['Nickname'])
            username = users.loc[users['Nickname']==nickname, 'Username'].iloc[0]
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if verify_login(username, password):
                    st.session_state.logged_in=True
                    st.session_state.username=username
                    st.session_state.nickname=nickname
                    st.session_state.page='Home'
                else:
                    st.error("Invalid credentials")
    else:
        # Sidebar nav
        with st.sidebar:
            draw_logo_center(150)
            options = ['Home', 'Kilometer Logger', 'Incident Reports', 'Risk Assessments', 'Company Docs']
            choice = st.radio("Navigate", options, index=options.index(st.session_state.page))
            st.session_state.page = choice
        # Render
        if st.session_state.page == 'Home': home_page()
        elif st.session_state.page == 'Kilometer Logger': kilometer_logger()
        elif st.session_state.page == 'Incident Reports': incident_reports()
        elif st.session_state.page == 'Risk Assessments': risk_assessments()
        elif st.session_state.page == 'Company Docs': company_docs()

if __name__ == '__main__':
    main()
