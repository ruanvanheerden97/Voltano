import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Voltano Metering",  # name shown in browser tab and mobile shortcut
    page_icon="Voltano Metering Logo PNG.png",  # path to your logo file (set as favicon)
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CONFIG ---
LOGO_FILE = "Voltano Metering Logo PNG.png"
GS_CRED_JSON = "creds.json"
GS_SPREADSHEET_NAME = "Technicians"
GS_KM_WORKSHEET = "Kilometers"
COLUMNS = ["Date","Start_km","End_km","Distance_km","From","To","Reason","User"]

# --- AUTH HELPERS ---
@st.cache_resource
def get_gs_client():
    """
    Authenticate to Google Sheets using a service account.
    Uses the JSON in Streamlit secrets 'GOOGLE_SERVICE_ACCOUNT_JSON' or falls back to a local file.
    """
    import json, tempfile
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Load credentials from secrets if available
    if "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets:
        creds_json = st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]
        creds_dict = json.loads(creds_json)
        # write to temp file
        tf = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        json.dump(creds_dict, tf)
        tf.flush()
        key_path = tf.name
    else:
        key_path = GS_CRED_JSON
    creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
    return gspread.authorize(creds)

@st.cache_data
def load_users():
    client = get_gs_client()
    spreadsheet = client.open(GS_SPREADSHEET_NAME)
    users_sheet = spreadsheet.worksheet("Technicians")
    return pd.DataFrame(users_sheet.get_all_records())

def verify_login(username, password):
    users = load_users()
    row = users[users['Username'] == username]
    if not row.empty and str(row.iloc[0]['Password']).strip() == str(password).strip():
        client = get_gs_client()
        spreadsheet = client.open(GS_SPREADSHEET_NAME)
        users_sheet = spreadsheet.worksheet("Technicians")
        idx = row.index[0] + 2
        col = users.columns.get_loc('LastLogin') + 1
        users_sheet.update_cell(idx, col, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
    return False

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.nickname = None
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# --- COMMON FUNCTIONS ---
def draw_logo_center(width=350):
    """
    Display the company logo centered using three columns.
    """
    if os.path.exists(LOGO_FILE):
        cols = st.columns([1, 2, 1])
        with cols[1]:
            st.image(Image.open(LOGO_FILE), width=width)

# --- PAGES ---
def home_page():
    draw_logo_center()
    st.markdown(
        f"<h2 style='text-align:center; font-size:18px;'>Welcome, {st.session_state.nickname}</h2>",
        unsafe_allow_html=True
    )
    st.write("")
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

def kilometer_logger():
    draw_logo_center()
    st.markdown(
        f"<h3 style='text-align:center; font-size:14px;'>Kilometer Logger for {st.session_state.nickname}</h3>",
        unsafe_allow_html=True
    )
    client = get_gs_client()
    spreadsheet = client.open(GS_SPREADSHEET_NAME)
    km_sheet = spreadsheet.worksheet(GS_KM_WORKSHEET)
    records = km_sheet.get_all_records()
    df = pd.DataFrame(records)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNS]
    df[['Start_km','End_km','Distance_km']] = df[['Start_km','End_km','Distance_km']].apply(pd.to_numeric, errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    user = st.session_state.username
    df_user = df[df['User'] == user]
    # Prefill starting km as last completed end_km
    last_ended = df_user['End_km'].dropna().max() if not df_user['End_km'].dropna().empty else 0.0
    pending = df_user[df_user['End_km'].isna()]
    if not pending.empty:
        st.warning("⚠️ You have an unfinished entry. Complete it before adding new ones.")
        idx = st.selectbox("Select pending entry to complete", pending.index,
                           format_func=lambda i: f"{pending.at[i,'Date'].date()} Start: {pending.at[i,'Start_km']}km")
        row = pending.loc[idx]
        start_km = float(row['Start_km'])
        new_to = st.text_input("To", value=row.get('To',''))
        new_reason = st.text_input("Reason", value=row.get('Reason',''))
        end_km = st.number_input("Closing Odometer (km)", value=start_km, min_value=start_km, step=1.0, format="%.1f")
        if st.button("Complete Entry"):
            if end_km < start_km:
                st.error("Closing reading cannot be less than opening reading.")
            else:
                distance = end_km - start_km
                headers = km_sheet.row_values(1)
                row_num = idx + 2
                km_sheet.update_cell(row_num, headers.index('End_km')+1, end_km)
                km_sheet.update_cell(row_num, headers.index('Distance_km')+1, distance)
                km_sheet.update_cell(row_num, headers.index('To')+1, new_to)
                km_sheet.update_cell(row_num, headers.index('Reason')+1, new_reason)
                st.success(f"Completed {distance:.1f} km on {row['Date'].date()}")
        return
    st.subheader("➕ New Entry")
    with st.form("new_km", clear_on_submit=True):
        d = st.date_input("Date", value=date.today())
        f_loc = st.text_input("From")
        t_loc = st.text_input("To")
        note = st.text_input("Reason (optional)")
        s_km = st.number_input("Opening km", min_value=0.0, step=1.0, format="%.1f")
        half = st.checkbox("Half entry (no closing km)")
        e_km = None if half else st.number_input("Closing km", min_value=s_km, step=1.0, format="%.1f")
        submitted = st.form_submit_button("Save Entry")
    if submitted:
        if not f_loc.strip(): st.error("Enter 'From'.")
        elif not half and e_km is None: st.error("Enter closing km or check half entry.")
        elif not half and e_km < s_km: st.error("Closing km must be ≥ opening km.")
        else:
            dist = e_km - s_km if e_km is not None else ''
            new = [d.strftime('%Y-%m-%d'), float(s_km), float(e_km) if e_km is not None else '', float(dist) if dist!='' else '', f_loc, t_loc, note, user]
            km_sheet.append_row(new)
            st.success("Entry saved.")
            return
    st.subheader("🗒️ Your Log")
    st.dataframe(df_user.sort_values('Date').reset_index(drop=True))
    st.subheader("📥 Download by Date Range")
    dates = df_user['Date'].dt.date
    min_date = dates.min() if not dates.empty else date.today()
    max_date = dates.max() if not dates.empty else date.today()
    start_date = st.date_input("Start date", value=min_date, min_value=min_date, max_value=max_date)
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
    if start_date > end_date:
        st.error("Start must be ≤ End.")
    else:
        report_df = df_user[(df_user['Date'] >= pd.to_datetime(start_date)) & (df_user['Date'] <= pd.to_datetime(end_date))]
        def to_excel(dfm):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                dfm.to_excel(writer, index=False, sheet_name='Log')
            return buf.getvalue()
        st.download_button(
            "Download Excel",
            data=to_excel(report_df),
            file_name=f"km_report_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def incident_reports():
    draw_logo_center()
    st.markdown(f"<h3 style='text-align:center; font-size:14px;'>Incident Reports</h3>", unsafe_allow_html=True)

def risk_assessments():
    draw_logo_center()
    st.markdown(f"<h3 style='text-align:center; font-size:14px;'>Risk Assessments</h3>", unsafe_allow_html=True)

def company_docs():
    draw_logo_center()
    st.markdown(f"<h3 style='text-align:center; font-size:14px;'>Company Docs</h3>", unsafe_allow_html=True)
    docs = {
        "Job Cards": "https://docs.google.com/forms/d/e/1FAIpQLSdYgwhqsrFNH3r3mohsokOLeYFd8ASNgFnxHdGLVP5llcFMhA/viewform?pli=1",
        "Meter Installations": "https://docs.google.com/forms/d/e/1FAIpQLScpU4mgRMCvnpa7yrfCZlTmH3dUEKLhdZz0KOFM8QOUwyLkvQ/viewform",
        "Kiosk/DB Inspections": "https://docs.google.com/forms/d/e/1FAIpQLSdLhFeITjCkq0HksHvBl0GqmuyKJAVStc4IVTmFyJbdyqwaLw/viewform"
    }
    cols = st.columns([1,2,1])
    with cols[1]:
        for name, url in docs.items():
            html = (
                f"<div style='text-align:center; margin:10px;'>"
                f"<a href='{url}' target='_blank'>"
                f"<button style='padding:12px 24px; font-size:16px; border-radius:8px;'>{name}</button>"
                f"</a></div>"
            )
            st.markdown(html, unsafe_allow_html=True)

def main():
    if not st.session_state.logged_in:
        cols = st.columns([1,2,1])
        with cols[1]:
            draw_logo_center(400)
            st.markdown("<h2 style='text-align:center; font-size:16px;'>Voltano Metering Login</h2>", unsafe_allow_html=True)
            users = load_users()
            nickname = st.selectbox("Select User", users['Nickname'])
            username = users.loc[users['Nickname']==nickname, 'Username'].iloc[0]
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if verify_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.nickname = nickname
                    st.session_state.page = 'Home'
                else:
                    st.error("Invalid credentials")
    else:
        with st.sidebar:
            draw_logo_center(300)
            opts = ['Home', 'Kilometer Logger', 'Incident Reports', 'Risk Assessments', 'Company Docs']
            choice = st.radio("Navigate", opts, index=opts.index(st.session_state.page))
            st.session_state.page = choice
        if st.session_state.page == 'Home':
            home_page()
        elif st.session_state.page == 'Kilometer Logger':
            kilometer_logger()
        elif st.session_state.page == 'Incident Reports':
            incident_reports()
        elif st.session_state.page == 'Risk Assessments':
            risk_assessments()
        elif st.session_state.page == 'Company Docs':
            company_docs()

if __name__ == '__main__':
    main()
