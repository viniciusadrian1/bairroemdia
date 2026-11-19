import streamlit as st

from frontend.providers import api
from frontend.ui.components import heading, status_card, mode_label

MODULES = {
    "front-end-mobile": ("Desenvolvimento web e móvel", "Toda a aplicação", "Navegação, formulário, conversa, revisão e painel responsivos."),
    "generative-ai": ("IA generativa", "Agente do bairro", "Respostas com consulta à base documental e fontes; geração depende do modelo local disponível."),
    "nlp-chatbots-virtual-agents": ("Linguagem natural e agentes virtuais", "Agente do bairro → Conferir fontes", "Preparação dos documentos, anonimização, trechos e conjuntos de avaliação alimentam a consulta."),
    "visao-computacional": ("Visão computacional", "Registrar → Revisar / Sequência de imagens", "Detector de pavimentação, caixas para revisão e comparação de quadros; não classifica todos os problemas urbanos."),
    "ai-rpa": ("Automação de processos com IA", "Acompanhar e revisar → Criar protocolo", "Após aprovação humana, cria um protocolo interno sem duplicar a operação. Não envia a órgãos públicos."),
    "iot": ("Computação física e IoT", "Acessibilidade sonora", "Grava ou recebe WAV para análise YAMNet no servidor e preserva importação de eventos. Inferência no celular pelo Edge Impulse exige evidência própria."),
    "cluster-computing": ("Cluster e supercomputação", "Projeto e transparência → Cluster", "Estudo acadêmico entregue separadamente; seus arquivos não estão neste repositório de código."),
    "computacao-quantica": ("Computação quântica e IA", "Projeto e transparência → Quântica", "Estudo acadêmico entregue separadamente. Não há execução nem vantagem quântica demonstrada na aplicação."),
    "governanca-ia-business-analytics": ("Governança em IA e análise de negócios", "Revisão + Painel do gestor + Transparência", "Integra o fluxo, a supervisão humana, os indicadores e as evidências. Relatório e vídeo são entregas próprias."),
}


def show_integration_data(module):
    data = module.get("data")
    if module.get("data_error"):
        st.warning(str(module["data_error"]))
    if not isinstance(data, dict):
        return
    st.write("**Dados da evidência integrada**")
    if module.get("data_path"):
        st.caption("Arquivo de origem: " + str(module["data_path"]))
    discipline = module.get("discipline")
    if discipline == "cluster-computing":
        st.warning("Simulação iSPD com carga sintética. Estes tempos não são latência da aplicação, capacidade de produção ou desempenho de um cluster físico.")
        rows = [{"Nós de processamento": s.get("workers"), "Tempo total simulado (s)": s.get("total_simulated_time_s"),
                 "Tarefas concluídas": s.get("tasks_completed"), "Tarefas por nó": s.get("tasks_per_worker")}
                for s in data.get("scenarios", [])]
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        derived = data.get("derived", {})
        reduction = derived.get("reduction_percent")
        ratio = derived.get("ratio_t2_t4")
        if isinstance(reduction, (float, int)) and isinstance(ratio, (float, int)):
            st.caption(f"Redução no cenário simulado: {reduction:.2f}% · Razão T₂/T₄: {ratio:.3f}")
    elif discipline == "computacao-quantica":
        st.warning("Estudo de evolução: não houve execução quântica nem demonstração de ganho quântico. Medições clássicas e simulações têm escopos distintos.")
        benchmark = data.get("vision_benchmark", {})
        if benchmark:
            st.caption(f"Detector clássico: {benchmark.get('measured_calls', 'não informado')} chamadas medidas em {benchmark.get('measured_runs', 'não informado')} execuções controladas.")
        st.dataframe([
            {"Etapa": "Hoje", "Escopo": "Medições locais do detector clássico e estudo de filas; limites no arquivo de evidência."},
            {"Etapa": "Antes de uma proposta quântica", "Escopo": "Validar carga representativa e melhorias clássicas; confirmar problema residual de alocação."},
            {"Etapa": "Futuro condicionado", "Escopo": "Avaliar otimização quântica somente se persistir gargalo pertinente e houver comparação justa com alternativas clássicas."},
        ], hide_index=True, use_container_width=True)
        if data.get("pending"):
            st.write("Pendências do estudo:")
            for item in data["pending"]:
                st.write("• " + str(item))
    elif discipline == "nlp-chatbots-virtual-agents":
        stats = data.get("estatisticas", {})
        st.dataframe([{"Corpus": name, "Exemplos": item.get("exemplos"),
                       "Recusas/encaminhamentos": item.get("recusas_encaminhamentos"),
                       "Média de tokens do registro com metadados": item.get("media_tokens_registro_com_metadados")}
                      for name, item in stats.items()], hide_index=True, use_container_width=True)
        st.caption(f"Fontes: {data.get('paginas_pdf', 'não informado')} páginas PDF · {data.get('palavras_extraidas_total', 'não informado')} palavras extraídas.")
        st.warning("Contagens e verificações automáticas não substituem revisão humana, fidelidade das respostas ou avaliação completa de anonimização.")
        review = data.get("revisao_humana", {})
        st.caption(f"Revisão humana: {review.get('status', 'não informada')} · Registros revisados: {review.get('realizada', 'não informado')}")
    st.caption("Dados originais da evidência (campos técnicos preservados):")
    st.json(data, expanded=False)


def render():
    heading("Projeto e transparência", "Entenda como as nove matérias participam da solução.")
    st.caption("Ter uma área no aplicativo não comprova a conclusão da disciplina. As evidências e pendências abaixo delimitam o que foi realizado.")
    with st.expander("Onde está cada matéria?", expanded=True):
        for title, location, role in MODULES.values():
            st.write(f"**{title}** · {location}")
            st.caption(role)
    st.subheader("Evidências e situação de cada frente")
    try:
        with st.spinner("Consultando situação dos módulos..."):
            integrations = api.get("/integrations")
        if isinstance(integrations, dict):
            integrations = integrations.get("integrations", [])
        for module in integrations:
            name = module.get("discipline", "Módulo")
            title = MODULES.get(name, (name,))[0]
            with st.expander(title, expanded=False):
                status_card("Modo de integração", mode_label(module.get("mode")))
                st.markdown(str(module.get("status", "Situação não informada.")))
                st.write("**Evidências disponíveis**")
                st.write(module.get("evidence") or "Nenhuma evidência informada.")
                st.write("**Pendências**")
                st.write(module.get("pending") or "Nenhuma pendência informada pela API; conferir a documentação.")
                show_integration_data(module)
    except api.APIError as error:
        st.error(str(error))


def render_sound():
    from frontend.features.sound_recognition import render
    render()
