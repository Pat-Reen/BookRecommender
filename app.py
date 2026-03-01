import os
import re
import anthropic
import streamlit as st
from dotenv import load_dotenv

from db import (
    init_db, add_book, get_books, update_book, delete_book,
    add_to_reading_list, get_reading_list, update_reading_list_item, delete_from_reading_list,
)

load_dotenv()

# On Streamlit Cloud, secrets live in st.secrets rather than env vars — bridge them.
try:
    import streamlit as _st
    for _k in ("ANTHROPIC_API_KEY", "DATABASE_URL"):
        if not os.getenv(_k) and _k in _st.secrets:
            os.environ[_k] = _st.secrets[_k]
except Exception:
    pass

init_db()

# ── Page config & styling ──────────────────────────────────────────────────────
st.set_page_config(page_title="Book Recommender", page_icon="📚", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3 {
        color: #2d6a4f;
    }

    .stButton > button {
        background-color: #2d6a4f;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.4rem 1.2rem;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }

    .stButton > button:hover {
        background-color: #1b4332;
        color: white;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        color: #2d6a4f !important;
        border-bottom-color: #2d6a4f !important;
    }

    /* Keep all column rows horizontal on mobile without overflowing */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        min-width: 0;
    }
    [data-testid="stHorizontalBlock"] > div {
        min-width: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📚 Book Recommender")


# ── Helpers ────────────────────────────────────────────────────────────────────
def stars(rating):
    if rating is None:
        return "—"
    return "★" * rating + "☆" * (5 - rating)


def parse_recommendations(text):
    """Split Claude's response into individual {title, author, year, md} dicts."""
    parts = re.split(r'(\*\*\d+\.\s[^\n]+\*\*)', text)
    recs = []
    i = 1
    while i < len(parts):
        header = parts[i]
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        m = re.match(r'\*\*\d+\.\s+(.+?)\s+[—–]\s+(.+?)(?:\s+\((\d{4})\))?\*\*', header)
        if m:
            recs.append({
                "title": m.group(1).strip(),
                "author": m.group(2).strip(),
                "year": int(m.group(3)) if m.group(3) else None,
                "md": header + "\n" + body,
            })
        i += 2
    return recs


def get_recommendations(books, mood):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    read_or_dnf = [b for b in books if b["status"] in ("read", "dnf")]
    all_titles = [b["title"] for b in books]

    library_lines = []
    for b in read_or_dnf:
        year_str = f" ({b['year']})" if b["year"] else ""
        rating_str = f"{b['rating']}/5" if b["rating"] else "unrated"
        notes_str = f" — Notes: {b['notes']}" if b["notes"] else ""
        library_lines.append(
            f"- {b['title']} by {b['author']}{year_str} — Rating: {rating_str}{notes_str}"
        )

    library_text = "\n".join(library_lines) if library_lines else "(no rated books yet)"
    exclude_text = ", ".join(all_titles) if all_titles else "none"
    mood_text = mood.strip() if mood.strip() else "None specified"

    user_message = f"""Library ({len(read_or_dnf)} books):
{library_text}

All titles to EXCLUDE (already read or want-to-read):
{exclude_text}

Mood / request: {mood_text}

Recommend 3–5 books I haven't read that match my taste."""

    system_prompt = """You are a personal book critic and recommender.
The user has shared their reading history with ratings and notes.
Recommend 3–5 books they haven't read yet that match their taste.
At least one pick must be a genuine wildcard — something unexpected, genre-crossing, or obscure that most readers wouldn't think to suggest, but that fits the reader's sensibility in a surprising way. Mark it with 🃏 directly after the title in the header.

For each book output exactly:

**N. Title — Author (Year)**
*Why it fits:* 2–3 bullet points tied to their specific liked books/notes.
*Potential miss:* 1 bullet point — honest reason it might not land."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_library, tab_list, tab_recommend = st.tabs(["My Library", "My List", "Recommend"])

# ── Tab 1: My Library ──────────────────────────────────────────────────────────
with tab_library:
    with st.expander("Add a book", expanded=False):
        with st.form("add_book_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Title *")
                author = st.text_input("Author *")
                year = st.number_input("Year", min_value=0, max_value=2100, value=None, step=1)
            with col2:
                rating = st.slider("Rating", min_value=1, max_value=5, value=3)
                fmt = st.selectbox("Format", ["print", "ebook", "audio"])
                status = st.selectbox("Status", ["read", "want", "dnf"])
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Book")

        if submitted:
            if not title.strip() or not author.strip():
                st.error("Title and Author are required.")
            else:
                add_book(
                    title=title.strip(),
                    author=author.strip(),
                    year=int(year) if year else None,
                    rating=rating,
                    format=fmt,
                    status=status,
                    notes=notes.strip() or None,
                )
                st.success(f"Added «{title}»!")
                st.rerun()

    if "editing_book" not in st.session_state:
        st.session_state.editing_book = None

    books = get_books()
    if not books:
        st.info("Your library is empty. Add some books above to get started.")
    else:
        st.markdown(f"**{len(books)} book{'s' if len(books) != 1 else ''} in your library**")
        fmt_options = ["print", "ebook", "audio"]
        status_options = ["read", "want", "dnf"]
        for b in books:
            with st.container(border=True):
                year_str = f" ({b['year']})" if b["year"] else ""
                st.markdown(f"**{b['title']}**{year_str}  \n*{b['author']}*")
                meta = [p for p in [stars(b["rating"]) if b["rating"] else None, b["status"], b["format"]] if p]
                if meta:
                    st.caption(" · ".join(meta))
                if b["notes"]:
                    st.caption(b["notes"])
                btn_edit, btn_del = st.columns(2)
                if btn_edit.button("✏️ Edit", key=f"edit_{b['id']}", use_container_width=True):
                    st.session_state.editing_book = b["id"]
                    st.rerun()
                if btn_del.button("🗑 Delete", key=f"del_{b['id']}", use_container_width=True):
                    delete_book(b["id"])
                    if st.session_state.editing_book == b["id"]:
                        st.session_state.editing_book = None
                    st.rerun()

            if st.session_state.editing_book == b["id"]:
                with st.form(f"edit_form_{b['id']}"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_title = st.text_input("Title *", value=b["title"])
                        e_author = st.text_input("Author *", value=b["author"])
                        e_year = st.number_input("Year", min_value=0, max_value=2100, value=b["year"] or None, step=1)
                    with e_col2:
                        e_rating = st.slider("Rating", 1, 5, b["rating"] or 3)
                        e_fmt = st.selectbox("Format", fmt_options, index=fmt_options.index(b["format"]) if b["format"] in fmt_options else 0)
                        e_status = st.selectbox("Status", status_options, index=status_options.index(b["status"]) if b["status"] in status_options else 0)
                    e_notes = st.text_area("Notes", value=b["notes"] or "")
                    s_col1, s_col2 = st.columns(2)
                    saved = s_col1.form_submit_button("Save")
                    cancelled = s_col2.form_submit_button("Cancel")

                if saved:
                    if not e_title.strip() or not e_author.strip():
                        st.error("Title and Author are required.")
                    else:
                        update_book(
                            book_id=b["id"],
                            title=e_title.strip(),
                            author=e_author.strip(),
                            year=int(e_year) if e_year else None,
                            rating=e_rating,
                            format=e_fmt,
                            status=e_status,
                            notes=e_notes.strip() or None,
                        )
                        st.session_state.editing_book = None
                        st.rerun()
                elif cancelled:
                    st.session_state.editing_book = None
                    st.rerun()


# ── Tab 2: My List ─────────────────────────────────────────────────────────────
with tab_list:
    with st.expander("Add a book", expanded=False):
        with st.form("add_list_form", clear_on_submit=True):
            l_col1, l_col2 = st.columns(2)
            with l_col1:
                l_title = st.text_input("Title *")
                l_author = st.text_input("Author *")
            with l_col2:
                l_year = st.number_input("Year", min_value=0, max_value=2100, value=None, step=1)
                l_notes = st.text_area("Notes")
            l_submitted = st.form_submit_button("Add to My List")

        if l_submitted:
            if not l_title.strip() or not l_author.strip():
                st.error("Title and Author are required.")
            else:
                add_to_reading_list(
                    title=l_title.strip(),
                    author=l_author.strip(),
                    year=int(l_year) if l_year else None,
                    notes=l_notes.strip() or None,
                )
                st.success(f"Added «{l_title}» to your list!")
                st.rerun()

    if "editing_list_item" not in st.session_state:
        st.session_state.editing_list_item = None
    if "moving_list_item" not in st.session_state:
        st.session_state.moving_list_item = None

    reading_list = get_reading_list()
    if not reading_list:
        st.info("Your reading list is empty. Add books above or push 'Add to My List' on a recommendation.")
    else:
        st.markdown(f"**{len(reading_list)} book{'s' if len(reading_list) != 1 else ''} on your list**")
        for item in reading_list:
            with st.container(border=True):
                year_str = f" ({item['year']})" if item["year"] else ""
                st.markdown(f"**{item['title']}**{year_str}  \n*{item['author']}*")
                if item["notes"]:
                    st.caption(item["notes"])

                b1, b2, b3 = st.columns(3)
                if b1.button("📚 Read", key=f"move_list_{item['id']}", use_container_width=True):
                    st.session_state.moving_list_item = item["id"]
                    st.session_state.editing_list_item = None
                    st.rerun()
                if b2.button("✏️ Edit", key=f"edit_list_{item['id']}", use_container_width=True):
                    st.session_state.editing_list_item = item["id"]
                    st.session_state.moving_list_item = None
                    st.rerun()
                if b3.button("🗑 Delete", key=f"del_list_{item['id']}", use_container_width=True):
                    delete_from_reading_list(item["id"])
                    if st.session_state.editing_list_item == item["id"]:
                        st.session_state.editing_list_item = None
                    if st.session_state.moving_list_item == item["id"]:
                        st.session_state.moving_list_item = None
                    st.rerun()

            if st.session_state.moving_list_item == item["id"]:
                with st.form(f"move_to_lib_form_{item['id']}"):
                    st.markdown(f"Moving **{item['title']}** to library — fill in the details:")
                    m_col1, m_col2 = st.columns(2)
                    with m_col1:
                        m_rating = st.slider("Rating", 1, 5, 3)
                        m_fmt = st.selectbox("Format", ["print", "ebook", "audio"])
                    with m_col2:
                        m_status = st.selectbox("Status", ["read", "want", "dnf"])
                        m_notes = st.text_area("Notes", value=item["notes"] or "", height=68)
                    mc1, mc2 = st.columns(2)
                    move_confirmed = mc1.form_submit_button("Read")
                    move_cancelled = mc2.form_submit_button("Cancel")

                if move_confirmed:
                    add_book(
                        title=item["title"],
                        author=item["author"],
                        year=item["year"],
                        rating=m_rating,
                        format=m_fmt,
                        status=m_status,
                        notes=m_notes.strip() or None,
                    )
                    delete_from_reading_list(item["id"])
                    st.session_state.moving_list_item = None
                    st.rerun()
                elif move_cancelled:
                    st.session_state.moving_list_item = None
                    st.rerun()

            if st.session_state.editing_list_item == item["id"]:
                with st.form(f"edit_list_form_{item['id']}"):
                    el_col1, el_col2 = st.columns(2)
                    with el_col1:
                        el_title = st.text_input("Title *", value=item["title"])
                        el_author = st.text_input("Author *", value=item["author"])
                    with el_col2:
                        el_year = st.number_input("Year", min_value=0, max_value=2100, value=item["year"] or None, step=1)
                        el_notes = st.text_area("Notes", value=item["notes"] or "")
                    el_c1, el_c2 = st.columns(2)
                    el_saved = el_c1.form_submit_button("Save")
                    el_cancelled = el_c2.form_submit_button("Cancel")

                if el_saved:
                    if not el_title.strip() or not el_author.strip():
                        st.error("Title and Author are required.")
                    else:
                        update_reading_list_item(
                            item_id=item["id"],
                            title=el_title.strip(),
                            author=el_author.strip(),
                            year=int(el_year) if el_year else None,
                            notes=el_notes.strip() or None,
                        )
                        st.session_state.editing_list_item = None
                        st.rerun()
                elif el_cancelled:
                    st.session_state.editing_list_item = None
                    st.rerun()


# ── Tab 3: Recommend ───────────────────────────────────────────────────────────
with tab_recommend:
    if "recs" not in st.session_state:
        st.session_state.recs = None
    if "adding_rec" not in st.session_state:
        st.session_state.adding_rec = None
    if "added_recs" not in st.session_state:
        st.session_state.added_recs = set()
    if "added_to_list_recs" not in st.session_state:
        st.session_state.added_to_list_recs = set()

    books = get_books()
    is_empty = len(books) == 0

    mood = st.text_area(
        "What are you in the mood for? (optional)",
        placeholder="e.g. something dark and philosophical, or a page-turner set in space…",
        height=80,
    )

    if is_empty:
        st.warning("Add some books to your library first so Claude can tailor recommendations.")

    get_btn = st.button("Recommend", disabled=is_empty)
    regen_btn = st.button("↺", disabled=is_empty or not st.session_state.recs)

    if get_btn or regen_btn:
        st.session_state.added_recs = set()
        st.session_state.added_to_list_recs = set()
        st.session_state.adding_rec = None
        with st.spinner("Asking Claude for recommendations…"):
            try:
                raw = get_recommendations(books, mood)
                parsed = parse_recommendations(raw)
                # Fallback to raw markdown if parsing fails
                st.session_state.recs = parsed or [{"title": None, "author": None, "year": None, "md": raw}]
            except anthropic.AuthenticationError:
                st.error("Invalid API key. Check your ANTHROPIC_API_KEY in .env.")
            except Exception as exc:
                st.error(f"Something went wrong: {exc}")

    if st.session_state.recs:
        st.markdown("---")
        for i, rec in enumerate(st.session_state.recs):
            st.markdown(rec["md"])

            if rec["title"] is None:
                # Raw fallback — no add buttons
                pass
            else:
                rb1, rb2 = st.columns(2)
                with rb1:
                    if i in st.session_state.added_recs:
                        st.success("Library ✓")
                    elif st.session_state.adding_rec != i:
                        if st.button("+ Add to Library", key=f"add_rec_btn_{i}", use_container_width=True):
                            st.session_state.adding_rec = i
                            st.rerun()
                with rb2:
                    if i in st.session_state.added_to_list_recs:
                        st.success("My List ✓")
                    else:
                        if st.button("+ Add to My List", key=f"add_list_btn_{i}", use_container_width=True):
                            add_to_reading_list(title=rec["title"], author=rec["author"], year=rec["year"])
                            st.session_state.added_to_list_recs.add(i)
                            st.rerun()

                if st.session_state.adding_rec == i:
                    with st.form(f"add_rec_form_{i}"):
                        st.markdown(f"**{rec['title']}** by *{rec['author']}*")
                        r_col1, r_col2 = st.columns(2)
                        with r_col1:
                            r_rating = st.slider("Rating", 1, 5, 3)
                            r_fmt = st.selectbox("Format", ["print", "ebook", "audio"])
                        with r_col2:
                            r_status = st.selectbox("Status", ["read", "want", "dnf"])
                            r_notes = st.text_area("Notes", height=68)
                        b_col1, b_col2 = st.columns(2)
                        confirmed = b_col1.form_submit_button("Add to Library")
                        cancelled = b_col2.form_submit_button("Cancel")

                    if confirmed:
                        add_book(
                            title=rec["title"],
                            author=rec["author"],
                            year=rec["year"],
                            rating=r_rating,
                            format=r_fmt,
                            status=r_status,
                            notes=r_notes.strip() or None,
                        )
                        st.session_state.added_recs.add(i)
                        st.session_state.adding_rec = None
                        st.rerun()
                    elif cancelled:
                        st.session_state.adding_rec = None
                        st.rerun()

            st.divider()
