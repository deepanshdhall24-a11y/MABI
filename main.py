import streamlit as st
import os
from fpdf import FPDF
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

# --- 1. CONFIGURATION ---
PROPERTY_NAME = "Maa Anjana Apartments"
PROPERTY_ADDRESS = "O-47A Karmyogi Enclave Kamla Nagar, Agra, UP 282005"
PAYMENT_MOBILE = "8433462897"
QUERY_CONTACT = "Mr. Rahul Kushwah: 6396764390"
RATE_PER_UNIT = 8
SOCIETY_CHARGE = 200

# --- 2. GOOGLE DRIVE SYNC LOGIC ---
def get_drive_service():
    # This updated logic correctly handles Streamlit TOML secrets
    if "gcp_service_account" in st.secrets:
        # Instead of json.loads, we pass the secret directly as a dictionary
        info = dict(st.secrets["gcp_service_account"])
    else:
        # Local fallback remains the same
        with open("your_service_account_key.json") as f:
            info = json.load(f)
            
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def get_or_create_month_folder(service, parent_id, month_name):
    query = f"name = '{month_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query).execute().get('files', [])
    
    if results:
        return results[0]['id']
    else:
        file_metadata = {
            'name': month_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(file_name, folder_id):
    service = get_drive_service()
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_name, mimetype='application/pdf')
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# --- 3. PDF GENERATION CLASS ---
class MobileBillPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "!! JAI SHREE RAM !! | !! JAI GURUJI !! | !! JAI MATA DI !!", ln=1, align='C')
        self.ln(2)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 8, PROPERTY_NAME, ln=1, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, PROPERTY_ADDRESS, ln=1, align="C")
        self.line(10, 35, 200, 35)
        self.ln(10)

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="Maa Anjana Bills", page_icon="🏡")

st.title("🏡 Maa Anjana Bills")
st.info("Mobile Bill Generator with Laptop Sync")

# --- STEP 1: MONTHLY SETUP ---
with st.expander("Step 1: Monthly Common Details", expanded=True):
    month = st.text_input("Billing Month", value=datetime.now().strftime("%B %Y"))
    pump_bill = st.number_input("Total Pump Bill (₹)", value=0.0)
    total_persons = st.number_input("Total Persons in Building", value=1, min_value=1)
    # The Folder ID you copied from your Google Drive URL
    base_folder_id = "YOUR_FOLDER_ID_HERE" 

st.divider()

# --- STEP 2: TENANT INPUT ---
st.subheader("Step 2: Tenant Billing")
p_id = st.text_input("Person ID (e.g. P001)")
p_name = st.text_input("Tenant Name")

c1, c2 = st.columns(2)
with c1:
    prev_r = st.number_input("Previous Meter Reading", value=0.0)
with c2:
    curr_r = st.number_input("Current Meter Reading", value=0.0)

rent = st.number_input("Monthly Rent (₹)", value=0.0)
dues = st.number_input("Previous Dues (₹)", value=0.0)

if st.button("🚀 Generate & Sync Bill"):
    if not p_name or curr_r < prev_r:
        st.error("Invalid details! Check name and readings.")
    else:
        with st.spinner("Creating bill and syncing to laptop..."):
            # Calculations
            units = curr_r - prev_r
            elec_cost = units * RATE_PER_UNIT
            pump_share = pump_bill / total_persons
            total = elec_cost + SOCIETY_CHARGE + pump_share + rent + dues

            # PDF Generation
            pdf = MobileBillPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"BILL INVOICE - {month}", ln=1)
            pdf.set_font("Helvetica", "", 12)
            pdf.cell(0, 8, f"Name: {p_name} (ID: {p_id})", ln=1)
            pdf.ln(5)
            
            # Simple Table
            pdf.cell(140, 10, "Description", 1); pdf.cell(50, 10, "Amount", 1, ln=1)
            pdf.cell(140, 10, f"Rent", 1); pdf.cell(50, 10, f"{rent:.2f}", 1, ln=1)
            pdf.cell(140, 10, f"Electricity ({units} units)", 1); pdf.cell(50, 10, f"{elec_cost:.2f}", 1, ln=1)
            pdf.cell(140, 10, f"Submersible Share", 1); pdf.cell(50, 10, f"{pump_share:.2f}", 1, ln=1)
            pdf.cell(140, 10, f"Society Charge", 1); pdf.cell(50, 10, f"{SOCIETY_CHARGE:.2f}", 1, ln=1)
            if dues > 0:
                pdf.cell(140, 10, f"Arrears/Dues", 1); pdf.cell(50, 10, f"{dues:.2f}", 1, ln=1)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(140, 12, "TOTAL PAYABLE", 1); pdf.cell(50, 12, f"{total:.2f}", 1, ln=1)

            # Filename
            file_name = f"{month.replace(' ', '_')}_{p_name.replace(' ', '_')}.pdf"
            pdf.output(file_name)

            # Sync to Drive
            try:
                service = get_drive_service()
                month_folder_id = get_or_create_month_folder(service, base_folder_id, month.replace(' ', '_'))
                upload_to_drive(file_name, month_folder_id)
                
                st.success(f"✅ Bill for {p_name} is now on your laptop!")
                
                # Also allow local download on phone
                with open(file_name, "rb") as f:
                    st.download_button("📩 Download Copy to Phone", f, file_name)
                    
                # Cleanup local server file
                os.remove(file_name)
            except Exception as e:
                st.error(f"Sync failed, but PDF generated. Error: {e}")
