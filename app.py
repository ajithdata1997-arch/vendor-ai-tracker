import streamlit as st
import pandas as pd
from services.db_service import init_db, save_vendor, get_all_vendors
from services.retrieval_service import RetrievalService

st.set_page_config(page_title="Vendor AI Tracker", page_icon="🤖", layout="wide")

# ── Bootstrap ─────────────────────────────────────────────────────────────────
try:
    init_db()
    db_ok = True
except Exception as e:
    db_ok = False
    db_error = str(e)


@st.cache_resource(show_spinner="Loading AI model...")
def get_retrieval_service():
    return RetrievalService()


retrieval = get_retrieval_service()

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! I am your **Vendor AI Assistant**. Here is what I can do:\n\n"
                "- **Add a vendor** -- say *add vendor* to submit details\n"
                "- **View vendors** -- say *show all vendors*\n"
                "- **Ask questions** -- e.g., *Who has the lowest rate?*\n\n"
                "You can also **upload a CSV or Excel file** from the sidebar."
            ),
        }
    ]
if "step" not in st.session_state:
    st.session_state.step = None
if "vendor_draft" not in st.session_state:
    st.session_state.vendor_draft = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def detect_column(columns, keywords):
    for col in columns:
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


def bulk_import(df, name_col, phone_col, company_col, rate_col):
    count = 0
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name.lower() == "nan":
            continue
        vid = save_vendor(
            name,
            str(row[phone_col]).strip(),
            str(row[company_col]).strip(),
            str(row[rate_col]).strip(),
        )
        retrieval.index_vendor(
            vid, name,
            str(row[phone_col]).strip(),
            str(row[company_col]).strip(),
            str(row[rate_col]).strip(),
        )
        count += 1
    return count


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Vendor Directory")

    if not db_ok:
        st.error(f"Database not connected: {db_error}")
    else:
        vendors = get_all_vendors()
        if vendors:
            df_v = pd.DataFrame(vendors)[["id", "name", "company_name", "phone", "rate", "created_at"]]
            df_v.columns = ["ID", "Name", "Company", "Phone", "Rate", "Added"]
            df_v["Added"] = pd.to_datetime(df_v["Added"]).dt.strftime("%Y-%m-%d")
            st.dataframe(df_v, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(vendors)} vendor(s)")
        else:
            st.info("No vendors yet.")

    st.divider()

    # ── Bulk Upload ───────────────────────────────────────────────────────────
    st.subheader("Bulk Upload")
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx", "xls"],
        help="Must have columns for name, phone, company, and rate.",
    )
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)

            st.caption(f"Preview: {len(df_upload)} rows")
            st.dataframe(df_upload.head(5), use_container_width=True, hide_index=True)
            cols = df_upload.columns.tolist()

            auto_name    = detect_column(cols, ["name", "vendor"])
            auto_phone   = detect_column(cols, ["phone", "mobile", "contact", "tel"])
            auto_company = detect_column(cols, ["company", "org", "firm", "business"])
            auto_rate    = detect_column(cols, ["rate", "price", "cost", "fee", "amount"])

            st.markdown("**Map columns:**")
            name_col    = st.selectbox("Name",    cols, index=cols.index(auto_name)    if auto_name    else 0)
            phone_col   = st.selectbox("Phone",   cols, index=cols.index(auto_phone)   if auto_phone   else 0)
            company_col = st.selectbox("Company", cols, index=cols.index(auto_company) if auto_company else 0)
            rate_col    = st.selectbox("Rate",    cols, index=cols.index(auto_rate)    if auto_rate    else 0)

            if st.button("Import Vendors", type="primary"):
                with st.spinner("Importing..."):
                    n = bulk_import(df_upload, name_col, phone_col, company_col, rate_col)
                st.success(f"Imported {n} vendor(s)!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to read file: {e}")

    st.divider()
    st.caption("Powered by Groq · pgvector · Supabase")


# ── Main Chat ─────────────────────────────────────────────────────────────────
st.title("Vendor AI Chatbot")
st.caption("Submit vendor details or ask questions about stored vendors")

if not db_ok:
    st.error(
        "Database not connected. Set DATABASE_URL in your .env file (local) "
        "or in Streamlit Cloud secrets."
    )
    st.stop()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Message processing ────────────────────────────────────────────────────────
def process_input(user_input):
    step  = st.session_state.step
    draft = st.session_state.vendor_draft
    text  = user_input.strip()
    lower = text.lower()

    if step == "name":
        if not text:
            return "Please provide a valid name."
        draft["name"] = text
        st.session_state.step = "phone"
        return f"Got it! What is **{text}**'s phone number?"

    if step == "phone":
        draft["phone"] = text
        st.session_state.step = "company"
        return "What is the **company name**?"

    if step == "company":
        draft["company_name"] = text
        st.session_state.step = "rate"
        return "What is the **rate**? (e.g., $50/hr, $5,000/month)"

    if step == "rate":
        draft["rate"] = text
        st.session_state.step = "confirm"
        return (
            "Here is a summary:\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Name | {draft['name']} |\n"
            f"| Phone | {draft['phone']} |\n"
            f"| Company | {draft['company_name']} |\n"
            f"| Rate | {draft['rate']} |\n\n"
            "Type **yes** to save or **no** to cancel."
        )

    if step == "confirm":
        if lower in ("yes", "y", "confirm", "save", "ok", "sure"):
            vid = save_vendor(
                draft["name"], draft["phone"], draft["company_name"], draft["rate"]
            )
            retrieval.index_vendor(
                vid, draft["name"], draft["phone"],
                draft["company_name"], draft["rate"],
            )
            st.session_state.step = None
            st.session_state.vendor_draft = {}
            return f"Vendor **{draft['name']}** saved! (ID: {vid})"
        if lower in ("no", "n", "cancel", "abort"):
            st.session_state.step = None
            st.session_state.vendor_draft = {}
            return "Cancelled. What else can I help you with?"
        return "Please type **yes** to save or **no** to cancel."

    add_kw = ["add vendor", "new vendor", "submit vendor", "add a vendor",
              "register vendor", "add new vendor", "enter vendor", "create vendor"]
    if any(k in lower for k in add_kw):
        st.session_state.step = "name"
        st.session_state.vendor_draft = {}
        return "Let's add a new vendor! What is the **vendor name**?"

    show_kw = ["show all", "list all", "view all", "all vendors", "show vendors", "list vendors"]
    if any(k in lower for k in show_kw):
        vendors = get_all_vendors()
        if not vendors:
            return "No vendors yet. Say **add vendor** or upload a file from the sidebar."
        lines = [
            f"{i}. **{v['name']}** | {v['company_name']} | {v['phone']} | {v['rate']}"
            for i, v in enumerate(vendors, 1)
        ]
        return "**All vendors:**\n\n" + "\n".join(lines)

    if any(k in lower for k in ["help", "what can you do", "how do i"]):
        return (
            "Here is what I can do:\n\n"
            "- **Add vendor**: Say *add vendor*\n"
            "- **View vendors**: Say *show all vendors*\n"
            "- **Bulk upload**: Use the sidebar file uploader (CSV or Excel)\n"
            "- **Ask questions**: e.g., *Who has the lowest rate?*"
        )

    return retrieval.answer(text)


# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Type a message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Thinking..."):
        response = process_input(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
