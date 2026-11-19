"""Local brand assets and presentation, independent of API and user data."""
import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "brand"
COLORS = {"primary": "#BE422F", "background": "#FFF5E6", "text": "#352522",
          "peach": "#F2B293", "sage": "#CBD5B7"}
CHART_COLORS = [COLORS["primary"], COLORS["text"], "#566349", "#87524C", COLORS["peach"], COLORS["sage"]]


@lru_cache(maxsize=12)
def asset_uri(filename, mime="image/svg+xml"):
    """Only fixed filenames from our bundled brand assets are passed here."""
    encoded = base64.b64encode((ASSETS / filename).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def stylesheet():
    css = (Path(__file__).with_name("brand.css")).read_text(encoding="utf-8")
    # Inline local WOFF2 assets: works offline and from any Streamlit working dir.
    return css.replace("__BODY_FONT__", asset_uri("bricolage.woff2", "font/woff2")).replace(
        "__DISPLAY_FONT__", asset_uri("fraunces.woff2", "font/woff2"))


def apply_theme():
    st.markdown(f"<style>{stylesheet()}</style>", unsafe_allow_html=True)


def _enter():
    st.session_state.brand_entered = True


def show_welcome():
    """A real entry screen, once per session; no artificial loading timer."""
    st.markdown(f"""
<section class="bed-welcome" aria-label="Bem-vindo ao Bairro em Dia">
  <div class="bed-welcome-copy">
    <p class="bed-eyebrow">CUIDADO QUE COMEÇA PERTO.</p>
    <img class="bed-welcome-logo" src="{asset_uri('nome-creme.svg')}" alt="Bairro em Dia">
    <h1>Seu bairro tem voz.</h1>
    <p>Conte o que precisa de atenção e acompanhe cada etapa do seu relato.</p>
  </div>
  <div class="bed-welcome-art" aria-hidden="true">
    <img src="{asset_uri('simbolo-terracota.svg')}" alt="">
  </div>
</section>
""", unsafe_allow_html=True)
    st.button("Entrar no bairro", type="primary", use_container_width=True,
              on_click=_enter, key="brand_enter")
    st.markdown("""
<div class="bed-steps" aria-label="Como funciona">
  <div><span>01</span><strong>Registre</strong><p>Conte o que aconteceu no bairro.</p></div>
  <div><span>02</span><strong>Confira</strong><p>Revise a análise e confirme os dados.</p></div>
  <div><span>03</span><strong>Acompanhe</strong><p>Veja a situação do protocolo interno.</p></div>
</div>
""", unsafe_allow_html=True)
    st.caption("Protótipo educacional · FIAP · 2TIAPF. Use apenas dados públicos ou sintéticos. "
               "Nenhum relato é enviado a autoridades.")


def show_header():
    st.markdown(f"""
<section class="bed-page-heading" aria-label="Bairro em Dia">
  <div><p class="bed-eyebrow">CUIDADO QUE COMEÇA PERTO.</p>
  <h1>Seu bairro tem voz.</h1>
  <p>Registre. Confira. Acompanhe.</p></div>
  <img src="{asset_uri('simbolo-terracota.svg')}" alt="" aria-hidden="true">
</section>
""", unsafe_allow_html=True)


def show_sidebar_logo():
    # st.logo renders the wordmark in the expanded menu and the icon when collapsed.
    st.caption("Cuidado com o bairro, com você no controle.")


def style_chart(figure):
    figure.update_layout(paper_bgcolor=COLORS["background"], plot_bgcolor=COLORS["background"],
                         font={"family": "Bricolage Grotesque, sans-serif", "color": COLORS["text"], "size": 14},
                         title_font={"family": "Fraunces, Georgia, serif", "size": 24},
                         margin={"l": 20, "r": 20, "t": 70, "b": 30})
    figure.update_yaxes(gridcolor="#DFCEC1")
    return figure
