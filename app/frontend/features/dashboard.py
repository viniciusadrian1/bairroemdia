import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.providers import api
from frontend.state.session import load_reports, remember_report
from frontend.ui.components import CATEGORIES, STATUSES, heading, status_card
from frontend.ui.brand import CHART_COLORS, style_chart


def filter_reports(reports, categories, statuses):
    return [r for r in reports if r.get("category") in categories and r.get("status") in statuses]


def render():
    heading("Painel do gestor", "Demonstração de acompanhamento, sem conexão com prefeitura ou concessionária.")
    st.warning("Gestor simulado: as ações abaixo alteram apenas o ambiente educacional. Não há autenticação de produção.")
    try:
        reports = load_reports(force=st.button("Atualizar painel"))
    except api.APIError as error:
        st.error(str(error))
        return
    if not reports:
        st.info("O painel será preenchido com os relatos registrados na aplicação.")
        return
    cols = st.columns(2)
    categories = cols[0].multiselect("Filtrar por tipo", list(CATEGORIES), default=list(CATEGORIES), format_func=CATEGORIES.get)
    statuses = cols[1].multiselect("Filtrar por situação", list(STATUSES), default=list(STATUSES), format_func=STATUSES.get)
    filtered = filter_reports(reports, categories, statuses)
    cols = st.columns(3)
    with cols[0]:
        status_card("Relatos na seleção", len(filtered))
    with cols[1]:
        status_card("Aguardando revisão", sum(r["status"] == "pending_review" for r in filtered))
    with cols[2]:
        status_card("Com protocolo interno", sum(bool(r.get("protocol")) for r in filtered))
    if not filtered:
        st.info("Nenhum relato corresponde aos filtros escolhidos.")
    else:
        frame = pd.DataFrame([{"Bairro": r.get("neighborhood", "Não informado"),
                               "Situação": STATUSES.get(r["status"], r["status"]),
                               "Tipo": CATEGORIES.get(r["category"], r["category"]), "Relatos": 1} for r in filtered])
        grouped = frame.groupby(["Bairro", "Situação", "Tipo"], as_index=False)["Relatos"].sum()
        figure = px.bar(grouped, x="Bairro", y="Relatos", color="Situação", pattern_shape="Tipo",
                        barmode="stack", title="Relatos por bairro e situação", template="plotly_white",
                        hover_data=["Tipo"], color_discrete_map=dict(zip(STATUSES.values(), CHART_COLORS)))
        figure.update_layout(legend_title_text="Situação", dragmode="zoom", yaxis_dtick=1)
        style_chart(figure)
        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False, "scrollZoom": True})
        st.caption("Passe sobre as barras para detalhes. Arraste para ampliar; dê dois cliques para restaurar.")
        st.dataframe(frame.drop(columns=["Relatos"]), use_container_width=True, hide_index=True)
    actionable = [r for r in filtered if r["status"] in {"protocolled", "in_progress"}]
    if actionable:
        heading("Simular atendimento", "A mudança fica registrada na API e pode ser conferida na tela do cidadão.")
        options = {r["id"]: r for r in actionable}
        selected = st.selectbox("Protocolo para atualizar", list(options), format_func=lambda k: str(options[k].get("protocol") or k))
        next_statuses = ["in_progress"] if options[selected]["status"] == "protocolled" else ["resolved"]
        status = st.selectbox("Nova situação", next_statuses, format_func=STATUSES.get)
        if st.button("Salvar situação simulada"):
            try:
                with st.spinner("Atualizando o acompanhamento..."):
                    result = api.post(api.report_path(selected, "status"), {"status": status})
                remember_report(result)
                st.rerun()
            except api.APIError as error:
                st.error(str(error))
