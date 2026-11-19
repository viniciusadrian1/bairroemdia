import streamlit as st

from frontend.providers import api
from frontend.ui.components import heading, show_guidance


def render():
    heading("Agente do bairro", "Uma conversa para entender o próximo passo, com fontes para você conferir.")
    st.write("Você pode perguntar como registrar um problema, revisar a análise ou acompanhar um protocolo. As respostas consultam a base documental; o agente não registra nem aprova ocorrências por você.")
    st.caption("O assistente pode se abster quando faltam documentos. Não é um canal de emergência, fiscalização ou assessoria individual.")
    if st.button("Limpar conversa desta sessão"):
        st.session_state.chat_history = []
        st.rerun()
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                show_guidance(message.get("result", {"answer": message["content"]}))
            else:
                st.write(message["content"])
    question = st.chat_input("Digite sua dúvida, sem dados pessoais", max_chars=1000)
    if question:
        if len(question.strip()) < 3:
            st.error("Escreva uma pergunta com pelo menos 3 caracteres.")
            return
        history = [{"role": m["role"], "content": m["content"][:3000]} for m in st.session_state.chat_history[-10:]]
        try:
            with st.spinner("Consultando a base documental..."):
                result = api.post("/assistant", {"question": question.strip(), "history": history})
            if not isinstance(result, dict) or not isinstance(result.get("answer"), str) or not result["answer"].strip():
                raise api.APIError("A orientação recebida está vazia ou incompleta. Reformule a pergunta ou tente novamente.")
            st.session_state.chat_history.extend([
                {"role": "user", "content": question.strip()},
                {"role": "assistant", "content": result["answer"], "result": result},
            ])
            st.rerun()
        except api.APIError as error:
            st.error(str(error))
            st.caption("A pergunta não foi adicionada ao histórico. Você pode enviá-la novamente.")
