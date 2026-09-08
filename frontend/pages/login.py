"""Login and registration page."""
from __future__ import annotations

import streamlit as st

from api_client import ApiError, backend_status
from state import client, sign_in


def render() -> None:
    """Render the sign-in screen."""
    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.markdown(
            "<h1 style='text-align:center;margin-bottom:0'>🏢 AI HR Assistant</h1>"
            "<p style='text-align:center;color:#6b7280;margin-top:4px'>"
            "Ask HR questions. Get answers from company policy documents.</p>",
            unsafe_allow_html=True,
        )
        st.write("")

        online, health = backend_status(client())
        if not online:
            st.error(
                "Backend is not reachable. Start it first:\n\n"
                "`uvicorn backend.main:app --reload`"
            )

        sign_in_tab, register_tab = st.tabs(["Sign in", "Create account"])

        with sign_in_tab:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="employee@acme.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")

            if submitted:
                if not email or not password:
                    st.error("Enter both email and password.")
                else:
                    try:
                        result = client().login(email.strip(), password)
                        sign_in(result["access_token"], result["user"])
                        st.rerun()
                    except ApiError as exc:
                        st.error(str(exc))

            with st.expander("Demo accounts"):
                st.markdown(
                    "| Role | Email | Password |\n"
                    "| --- | --- | --- |\n"
                    "| HR Admin | `admin@acme.com` | `Admin@123` |\n"
                    "| Employee | `employee@acme.com` | `Employee@123` |"
                )

        with register_tab:
            with st.form("register_form"):
                name = st.text_input("Full name")
                new_email = st.text_input("Work email")
                new_password = st.text_input(
                    "Password", type="password", help="At least 8 characters"
                )
                created = st.form_submit_button("Create account", use_container_width=True)

            if created:
                if not all([name, new_email, new_password]):
                    st.error("All fields are required.")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        result = client().register(name.strip(), new_email.strip(), new_password)
                        sign_in(result["access_token"], result["user"])
                        st.rerun()
                    except ApiError as exc:
                        st.error(str(exc))

        if online and health:
            st.caption(
                f"Backend online · {health.get('indexed_chunks', 0)} indexed chunks · "
                f"answer mode: {health.get('llm_mode', 'n/a')}"
            )


render()
