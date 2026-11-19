import hashlib
import json
from uuid import uuid4

import streamlit as st


def request_id_for(payload, state=None):
    """Keep retry identity until the actual submitted content changes."""
    state = st.session_state if state is None else state
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=False).encode("utf-8")).hexdigest()
    attempt = state.get("report_attempt", {})
    if attempt.get("fingerprint") != fingerprint:
        attempt = {"fingerprint": fingerprint, "client_request_id": str(uuid4())}
        state["report_attempt"] = attempt
    return attempt["client_request_id"]


def reset_report_form(state=None):
    state = st.session_state if state is None else state
    state.pop("report_attempt", None)
    state.pop("last_created", None)
    state.pop("draft_sound_event", None)
    state["report_form_version"] = state.get("report_form_version", 0) + 1


def start_sound_report(event):
    """An explicit action starts a draft; it never submits a report automatically."""
    reset_report_form()
    st.session_state.draft_sound_event = event
    st.session_state.page = "Registrar ocorrência"


def open_report(report_id):
    st.session_state.selected_report_id = report_id
    st.session_state.page = "Acompanhar e revisar"


def initialize():
    defaults = {"reports": [], "reports_loaded": False, "chat_history": [],
                "interactions": [], "selected_report_id": None, "report_photos": {}}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def remember_report(report):
    reports = st.session_state.reports
    st.session_state.reports = [report] + [r for r in reports if r["id"] != report["id"]]
    st.session_state.selected_report_id = report["id"]
    if st.session_state.get("last_created", {}).get("id") == report["id"]:
        st.session_state.last_created = report
    st.session_state.interactions.append({"id": report["id"], "status": report["status"]})


def load_reports(force=False):
    from frontend.providers import api
    if force or not st.session_state.reports_loaded:
        reports = api.get("/reports")
        if not isinstance(reports, list) or any(not isinstance(r, dict) or "id" not in r or "status" not in r for r in reports):
            raise api.APIError("A lista recebida está incompleta. Tente atualizar novamente.")
        st.session_state.reports = reports
        st.session_state.reports_loaded = True
    return st.session_state.reports
