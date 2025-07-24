import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import paramiko
import networkx as nx
import matplotlib.pyplot as plt
from io import StringIO
import pygraphviz

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Voltano Metering",
    page_icon="Voltano Metering Logo PNG.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CONFIG ---
LOGO_FILE       = "Voltano Metering Logo PNG.png"
GS_CRED_JSON    = "creds.json"
GS_SPREADSHEET  = "Technicians"
GS_KM_WORKSHEET = "Kilometers"
GS_HIER_SHEET   = "Hierarchy"
GS_HIST_SHEET   = "HistoricalReadings"
COLUMNS_KM      = ["Date","Start_km","End_km","Distance_km","From","To","Reason","User"]

# --- AUTH HELPERS ---
@st.cache_resource
def get_gs_client():
    import json, tempfile
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    if "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
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
    sheet  = client.open(GS_SPREADSHEET).worksheet("Technicians")
    return pd.DataFrame(sheet.get_all_records())

def verify_login(username, password):
    users = load_users()
    row   = users[users["Username"]==username]
    if not row.empty and str(row.iloc[0]["Password"]).strip()==str(password).strip():
        # update last login
        client   = get_gs_client()
        sheet    = client.open(GS_SPREADSHEET).worksheet("Technicians")
        idx      = row.index[0] + 2
        col      = users.columns.get_loc("LastLogin") + 1
        sheet.update_cell(idx, col, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return True
    return False

def logout():
    for key in ["logged_in","username","nickname","page","confirm_logout"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.logged_in = False
    st.session_state.page      = "Home"

def navigate(page_key):
    st.session_state.page = page_key

# --- COMMON UI ---
def draw_logo_center(width=350):
    if os.path.exists(LOGO_FILE):
        cols = st.columns([1,2,1])
        with cols[1]:
            st.image(Image.open(LOGO_FILE), width=width)

# --- PAGE FUNCTIONS ---
def home_page():
    draw_logo_center(350)
    st.markdown(f"<h2 style='text-align:center; font-size:18px;'>Welcome, {st.session_state.nickname}</h2>",
                unsafe_allow_html=True)
    btns = [
        ("📊 Kilometer Logger", "Kilometer Logger"),
        ("📝 Incident Reports",     "Incident Reports"),
        ("⚠️ Risk Assessments",     "Risk Assessments"),
        ("📄 Company Docs",         "Company Docs"),
        ("🌐 Site Hierarchy",       "Site Hierarchy"),
    ]
    cols = st.columns([1,1,1,1,1,1])
    for i, (label, key) in enumerate(btns):
        with cols[i+1]:
            if st.button(label, key=f"home_{key}"):
                navigate(key)

def kilometer_logger():
    draw_logo_center(300)
    st.markdown(f"<h3 style='text-align:center; font-size:14px;'>Kilometer Logger for {st.session_state.nickname}</h3>",
                unsafe_allow_html=True)
    client = get_gs_client()
    sheet  = client.open(GS_SPREADSHEET).worksheet(GS_KM_WORKSHEET)
    df     = pd.DataFrame(sheet.get_all_records())
    for col in COLUMNS_KM:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS_KM] = df[COLUMNS_KM]
    df[['Start_km','End_km','Distance_km']] = df[['Start_km','End_km','Distance_km']].apply(pd.to_numeric, errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    user = st.session_state.username
    df_user = df[df['User']==user]

    # Pending half entry
    pending = df_user[df_user['End_km'].isna()]
    if not pending.empty:
        st.warning("⚠️ You have an unfinished entry. Complete it first.")
        idx = st.selectbox(
            "Select pending entry", pending.index,
            format_func=lambda i: f"{pending.at[i,'Date'].date()} Start: {pending.at[i,'Start_km']}km"
        )
        row     = pending.loc[idx]
        start_km= float(row['Start_km'])
        new_to  = st.text_input("To",     value=row.get('To',''))
        new_re  = st.text_input("Reason", value=row.get('Reason',''))
        end_km  = st.number_input("Closing km", value=start_km, min_value=start_km, step=1.0, format="%.1f")
        if st.button("Complete Entry"):
            if end_km<start_km:
                st.error("Closing km < opening km.")
            else:
                dist = end_km - start_km
                headers = sheet.row_values(1)
                rnum = idx+2
                sheet.update_cell(rnum, headers.index('End_km')+1,    end_km)
                sheet.update_cell(rnum, headers.index('Distance_km')+1, dist)
                sheet.update_cell(rnum, headers.index('To')+1,         new_to)
                sheet.update_cell(rnum, headers.index('Reason')+1,     new_re)
                st.success(f"Completed {dist:.1f} km.")

    # New Entry
    st.subheader("➕ New Entry")
    last_end = df_user['End_km'].dropna().max() if not df_user['End_km'].dropna().empty else 0.0
    with st.form("new_km", clear_on_submit=True):
        d    = st.date_input("Date",   value=date.today())
        f_loc= st.text_input("From")
        t_loc= st.text_input("To")
        note = st.text_input("Reason (optional)")
        s_km = st.number_input("Opening km", value=float(last_end), min_value=0.0, step=1.0, format="%.1f")
        half= st.checkbox("Half entry (no closing km)")
        if not half:
            e_km= st.number_input("Closing km", min_value=s_km, step=1.0, format="%.1f")
        else:
            e_km = None
        submit = st.form_submit_button("Save Entry")
    if submit:
        if not f_loc.strip():
            st.error("Enter 'From'")
        elif not half and e_km is None:
            st.error("Enter closing km or check half.")
        elif not half and e_km < s_km:
            st.error("Closing km < opening km.")
        else:
            dist = e_km - s_km if e_km is not None else ''
            new_row = [
                d.strftime('%Y-%m-%d'),
                float(s_km),
                float(e_km) if e_km is not None else '',
                float(dist) if dist!='' else '',
                f_loc, t_loc, note, user
            ]
            sheet.append_row(new_row)
            st.success("Entry saved.")

    # Display Log
    st.subheader("🗒️ Your Log")
    st.dataframe(df_user.sort_values('Date').reset_index(drop=True))

    # Download by Date Range
    st.subheader("📥 Download by Date Range")
    dates = df_user['Date'].dt.date
    min_d = dates.min() if not dates.empty else date.today()
    max_d = dates.max() if not dates.empty else date.today()
    start_date = st.date_input("Start", value=min_d, min_value=min_d, max_value=max_d)
    end_date   = st.date_input("End",   value=max_d, min_value=min_d, max_value=max_d)
    if start_date> end_date:
        st.error("Start ≤ End")
    else:
        report_df = df_user[(df_user['Date']>=pd.to_datetime(start_date)) &
                             (df_user['Date']<=pd.to_datetime(end_date))]
        def to_excel(dfm):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                dfm.to_excel(w, index=False, sheet_name='Log')
            return buf.getvalue()
        st.download_button("Download Excel", data=to_excel(report_df),
            file_name=f"km_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def incident_reports():
    draw_logo_center()
    st.markdown("<h3 style='text-align:center; font-size:14px;'>Incident Reports</h3>",
                unsafe_allow_html=True)

def risk_assessments():
    draw_logo_center()
    st.markdown("<h3 style='text-align:center; font-size:14px;'>Risk Assessments</h3>",
                unsafe_allow_html=True)

def company_docs():
    draw_logo_center()
    st.markdown("<h3 style='text-align:center; font-size:14px;'>Company Docs</h3>",
                unsafe_allow_html=True)
    docs = {
        "Job Cards":          "<PASTE_JOB_CARDS_URL>",
        "Meter Installations":"<PASTE_INSTALL_URL>",
        "Kiosk/DB Inspections":"<PASTE_KIOSK_URL>"
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

# --- HIERARCHY HELPERS ---
@st.cache_data(ttl=3600)
def load_hierarchy():
    client = get_gs_client()
    sheet  = client.open(GS_SPREADSHEET).worksheet(GS_HIER_SHEET)
    return pd.DataFrame(sheet.get_all_records())

def append_to_historical(site, df):
    client = get_gs_client()
    sheet  = client.open(GS_SPREADSHEET).worksheet(GS_HIST_SHEET)
    for _, row in df.iterrows():
        sheet.append_row([
            site,
            row["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            row["Serial"],
            row["Value"]
        ])

def fetch_new_readings(site, cache_dir="sftp_cache/"):
    os.makedirs(cache_dir, exist_ok=True)
    host = "sftp.voltano.co.za"
    port = 222
    user = "Ashford/VoltanoSFTP"
    pw   = "S#nsus22.co.za"

    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=pw)
    sftp = paramiko.SFTPClient.from_transport(transport)

    hier  = load_hierarchy()
    types= hier[hier["Site"]==site]["AMR_Type"].dropna().unique()
    for amr in types:
        remote_dir = f"/{amr}/{site}/"
        try:
            files = sftp.listdir(remote_dir)
        except IOError:
            continue
        for fname in files:
            if not fname.lower().endswith(".csv"):
                continue
            local_path = os.path.join(cache_dir, f"{amr}_{fname}")
            if os.path.exists(local_path):
                continue
            with sftp.open(remote_dir+fname) as remote_f:
                text = remote_f.read().decode()
                df   = pd.read_csv(StringIO(text), parse_dates=["timestamp"])
            df["AMR_Type"] = amr
            append_to_historical(site, df)
            df.to_csv(local_path, index=False)

    sftp.close()
    transport.close()

def site_hierarchy_page():
    draw_logo_center(300)
    st.markdown("<h3 style='text-align:center;'>Site Hierarchy & Consumption</h3>",
                unsafe_allow_html=True)

    hier  = load_hierarchy()
    sites = sorted(hier["Site"].unique())
    site  = st.selectbox("Select Site", sites)

    util  = st.radio("Utility Type", ["Electricity","Cold Water","Hot Water"], horizontal=True)

    with st.spinner("Fetching latest readings…"):
        fetch_new_readings(site)

    client = get_gs_client()
    sheet  = client.open(GS_SPREADSHEET).worksheet(GS_HIST_SHEET)
    hist   = pd.DataFrame(sheet.get_all_records())
    required_cols = ["timestamp", "Site", "Serial", "Value"]
    missing_cols = [col for col in required_cols if col not in hist.columns]
    if missing_cols:
        st.error(f"❌ Missing columns in HistoricalReadings sheet: {missing_cols}")
        return

    hist["timestamp"] = pd.to_datetime(hist["timestamp"])
    df_latest = (hist[hist["Site"]==site]
                 .sort_values("timestamp")
                 .groupby("Serial", as_index=False)
                 .last())

    sub = hier[(hier["Site"]==site)&(hier["Meter_Type"]==util)]
    total_expected = len(sub)
    total_fetched  = df_latest["Serial"].nunique()
    st.info(f"Imported {total_fetched}/{total_expected} meters")

    try:
        pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    except ImportError:
        st.error("❌ pygraphviz is not installed. Please install it to use this layout.")
        return

    G = nx.DiGraph()
    for _, r in sub.iterrows():
        parent = r["ParentMeterSerial"] or "MUNIC"
        G.add_edge(parent, r["Serial"], label=r["Stand"])
    labels = {
        n: (f"{n}\n{df_latest.loc[df_latest.Serial==n,'Value'].iat[0]:.1f}"
            if n in df_latest["Serial"].values else f"{n}\n–")
        for n in G.nodes
    }
    pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    plt.figure(figsize=(8,6))
    nx.draw(G, pos, with_labels=True, labels=labels, node_size=1500, font_size=8)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G,"label"), font_size=7)
    st.pyplot(plt.gcf())

    st.subheader("▣ Latest Readings")
    st.dataframe(df_latest.set_index("Serial")[["timestamp","Value"]], height=300)

# --- MAIN FUNCTION ---
def main():
    # 1) LOGIN SCREEN
    if not st.session_state.logged_in:
        cols = st.columns([1,2,1])
        with cols[1]:
            draw_logo_center(400)
            st.markdown("<h2 style='text-align:center; font-size:16px;'>Voltano Metering Login</h2>",
                        unsafe_allow_html=True)
            users = load_users()
            nickname = st.selectbox("Select User", users['Nickname'])
            username = users.loc[users['Nickname']==nickname, 'Username'].iloc[0]
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if verify_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username  = username
                    st.session_state.nickname  = nickname
                    st.session_state.page      = 'Home'
                else:
                    st.error("Invalid credentials")
        return

    # 2) AUTHENTICATED LAYOUT
    with st.sidebar:
        draw_logo_center(120)
        st.markdown("---")
        pages = ["Home","Kilometer Logger","Incident Reports","Risk Assessments","Company Docs","Site Hierarchy"]
        choice = st.radio("Menu", pages, index=pages.index(st.session_state.page), key="nav_radio")
        st.session_state.page = choice
        st.markdown("---")
        if 'confirm_logout' not in st.session_state:
            if st.button("🔒 Logout"):
                st.session_state.confirm_logout = True
        else:
            st.warning("Are you sure you want to log out?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes"):
                    logout()
            with c2:
                if st.button("No"):
                    del st.session_state.confirm_logout

    # 3) PAGE RENDERING
    if st.session_state.page == "Home":
        home_page()
    elif st.session_state.page == "Kilometer Logger":
        kilometer_logger()
    elif st.session_state.page == "Incident Reports":
        incident_reports()
    elif st.session_state.page == "Risk Assessments":
        risk_assessments()
    elif st.session_state.page == "Company Docs":
        company_docs()
    elif st.session_state.page == "Site Hierarchy":
        site_hierarchy_page()

if __name__ == "__main__":
    main()
