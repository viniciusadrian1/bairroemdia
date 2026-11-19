"""A small, explicit sequence of independent calls to the real image API."""
import base64
import json

import streamlit as st

from frontend.providers import api
from frontend.ui.components import heading, show_review_images, mode_label
from frontend.ui.upload import file_picker


def analyze_sequence(files):
    results = []
    for number, file in enumerate(files, start=1):
        photo = file.getvalue()
        item = {"frame": number, "photo": photo}
        try:
            if len(photo) > 5_000_000:
                raise api.APIError("A imagem ultrapassa 5 MB.")
            result = api.post("/vision", {"image_base64": base64.b64encode(photo).decode("ascii")})
            if not isinstance(result, dict) or not isinstance(result.get("detections"), list) or "mode" not in result:
                raise api.APIError("A análise recebida está incompleta.")
            item["result"] = result
        except api.APIError as error:
            item["error"] = str(error)
        results.append(item)
    return results


def render():
    heading("Sequência de imagens", "Compare de 2 a 12 fotos ou quadros extraídos de um vídeo, na ordem enviada.")
    st.info("Use imagens públicas ou sintéticas, sem pessoas ou placas identificáveis. Esta tela analisa cada imagem; não cria relatos nem protocolos.")
    st.caption("Não há rastreamento entre quadros nem medição de profundidade. Um detector indisponível é mostrado como indisponível, sem gerar caixas fictícias.")
    with st.form("vision_sequence"):
        files = file_picker("Enviar fotos ou quadros da sequência", extensions=["jpg", "jpeg", "png"],
                            max_bytes=5_000_000, help_text="De 2 a 12 imagens · JPEG ou PNG · Até 5 MB cada",
                            key="sequence_photos", max_files=12)
        consent = st.checkbox("Conferi a privacidade e a origem pública ou sintética das imagens")
        submitted = st.form_submit_button("Analisar sequência", type="primary")
    if submitted:
        if not 2 <= len(files) <= 12:
            st.error("Selecione de 2 a 12 imagens para comparar a sequência.")
        elif not consent:
            st.error("Confira a privacidade e a origem das imagens antes de continuar.")
        else:
            with st.spinner("Analisando cada imagem da sequência..."):
                st.session_state.vision_sequence_results = analyze_sequence(files)
    results = st.session_state.get("vision_sequence_results", [])
    if not results:
        return
    rows = [{"Quadro": item["frame"], "Modo": mode_label(item.get("result", {}).get("mode", "erro")),
             "Caixas": len(item.get("result", {}).get("detections", [])),
             "Tempo (ms)": item.get("result", {}).get("latency_ms"),
             "Aviso": item.get("error", "")} for item in results]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    for item in results:
        with st.expander(f"Quadro {item['frame']}"):
            if item.get("error"):
                st.error(item["error"])
            else:
                result = item["result"]
                for warning in result.get("warnings", []):
                    st.warning(str(warning))
                show_review_images(item["photo"], result["detections"])
    evidence = [{key: value for key, value in item.items() if key != "photo"} for item in results]
    st.download_button("Baixar resultados da sequência", json.dumps(evidence, ensure_ascii=False, indent=2),
                       file_name="sequencia-resultados.json", mime="application/json")
    st.caption("O arquivo contém os retornos da API por quadro, sem imagens ou nomes dos arquivos. Tempos dependem deste ambiente; não são medida de acurácia.")
