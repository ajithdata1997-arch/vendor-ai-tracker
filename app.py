from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st
import pandas as pd
from services.db_service import init_db, save_vendor, get_all_vendors, get_backend
from services.retrieval_service import RetrievalService

st.set_page_config(page_title="Vendor AI Tracker", page_icon="🤖", layout="wide")

# ── Bootstrap ─────────────────────────────────────────────────────────────────
@st.cache_resource
def _init_db():
    init_db()
    return get_backend()

try:
    _backend = _init_db()
    db_ok = True
except Exception as e:
    db_ok = False
    _backend = "unknown"
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

def bulk_import(df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        fields = {
            col: str(row[col]).strip()
            for col in df.columns
            if str(row[col]).strip() and str(row[col]).strip().lower() != "nan"
        }
        if not fields:
            continue
        vid = save_vendor(fields)
        retrieval.index_vendor(vid, fields)
        count += 1
    return count


def _vendors_dataframe(vendors: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from vendors with varying fields, putting id first and created_at last."""
    if not vendors:
        return pd.DataFrame()
    skip = {"id", "created_at"}
    field_keys = []
    for v in vendors:
        for k in v:
            if k not in skip and k not in field_keys:
                field_keys.append(k)
    cols = ["id"] + field_keys + ["created_at"]
    rows = [{c: v.get(c, "") for c in cols} for v in vendors]
    df = pd.DataFrame(rows, columns=cols)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Vendor Directory")

    if not db_ok:
        st.error(f"Database not connected: {db_error}")
    else:
        vendors = get_all_vendors()
        if vendors:
            st.dataframe(_vendors_dataframe(vendors), use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(vendors)} vendor(s)")
        else:
            st.info("No vendors yet.")

    st.divider()

    # ── Bulk Upload ───────────────────────────────────────────────────────────
    st.subheader("Bulk Upload")
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx", "xls"],
        help="All columns are imported automatically — no mapping needed.",
    )
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)

            st.caption(f"Preview: {len(df_upload)} rows · {len(df_upload.columns)} columns")
            st.dataframe(df_upload.head(5), use_container_width=True, hide_index=True)

            if st.button("Import Vendors", type="primary"):
                with st.spinner("Importing..."):
                    n = bulk_import(df_upload)
                st.success(f"Imported {n} vendor(s)!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to read file: {e}")

    st.divider()
    st.caption("Powered by Groq · pgvector · Supabase")


# ── Main Chat ─────────────────────────────────────────────────────────────────
st.title("Vendor AI Chatbot")
st.caption("Submit vendor details or ask questions about stored vendors")

if _backend == "sqlite":
    st.warning(
        "**Local database (SQLite) is active.** "
        "Data is stored only on this machine and is NOT shared with other users. "
        "To collect vendor details from multiple people, connect Supabase: "
        "unpause your project at supabase.com and ensure DATABASE_URL is set.",
        icon="⚠️",
    )

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
        summary = "\n".join(f"| {k} | {v} |" for k, v in draft.items())
        return (
            "Here is a summary:\n\n"
            f"| Field | Value |\n|---|---|\n{summary}\n\n"
            "Type **yes** to save or **no** to cancel."
        )

    if step == "confirm":
        if lower in ("yes", "y", "confirm", "save", "ok", "sure"):
            vid = save_vendor(draft)
            retrieval.index_vendor(vid, draft)
            st.session_state.step = None
            st.session_state.vendor_draft = {}
            return f"Vendor **{draft.get('name', vid)}** saved! (ID: {vid})"
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
        lines = []
        for i, v in enumerate(vendors, 1):
            detail = " | ".join(
                f"{k}: {v[k]}" for k in v if k not in ("id", "created_at") and v[k]
            )
            lines.append(f"{i}. {detail}")
        return "**All vendors:**\n\n" + "\n".join(lines)

    if any(k in lower for k in ["help", "what can you do", "how do i"]):
        return (
            "Here is what I can do:\n\n"
            "- **Add vendor**: Say *add vendor*\n"
            "- **View vendors**: Say *show all vendors*\n"
            "- **Bulk upload**: Use the sidebar file uploader (CSV or Excel) — all columns imported automatically\n"
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
