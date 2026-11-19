import streamlit as st


def go_to(page):
    st.session_state.page = page


def render():
    st.subheader("Do que aconteceu ao que fazer agora")
    st.write("Registre um problema na pavimentação ou um relato sonoro, confira a análise e acompanhe cada etapa em um só lugar.")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Registrar")
        st.write("Informe o local e o contexto. Para pavimentação, inclua uma foto e confira as sugestões do detector.")
        st.button("Registrar ocorrência", type="primary", use_container_width=True, on_click=go_to, args=("Registrar ocorrência",))
    with right, st.container(border=True):
        st.subheader("Acompanhar")
        st.write("Confira a análise, revise os dados e acompanhe o protocolo interno.")
        st.button("Acompanhar relatos", use_container_width=True, on_click=go_to, args=("Acompanhar e revisar",))
    with st.container(border=True):
        st.subheader("Sons que merecem atenção")
        st.write("Identifique um som e, se fizer sentido, use a análise para registrar o que aconteceu. O resultado acompanha o relato até a revisão.")
        st.button("Abrir acessibilidade sonora", use_container_width=True, on_click=go_to, args=("Acessibilidade sonora",))
    with st.container(border=True):
        st.subheader("Precisa de uma orientação?")
        st.write("O Agente do bairro ajuda você a entender como registrar e acompanhar um problema, com fontes para conferir.")
        st.button("Conversar com o agente", use_container_width=True,
                  on_click=go_to, args=("Agente do bairro",))
    st.caption("Nesta versão, o registro aceita pavimentação e relatos sonoros. Outras categorias de problemas do bairro fazem parte da evolução planejada.")
