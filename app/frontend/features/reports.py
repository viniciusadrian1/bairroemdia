import streamlit as st

from frontend.providers import api
from frontend.state.session import load_reports, remember_report
from frontend.ui.components import CATEGORIES, STATUSES, heading, show_report


def render():
    heading("Acompanhar e revisar", "A análise é uma sugestão. A criação do protocolo exige sua revisão.")
    st.caption("Ambiente compartilhado de demonstração: os registros são sintéticos ou públicos; não há contas individuais.")
    try:
        reports = load_reports(force=st.button("Atualizar relatos"))
    except api.APIError as error:
        st.error(str(error))
        return
    if not reports:
        st.info("Ainda não há relatos. Comece em Registrar ocorrência.")
        return
    ids = [r["id"] for r in reports]
    lookup = {r["id"]: r for r in reports}
    selected = st.session_state.selected_report_id
    report_id = st.selectbox("Escolha um relato", ids, index=ids.index(selected) if selected in ids else 0,
                            format_func=lambda k: f"{lookup[k].get('neighborhood', '')} · {STATUSES.get(lookup[k]['status'], lookup[k]['status'])} · {k[:8]}")
    report = lookup[report_id]
    show_report(report)
    if report["status"] == "pending_review":
        with st.form("review_" + report_id):
            st.write("**Sua revisão**")
            category_options = list(CATEGORIES) if report.get("vision") is not None else ["sound"]
            current_category = report.get("category", "sound")
            category = st.selectbox("Confirme ou corrija a categoria", category_options,
                                    index=category_options.index(current_category) if current_category in category_options else 0,
                                    format_func=CATEGORIES.get)
            if report.get("vision") is None:
                st.caption("Para registrar pavimentação, crie uma nova ocorrência com foto.")
            note = st.text_area("Observação da revisão (opcional)", max_chars=500)
            decision = st.radio("Decisão", ["Aprovar para protocolo interno", "Não aprovar"])
            reviewed = st.checkbox("Li a análise, conferi a localização e revisei os dados")
            submit = st.form_submit_button("Salvar minha revisão", type="primary")
        if submit:
            if not reviewed:
                st.error("Confirme que revisou o relato antes de continuar.")
            else:
                try:
                    with st.spinner("Salvando sua revisão..."):
                        result = api.post(api.report_path(report_id, "review"), {"approved": decision == "Aprovar para protocolo interno", "corrected_category": category, "note": note})
                    remember_report(result)
                    st.rerun()
                except api.APIError as error:
                    st.error(str(error))
    elif report["status"] == "approved":
        st.info("Revisão aprovada. O próximo botão cria somente um protocolo interno de demonstração.")
        if st.button("Criar protocolo interno", type="primary"):
            try:
                with st.spinner("Criando protocolo interno..."):
                    result = api.post(api.report_path(report_id, "protocol"))
                remember_report(result)
                st.rerun()
            except api.APIError as error:
                st.error(str(error))
    elif report["status"] == "rejected":
        st.info("Este relato não foi aprovado. Nenhum protocolo será criado.")
    else:
        st.success("Acompanhe acima a situação do protocolo interno. O atendimento exibido é simulado.")
