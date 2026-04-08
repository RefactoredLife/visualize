import streamlit as st
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from common.config import get_secret
from sqlalchemy import text


class AdminMariaDB:
    def __init__(self):
        self.PEPPER = get_secret("/visualize/PW_PEPPER")

    def hash_password(self, pw: str) -> str:
        # For production use bcrypt/argon2 with per-user salts.
        return hashlib.sha256((pw + self.PEPPER).encode("utf-8")).hexdigest()

    # --- Schema helpers ---
    def _ensure_schema(self, engine) -> None:
        with engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password_hash CHAR(64) NOT NULL,
                    created_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            ))
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    INDEX idx_notes_user_created (user_id, created_at),
                    CONSTRAINT fk_notes_user FOREIGN KEY (user_id) REFERENCES users(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            ))

    # --- Data access ---
    def create_user(self, engine, username: str, password: str):
        username = (username or "").strip()
        if not username or not password:
            return False, "Username and password are required."
        self._ensure_schema(engine)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO users (username, password_hash, created_at) VALUES (:u, :p, :ts)"),
                    {"u": username, "p": self.hash_password(password), "ts": datetime.utcnow()},
                )
            return True, "Account created. Please log in."
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg:
                return False, "Username already taken."
            return False, f"Error creating user: {e}"

    def verify_user(self, engine, username: str, password: str) -> Optional[int]:
        self._ensure_schema(engine)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, password_hash FROM users WHERE username = :u"),
                {"u": (username or "").strip()},
            ).mappings().first()
        if not row:
            return None
        return int(row["id"]) if row["password_hash"] == self.hash_password(password) else None

    def add_note(self, engine, user_id: int, content: str) -> None:
        if not content or not content.strip():
            return
        self._ensure_schema(engine)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO notes (user_id, content, created_at) VALUES (:uid, :c, :ts)"),
                {"uid": int(user_id), "c": content.strip(), "ts": datetime.utcnow()},
            )

    def get_notes(self, engine, user_id: int) -> List[Dict[str, Any]]:
        self._ensure_schema(engine)
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, content, created_at FROM notes WHERE user_id = :uid ORDER BY created_at DESC"),
                {"uid": int(user_id)},
            ).mappings().all()
        # Mirror Mongo shape: use "_id"
        return [{"_id": r["id"], "content": r["content"], "created_at": r["created_at"]} for r in rows]

    def delete_note(self, engine, user_id: int, note_id: str) -> None:
        self._ensure_schema(engine)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM notes WHERE id = :nid AND user_id = :uid"),
                {"nid": int(note_id), "uid": int(user_id)},
            )

    # --- UI ---
    def notes_app(self, engine):
        user = st.session_state.user
        st.header(f"👋 Hello, {user['username']}!")
        st.caption("Each user sees and persists their own data in MariaDB.")

        with st.form("add_note_form", clear_on_submit=True):
            prefix = st.session_state.get("cfg_prefix", "") or ""
            content = st.text_area("Add a note:", height=100, placeholder="Hello world…")
            if st.form_submit_button("Save"):
                self.add_note(engine, user["_id"], f"{prefix}{content}")
                st.success("Saved!")
                st.rerun()

        st.subheader("Your saved notes")
        notes = self.get_notes(engine, user["_id"])
        if not notes:
            st.info("No notes yet. Add one above!")
        else:
            for n in notes:
                with st.container(border=True):
                    # created_at is a datetime; format ISO for consistency
                    ts = n["created_at"].isoformat() if hasattr(n["created_at"], "isoformat") else str(n["created_at"])
                    st.markdown(f"**{n['_id']}** · _{ts}_")
                    st.write(n["content"])
                    cols = st.columns([1, 6])
                    with cols[0]:
                        if st.button("Delete", key=f"del_{n['_id']}"):
                            self.delete_note(engine, user["_id"], str(n["_id"]))
                            st.toast("Deleted")
                            st.rerun()

    def sidebar_admin_panel(self, engine):
        # Ensure schema and indexes exist
        self._ensure_schema(engine)
        with st.sidebar:
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

                    username = st.text_input("Username", key="auth_user")
                    password = st.text_input("Password", type="password", key="auth_pass")

                    st.session_state.auth_mode = st.radio(
                        "Action", ["Log in", "Sign up"], horizontal=True, key="auth_mode_radio"
                    )
                    primary_label = "Log in" if st.session_state.auth_mode == "Log in" else "Sign up"

                    if st.button(primary_label, use_container_width=True):
                        if st.session_state.auth_mode == "Log in":
                            uid = self.verify_user(engine, username, password)
                            if uid is not None:
                                st.session_state.user = {"_id": int(uid), "username": (username or "").strip(), "authenticated": True}
                                st.success(f"Welcome, {username}!")
                                st.rerun()
                            else:
                                st.error("Invalid username or password.")
                        else:
                            ok, msg = self.create_user(engine, username, password)
                            st.success(msg) if ok else st.error(msg)