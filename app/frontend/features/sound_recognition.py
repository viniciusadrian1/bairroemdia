"""Explicit audio inference over HTTP; no automatic or manual classification fallback."""
import base64
import hashlib
from io import BytesIO
import json
from uuid import uuid4
import wave

import streamlit as st

from frontend.providers import api
from frontend.ui.components import heading, status_card
from frontend.ui.upload import file_picker
from frontend.state.session import start_sound_report
from frontend.ui.sound_labels import SOURCE_LABELS, neighborhood_source

LABELS = {"campainha": "Campainha", "batida": "Batida", "outro": "Outro som", "incerto": "Incerto",
          "ambiente": "Ambiente", "doorbell": "Campainha", "knock": "Batida", "ambient": "Ambiente"}
SOURCES = {"yamnet": "YAMNet (análise no servidor)", "manual": "Importação manual",
           "edge_impulse": "Edge Impulse (declarado)"}


def validate_wav(data):
    if not data or len(data) > 3_000_000:
        raise ValueError("Selecione ou grave um áudio WAV de até 3 MB.")
    try:
        with wave.open(BytesIO(data), "rb") as audio:
            rate, frames = audio.getframerate(), audio.getnframes()
            channels, width = audio.getnchannels(), audio.getsampwidth()
            if audio.getcomptype() != "NONE" or width != 2 or channels not in (1, 2) or not 8000 <= rate <= 48000:
                raise ValueError("Use WAV PCM de 16 bits, mono ou estéreo, entre 8 e 48 kHz.")
            duration = frames / rate
            if not 1 <= duration <= 15:
                raise ValueError("O áudio precisa durar de 1 a 15 segundos.")
            if len(audio.readframes(frames)) != frames * channels * width:
                raise ValueError("O arquivo de áudio está incompleto. Grave ou selecione outro WAV.")
            return duration
    except (wave.Error, EOFError, OSError) as error:
        raise ValueError("Não foi possível ler o áudio. Use um arquivo WAV PCM de 16 bits.") from error


def analysis_identity(data, context):
    return json.dumps([hashlib.sha256(data).hexdigest(), context.get("model_version"),
                       context.get("decision_version"), context.get("source_profile_version")], separators=(",", ":"))


def analyze(data, context):
    fingerprint = analysis_identity(data, context)
    identities = st.session_state.setdefault("audio_request_ids", {})
    request_id = identities.setdefault(fingerprint, str(uuid4()))
    result = api.post("/audio/analyze", {"audio_base64": base64.b64encode(data).decode("ascii"),
                                         "client_request_id": request_id})
    if (not isinstance(result, dict) or not result.get("event_id") or result.get("source") != "yamnet"
            or result.get("label") not in {"campainha", "batida", "outro", "incerto"}
            or not isinstance(result.get("analysis"), dict) or result["analysis"].get("mode") != "yamnet"):
        raise api.APIError("A resposta da análise de áudio está incompleta. Confira os eventos antes de reenviar.")
    st.session_state.audio_result = {"fingerprint": fingerprint, "event": result}
    return result


def show_result(event):
    analysis = event["analysis"]
    st.subheader("Resultado da análise")
    source = neighborhood_source(event)
    if source:
        status_card("Tipo de som no relato", SOURCE_LABELS[source['label']])
        st.caption(source.get('reason', 'Confira se a sugestão corresponde ao que você ouviu.'))
        if isinstance(source.get('score'), (int, float)):
            st.caption(f"Escore do tipo de som: {source['score']:.3f} · Classe: {source.get('model_class', 'não informada')} · Média do clipe. Não mede volume.")
        st.caption("Descreva no relato o incômodo, o horário e o contexto. A análise identifica conteúdo sonoro, sem determinar quem o produziu.")
    if not source or event['label'] in ('campainha', 'batida'):
        status_card("Som de acessibilidade" if source else "Som sugerido", LABELS.get(event["label"], event["label"]))
    if event["label"] == "incerto" and not source:
        st.info("O modelo não sustentou uma classificação conclusiva. Confira o áudio e as classes sugeridas.")
    confidence = event.get("confidence")
    if isinstance(confidence, (float, int)):
        if not source or event['label'] in ('campainha', 'batida'):
            st.caption(f"Escore da decisão de acessibilidade: {confidence:.3f}. Não representa acurácia medida nem decibéis.")
    st.write("**Quer registrar o que aconteceu?**")
    st.caption("Leve esta análise para um relato, informe o contexto e o local e confira os dados antes do protocolo. Você também pode usar apenas o reconhecimento sonoro.")
    st.button("Criar relato com esta análise", on_click=start_sound_report,
              args=(event,), use_container_width=True)
    windows = analysis.get("event_windows") or []
    temporal_event = analysis.get("aggregation") == "target_event_windows" and isinstance(windows, list) and bool(windows)
    if temporal_event:
        with st.expander("Em que trecho o som apareceu?"):
            st.write("**Evento em trecho do áudio**")
            st.caption("Os intervalos abaixo são janelas sugeridas pelo modelo. Seus escores podem diferir da média do clipe inteiro; não delimitam com precisão o início e o fim do som.")
            st.dataframe([{"Início (s)": row.get("start_seconds"), "Fim (s)": row.get("end_seconds"),
                           "Som": LABELS.get(row.get("label"), row.get("label")), "Escore": row.get("score")}
                          for row in windows if isinstance(row, dict)], use_container_width=True, hide_index=True)
    classes = analysis.get("top_classes", [])
    if isinstance(classes, list) and classes:
        with st.expander("Conferir outras sugestões do modelo"):
            st.write("**Classes da janela selecionada**" if temporal_event else "**Classes retornadas pelo modelo**")
            st.dataframe([{"Classe": row.get("label"), "Escore": row.get("score")} for row in classes if isinstance(row, dict)],
                         use_container_width=True, hide_index=True)
            st.caption("Classes originais do modelo, que podem estar em inglês; os escores não são uma medição acústica calibrada.")
    means = analysis.get("mean_top_classes")
    if isinstance(means, list) and means:
        with st.expander("Médias do clipe completo"):
            st.caption("Escores médios ao longo do áudio, apresentados separadamente dos escores das janelas de evento.")
            st.dataframe([{"Classe": row.get("label"), "Escore": row.get("score")} for row in means if isinstance(row, dict)],
                         use_container_width=True, hide_index=True)
    with st.expander("Origem da análise"):
        for warning in analysis.get("warnings", []):
            st.warning(str(warning))
        st.caption(f"Duração: {analysis.get('duration_seconds', 'não informada')} s · Amostragem: {analysis.get('sample_rate', 'não informada')} Hz · Tempo de análise: {analysis.get('latency_ms', 'não informado')} ms")
        st.write("YAMNet executado no servidor. A captura no navegador não significa inferência no celular.")
        st.caption(f"Modelo: {event.get('model_version', 'não informado')} · SHA-256: {analysis.get('model_sha256', 'não informado')}")
        if analysis.get("decision_version"):
            st.caption(f"Versão da decisão: {analysis['decision_version']} · Agregação: {analysis.get('aggregation', 'não informada')}")
        if source:
            st.caption(f"Classificação para o bairro: {source.get('version')} · Agregação: {source.get('aggregation')}")
        st.caption(f"Evento: {event['event_id']} · Observado em: {event.get('observed_at', 'não informado')}")


def legacy_import():
    with st.expander("Importar resultado existente (manual ou Edge Impulse)"):
        st.caption("Importar um resultado demonstra troca de dados. A origem é declarada e não comprova execução do modelo no celular.")
        st.link_button("Abrir captura de áudio no navegador", "http://127.0.0.1:8765/mobile.html")
        st.caption("Serviço separado de captura neste computador; confira nessa página se há modelo disponível.")
        with st.form("import_sound"):
            event_file = file_picker("Enviar resultado sonoro", extensions=["json"], max_bytes=100_000,
                                     help_text="Arquivo JSON · Um evento · Até 100 KB", key="sound_file")
            submit = st.form_submit_button("Importar evento sonoro")
        if submit:
            try:
                if event_file is None:
                    raise ValueError("Escolha um arquivo JSON de resultado.")
                payload = json.loads(event_file.getvalue())
                if not isinstance(payload, dict):
                    raise ValueError("O arquivo não contém um objeto JSON válido.")
                api.post("/sound-events", payload)
                st.success("Evento importado com origem declarada. Não é uma análise YAMNet realizada nesta tela.")
            except (ValueError, UnicodeDecodeError):
                st.error("Escolha um arquivo JSON contendo um objeto de resultado válido.")
            except api.APIError as error:
                st.error(str(error))


def render():
    heading("Sons do bairro e acessibilidade", "Identifique possíveis sons de furadeira, obra ou música e leve a análise para um relato.")
    st.info("Use sons públicos, sintéticos ou gravados com autorização, sem conversas privadas. Classificar um som não mede decibéis nem comprova infração. O protótipo não substitui alertas de emergência.")
    st.caption("A análise roda no servidor somente ao clicar em Analisar áudio. O resultado é salvo como evento; o clipe não é persistido pelo backend e permanece temporariamente nesta sessão para reprodução.")
    context = dict(st.session_state.get("audio_model_context", {}))
    try:
        status = api.get("/audio/status")
        if isinstance(status, dict):
            context.update({key: status[key] for key in ("model_version", "decision_version", "source_profile_version")
                            if isinstance(status.get(key), str) and status[key]})
            st.session_state.audio_model_context = context
        if isinstance(status, dict) and status.get("available") is True:
            st.success("Modelo de áudio configurado")
            st.caption("A execução será confirmada quando a análise do áudio retornar.")
        elif isinstance(status, dict) and status.get("available") is False:
            st.warning("Modelo de áudio indisponível no momento. A análise não será substituída por classificação manual.")
    except api.APIError as error:
        st.warning(str(error))
    source = st.radio("Como deseja fornecer o áudio?", ["Gravar pelo microfone", "Enviar arquivo WAV"], horizontal=True)
    if source == "Gravar pelo microfone":
        clip = st.audio_input("Grave de 1 a 15 segundos", key="yamnet_recording",
                              help="Permita o microfone quando o navegador solicitar. Em outro dispositivo, o acesso ao microfone pode exigir HTTPS.")
    else:
        clip = file_picker("Enviar áudio para análise", extensions=["wav"], max_bytes=3_000_000,
                           help_text="WAV PCM 16 bits · 1 a 15 segundos · Até 3 MB · Mono/estéreo · 8 a 48 kHz", key="yamnet_wav")
    data = clip.getvalue() if clip is not None else None
    valid = False
    if data is not None:
        try:
            duration = validate_wav(data)
            valid = True
            st.audio(data, format="audio/wav")
            st.caption(f"Áudio selecionado: {duration:.2f} segundos. Ouça antes de enviar.")
        except ValueError as error:
            st.error(str(error))
    consent = st.checkbox("Conferi que o áudio não contém conversas privadas e tenho autorização para enviá-lo")
    if st.button("Analisar áudio", type="primary"):
        if not valid:
            st.error("Grave ou selecione um WAV válido antes de analisar.")
        elif not consent:
            st.error("Confira a privacidade e a autorização do áudio antes de enviá-lo.")
        else:
            try:
                with st.spinner("Analisando o áudio e registrando o resultado..."):
                    analyze(data, context)
                st.success("Análise recebida e evento salvo. Reenviar este áudio com as mesmas versões do modelo e da decisão não cria outro evento.")
            except api.APIError as error:
                st.error(str(error))
    previous = st.session_state.get("audio_result", {})
    if valid and previous.get("fingerprint") == analysis_identity(data, context):
        show_result(previous["event"])
    legacy_import()
    st.subheader("Eventos recebidos")
    try:
        events = api.get("/sound-events")
        if events:
            st.dataframe([{"ID do evento": e.get("event_id", "Não informado"),
                           "Som": LABELS.get(e.get("label"), e.get("label", "Não informado")),
                           "Tipo de som no relato": SOURCE_LABELS.get((neighborhood_source(e) or {}).get('label'), 'Análise anterior / não disponível'),
                           "Escore": e.get("confidence"), "Origem": SOURCES.get(e.get("source"), "Não informada"),
                           "Observado em": e.get("observed_at"), "Versão do modelo": e.get("model_version"),
                           "Versão da decisão": (e.get("analysis") or {}).get("decision_version", "Não informada")}
                          for e in events], hide_index=True, use_container_width=True)
            st.caption("Escores e rótulos de origens distintas não são diretamente comparáveis.")
        else:
            st.caption("Nenhum evento sonoro recebido.")
    except api.APIError as error:
        st.error(str(error))
