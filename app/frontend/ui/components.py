from urllib.parse import urlparse
from io import BytesIO

import streamlit as st
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from frontend.providers import api

CATEGORIES = {"pothole": "Buraco / pavimentação", "sound": "Relato sonoro"}
STATUSES = {"pending_review": "Aguardando revisão", "approved": "Aprovado na revisão",
            "rejected": "Não aprovado", "protocolled": "Protocolo interno criado",
            "in_progress": "Em atendimento simulado", "resolved": "Concluído na simulação"}

MODES = {"extractive": "Consulta documental, sem geração por IA", "ollama": "IA local com consulta a fontes",
         "policy": "Orientação de segurança", "rules": "Regras de triagem", "configured": "Detector configurado",
         "unavailable": "Indisponível", "onnx": "Detector de imagens local", "yolo": "Detector de imagens local",
         "yamnet": "Reconhecimento sonoro no servidor",
         "ultralytics": "Detector de imagens local", "funcional": "Funcional", "dados": "Base de dados integrada",
         "model": "Detector de imagens local", "adapter": "Conector de análise", "transporte": "Recepção de eventos", "analise_simulada": "Análise simulada",
         "analise": "Estudo e análise", "integracao": "Integração", "erro": "Erro", "arquivo": "Importação de arquivo"}


def mode_label(mode):
    return MODES.get(mode, "Modo não identificado")


def heading(title, subtitle):
    st.subheader(title)
    st.caption(subtitle)


def status_card(label, value, description=None):
    """Used in report details, health, dashboard and integration views."""
    with st.container(border=True):
        st.caption(label)
        st.write(f"**{value}**")
        if description:
            st.caption(description)


def safe_link(url):
    return isinstance(url, str) and urlparse(url).scheme in {"http", "https"} and bool(urlparse(url).netloc)


def show_guidance(guidance):
    if not isinstance(guidance, dict) or not isinstance(guidance.get("answer"), str):
        st.warning("A orientação não está disponível para este registro.")
        return
    st.write(guidance["answer"])
    mode = guidance.get("mode", "não informado")
    if mode == "extractive":
        st.caption("Consulta a trechos da base documental. Esta resposta não foi gerada por um LLM.")
    else:
        st.caption(f"Modo da orientação: {mode_label(mode)}")
    if guidance.get("abstained"):
        st.info("A base não sustenta uma resposta conclusiva para esta pergunta.")
    for warning in guidance.get("warnings", []):
        st.warning(str(warning))
    sources = guidance.get("sources") or []
    if sources:
        with st.expander(f"Conferir fontes ({len(sources)})"):
            for source in sources:
                st.write("**" + str(source.get("title", "Documento da base")) + "**")
                st.caption(source.get("excerpt", ""))
                if safe_link(source.get("url")):
                    st.link_button("Abrir fonte", source["url"])


def show_review_images(photo, detections):
    """Draw detector coordinates on the exact image used by the backend."""
    try:
        original = ImageOps.exif_transpose(Image.open(BytesIO(photo))).convert("RGB")
        annotated = original.copy()
        draw = ImageDraw.Draw(annotated)
        for detection in detections:
            box = detection.get("bbox", [])
            if len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
                draw.rectangle(box, outline="#F59E0B", width=max(2, original.width // 250))
                draw.text((box[0], max(0, box[1] - 14)), "Possível dano", fill="#F59E0B")
        original_tab, analysis_tab = st.tabs(["Foto para revisão", "Resultado do detector"])
        with original_tab:
            st.image(original, caption="Confira visualmente a imagem antes de aprovar o relato.", use_container_width=True)
        with analysis_tab:
            st.image(annotated, caption="Caixas retornadas pelo detector." if detections else "Sem caixas retornadas. Isso não comprova ausência de dano.", use_container_width=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        st.warning("A imagem não pôde ser exibida. Não conclua a revisão visual sem conferir uma foto legível.")


def show_report_photo(report, detections):
    photos = st.session_state.setdefault("report_photos", {})
    report_id = report.get("id")
    photo = photos.get(report_id)
    if not photo and report.get("image_available"):
        try:
            photo = api.get_image(report_id)
            photos[report_id] = photo
        except api.APIError as error:
            st.warning(str(error))
            if st.button("Tentar carregar a foto novamente", key=f"retry_photo_{report_id}"):
                st.rerun()
    if photo:
        st.caption("Imagem preservada para revisão, com metadados removidos e tamanho ajustado." if report.get("image_available") else "Imagem disponível somente nesta sessão.")
        show_review_images(photo, detections)
    elif not report.get("image_available"):
        st.warning("Este registro antigo não tem foto disponível para revisão. Para pavimentação, registre uma nova ocorrência com foto antes de aprovar.")


def show_sound_evidence(event, pending=False):
    from frontend.ui.sound_labels import SOURCE_LABELS, neighborhood_source
    labels = {"campainha": "Campainha", "batida": "Batida", "outro": "Outro som", "incerto": "Incerto"}
    st.write("**Análise sonora selecionada**" if pending else "**Análise sonora vinculada**")
    source = neighborhood_source(event)
    if source:
        status_card("Tipo de som no relato", SOURCE_LABELS[source['label']])
        st.caption(source.get('reason', 'Confira a sugestão junto ao contexto relatado.'))
    if not source or event.get('label') in ('campainha', 'batida'):
        status_card("Som de acessibilidade" if source else "Som sugerido", labels.get(event.get("label"), "Não informado"))
    st.caption("Sugestão para sua revisão. Reconhecer o tipo de som não mede decibéis nem comprova infração.")
    with st.expander("Conferir a análise sonora e sua origem"):
        st.caption(f"Evento: {event.get('event_id')} · Modelo: {event.get('model_version')} · Analisado em: {event.get('observed_at')}")
        analysis = event.get("analysis") or {}
        if isinstance(event.get("confidence"), (int, float)):
            st.caption(f"Escore: {event['confidence']:.3f}. Não é acurácia medida.")
        if analysis.get("decision_version"):
            st.caption(f"Versão da decisão: {analysis['decision_version']}")
        if source:
            st.caption(f"Tipo de som: {SOURCE_LABELS[source['label']]} · Escore médio: {source.get('score')} · Classe: {source.get('model_class')} · Política: {source.get('version')}")
        if analysis.get("top_classes"):
            st.dataframe([{"Classe": c.get("label"), "Escore": c.get("score")}
                          for c in analysis["top_classes"]], use_container_width=True, hide_index=True)
        st.caption("Ao confirmar o cadastro, este resultado será preservado junto ao relato. O clipe não fica armazenado no banco." if pending
                   else "O resultado é preservado junto ao relato. O clipe não fica armazenado no banco.")


def show_report(report, compact=False):
    status_card("Situação", STATUSES.get(report.get("status"), report.get("status", "Não informada")),
                "Protocolo: " + (report.get("protocol") or "ainda não criado"))
    st.write(report.get("description", ""))
    st.caption(f"{report.get('neighborhood', '')} · {CATEGORIES.get(report.get('category'), 'Categoria não informada')}")
    if not compact:
        if report.get("sound_event"):
            show_sound_evidence(report["sound_event"])
        st.caption(f"Local confirmado: {report.get('latitude')} / {report.get('longitude')} · Registro {report.get('id')}")
        analysis = report.get("analysis") or {}
        st.write("**Análise para revisão**")
        st.write(analysis.get("summary", "Análise indisponível."))
        confidence = analysis.get("confidence")
        st.caption("Confiança: não estimada" if confidence is None else f"Confiança declarada: {confidence:.1%}. Não é acurácia medida.")
        st.caption(f"Modo: {mode_label(analysis.get('mode'))}")
        for warning in analysis.get("warnings", []):
            st.warning(str(warning))
        vision = report.get("vision")
        if vision:
            st.write("**Análise da imagem**")
            st.caption(f"Modo: {mode_label(vision.get('mode'))} · {vision.get('latency_ms', 0):.1f} ms")
            for warning in vision.get("warnings", []):
                st.warning(str(warning))
            detections = vision.get("detections") or []
            if detections:
                st.dataframe([{"Identificação": "Possível dano na pavimentação", "Confiança": d.get("confidence"),
                               "Coordenadas na imagem": d.get("bbox")} for d in detections], use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhuma caixa apresentada. Isso não comprova ausência de dano.")
            show_report_photo(report, detections)
        elif report.get("image_available"):
            show_report_photo(report, [])
        st.write("**Orientação documental**")
        show_guidance(report.get("guidance"))
