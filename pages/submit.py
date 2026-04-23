from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st
from services.db_service import init_db, save_vendor
from services.retrieval_service import RetrievalService

st.set_page_config(page_title="Submit a Vendor", page_icon="📋", layout="centered")

try:
    init_db()
    db_ok = True
except Exception as e:
    db_ok = False
    db_error = str(e)


@st.cache_resource(show_spinner=False)
def get_retrieval():
    return RetrievalService()


# ── Page header ───────────────────────────────────────────────────────────────
st.title("📋 Submit a Vendor")
st.write("Fill in the vendor details below and hit **Submit**. All fields except Name and Company are optional.")
st.divider()

if not db_ok:
    st.error(f"Database not available: {db_error}")
    st.stop()

# ── Submission form ───────────────────────────────────────────────────────────
with st.form("vendor_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        name    = st.text_input("Vendor Name *", placeholder="e.g. John Smith")
        phone   = st.text_input("Phone",         placeholder="e.g. +1 555-000-1234")
        rate    = st.text_input("Rate / Price",  placeholder="e.g. $50/hr or $2,000/month")
        website = st.text_input("Website",       placeholder="e.g. https://example.com")

    with col2:
        company  = st.text_input("Company *",    placeholder="e.g. Acme Corp")
        email    = st.text_input("Email",        placeholder="e.g. vendor@example.com")
        category = st.text_input("Category",     placeholder="e.g. IT, Catering, Logistics")
        location = st.text_input("Location",     placeholder="e.g. New York, NY")

    services = st.text_area(
        "Services Offered",
        placeholder="Briefly describe what this vendor offers...",
        height=100,
    )
    notes = st.text_area(
        "Additional Notes",
        placeholder="Any other relevant information...",
        height=80,
    )

    submitted = st.form_submit_button("Submit Vendor", type="primary", use_container_width=True)

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    if not name.strip() or not company.strip():
        st.error("**Vendor Name** and **Company** are required.")
    else:
        raw = {
            "name":     name,
            "company":  company,
            "phone":    phone,
            "email":    email,
            "rate":     rate,
            "website":  website,
            "category": category,
            "location": location,
            "services": services,
            "notes":    notes,
        }
        fields = {k: v.strip() for k, v in raw.items() if v.strip()}

        vid = save_vendor(fields)
        try:
            get_retrieval().index_vendor(vid, fields)
        except Exception:
            pass

        st.success(f"**{name}** from **{company}** has been added to the vendor directory!")
        st.balloons()

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Vendor AI Tracker · All submissions are stored securely.")
