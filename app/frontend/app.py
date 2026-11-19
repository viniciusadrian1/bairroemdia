"""Run from app/: python -m streamlit run frontend/app.py"""
import sys
from pathlib import Path

# Streamlit runs this file as a script; keep imports stable from any working directory.
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streamlit as st

from frontend.features import assistant, dashboard, home, integrations, register, reports, vision_sequence
from frontend.providers import api
from frontend.state.session import initialize
from frontend.ui import brand
from frontend.ui.components import mode_label

st.set_page_config(page_title="Bairro em Dia", page_icon=str(brand.ASSETS / "favicon.png"),
                   layout="wide", initial_sidebar_state="auto")
initialize()
brand.apply_theme()
if not st.session_state.get("brand_entered", False):
    brand.show_welcome()
    st.stop()

st.logo(str(brand.ASSETS / "nome-linear.svg"), size="large",
        icon_image=str(brand.ASSETS / "app-icon.png"))
with st.sidebar:
    brand.show_sidebar_logo()
    page = st.radio("O que você quer fazer?", ["Início", "Registrar ocorrência", "Acompanhar e revisar", "Agente do bairro", "Acessibilidade sonora", "Painel do gestor", "Sequência de imagens", "Projeto e transparência"], key="page")
    st.divider()
    st.caption("Protótipo educacional · FIAP · 2TIAPF")
    st.caption("Nenhuma informação é enviada a autoridades. Use apenas dados públicos ou sintéticos.")
    try:
        status = api.health(api.base_url())
        st.success("Serviço conectado")
        with st.expander("Recursos disponíveis"):
            st.caption("Orientação: " + mode_label(status.get("llm_mode")))
            st.caption("Imagem: " + mode_label(status.get("vision_mode")))
    except api.APIError:
        st.warning("Serviço indisponível. Você pode preparar o formulário e tentar novamente.")
    if st.button("Verificar conexão"):
        api.health.clear()
        st.rerun()

brand.show_header()
{"Início": home.render, "Registrar ocorrência": register.render, "Acompanhar e revisar": reports.render,
 "Agente do bairro": assistant.render, "Painel do gestor": dashboard.render,
 "Acessibilidade sonora": integrations.render_sound, "Projeto e transparência": integrations.render,
 "Sequência de imagens": vision_sequence.render}[page]()
