import streamlit as st
import hashlib
import os
from datetime import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

class AdminMongo():
    def __init__(self):
        self.PEPPER = get_secret("/visualize/PW_PEPPER", "")

    def hash_password(self, pw: str) -> str:
        # For production use bcrypt/argon2 with per-user salts.
        return hashlib.sha256((pw + self.PEPPER).encode("utf-8")).hexdigest()

    def create_user(self, db, username: str, password: str):
        username = username.strip()
        if not username or not password:
            return False, "Username and password are required."
        try:
            db.users.insert_one({
                "username": username,
                "password_hash": self.hash_password(password),
                "created_at": datetime.utcnow(),
            })
            return True, "Account created. Please log in."
        except Exception as e:
            if "duplicate key error" in str(e).lower():
                return False, "Username already taken."
            return False, f"Error creating user: {e}"

    def verify_user(self, db, username: str, password: str):
        doc = db.users.find_one({"username": username.strip()})
        if not doc:
            return None
        return doc["_id"] if doc.get("password_hash") == self.hash_password(password) else None

    def add_note(self, db, user_id: ObjectId, content: str):
        if content and content.strip():
            db.notes.insert_one({
                "user_id": user_id,
                "content": content.strip(),
                "created_at": datetime.utcnow(),
            })

    def get_notes(self, db, user_id: ObjectId):
        return list(db.notes.find({"user_id": user_id}).sort("created_at", DESCENDING))

    def delete_note(self, db, user_id: ObjectId, note_id: str):
        db.notes.delete_one({"_id": ObjectId(note_id), "user_id": user_id})

    def notes_app(self, db):
        user = st.session_state.user
        st.header(f"👋 Hello, {user['username']}!")
        st.caption("Each user sees and persists their **own** data in MongoDB.")

        with st.form("add_note_form", clear_on_submit=True):
            prefix = st.session_state.get("cfg_prefix", "") or ""
            content = st.text_area("Add a note:", height=100, placeholder="Hello world…")
            if st.form_submit_button("Save"):
                self.add_note(db, user["_id"], f"{prefix}{content}")
                st.success("Saved!")
                st.rerun()

        st.subheader("Your saved notes")
        notes = self.get_notes(db, user["_id"])
        if not notes:
            st.info("No notes yet. Add one above!")
        else:
            for n in notes:
                with st.container(border=True):
                    st.markdown(f"**{n['_id']}** · _{n['created_at'].isoformat()}_")
                    st.write(n["content"])
                    cols = st.columns([1, 6])
                    with cols[0]:
                        if st.button("Delete", key=f"del_{n['_id']}"):
                            self.delete_note(db, user["_id"], str(n["_id"]))
                            st.toast("Deleted")
                            st.rerun()

    def sidebar_admin_panel(self, db):
        db.users.create_index([("username", ASCENDING)], unique=True)
        db.notes.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        with st.sidebar:
            # 🔐 Account panel (everything auth-related lives inside this expander)
            with st.expander("🔐 Account", expanded=True):
                # If already authenticated, hide login inputs and only show status + logout
                if st.session_state.get("user", {}).get("authenticated"):
                    st.caption(f"Signed in as **{st.session_state.user['username']}**")
                    if st.button("Log out", type="secondary", use_container_width=True):
                        st.session_state.pop("user", None)
                        st.rerun()
                else:
                    if "auth_mode" not in st.session_state:
                        st.session_state.auth_mode = "Log in"

                    # One shared set of inputs for both actions
                    username = st.text_input("Username", key="auth_user")
                    password = st.text_input("Password", type="password", key="auth_pass")

                    st.session_state.auth_mode = st.radio(
                        "Action", ["Log in", "Sign up"], horizontal=True, key="auth_mode_radio"
                    )
                    primary_label = "Log in" if st.session_state.auth_mode == "Log in" else "Sign up"

                    if st.button(primary_label, use_container_width=True):
                        if st.session_state.auth_mode == "Log in":
                            uid = self.verify_user(db, username, password)
                            if uid:
                                st.session_state.user = {"_id": uid, "username": username.strip(), "authenticated": True}
                                st.success(f"Welcome, {username}!")
                                st.rerun()
                            else:
                                st.error("Invalid username or password.")
                        else:
                            ok, msg = self.create_user(db, username, password)
                            st.success(msg) if ok else st.error(msg)
                                            
