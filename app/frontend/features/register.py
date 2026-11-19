import base64

import streamlit as st

from frontend.providers import api
from frontend.state.session import remember_report, request_id_for, reset_report_form, open_report
from frontend.ui.components import CATEGORIES, heading, show_report, show_sound_evidence
from frontend.ui.upload import file_picker


def render():
    heading("Conte o que aconteceu", "Registre → Confira a análise → Crie um protocolo interno")
    st.info("Use dados sintéticos ou públicos neste protótipo. Não inclua nomes, contatos, rostos ou placas identificáveis.")
    if st.session_state.get("report_attempt") and st.button("Novo relato"):
        reset_report_form()
        st.rerun()
    version = st.session_state.get("report_form_version", 0)
    sound_event = st.session_state.get("draft_sound_event")
    if sound_event:
        show_sound_evidence(sound_event, pending=True)
        st.caption("A análise já está pronta. Descreva o que aconteceu e confirme se ela corresponde a este relato.")
        st.button("Continuar sem esta análise", on_click=reset_report_form)
    with st.form(f"new_report_{version}", clear_on_submit=False):
        category = st.selectbox("Tipo de ocorrência", list(CATEGORIES), index=1 if sound_event else 0,
                                format_func=CATEGORIES.get, key=f"report_category_{version}")
        description = st.text_area("Descreva a ocorrência", max_chars=2000,
                                   placeholder="Ex.: Há um buraco na pista próximo à esquina. Foto feita sem entrar na via.", height=120)
        neighborhood = st.text_input("Bairro ou região", max_chars=80, placeholder="Ex.: Bairro de demonstração")
        cols = st.columns(2)
        latitude = cols[0].number_input("Latitude da ocorrência", min_value=-90.0, max_value=90.0, value=None, format="%.6f")
        longitude = cols[1].number_input("Longitude da ocorrência", min_value=-180.0, max_value=180.0, value=None, format="%.6f")
        st.caption("Informe as coordenadas do local do problema. A posição atual do celular pode ser diferente.")
        location_confirmed = st.checkbox("Confirmei que essas coordenadas correspondem à ocorrência")
        photo = file_picker("Enviar foto da ocorrência", extensions=["jpg", "jpeg", "png"],
                            max_bytes=5_000_000, help_text="Foto em JPEG ou PNG · Até 5 MB",
                            key=f"report_photo_{version}")
        st.caption("Para relato sonoro, a foto é opcional. Relatar um som não mede volume e não comprova infração.")
        consent = st.checkbox("Estou usando dados públicos ou sintéticos e conferi a privacidade do texto e da imagem")
        sound_confirmed = st.checkbox("Conferi que esta análise sonora corresponde ao relato que estou registrando") if sound_event else True
        submitted = st.form_submit_button("Analisar relato", type="primary", use_container_width=True)
    if submitted:
        errors = []
        if len(description.strip()) < 10:
            errors.append("Descreva a ocorrência com pelo menos 10 caracteres.")
        if len(neighborhood.strip()) < 2:
            errors.append("Informe o bairro ou a região.")
        if latitude is None or longitude is None or not location_confirmed:
            errors.append("Informe e confirme a localização da ocorrência.")
        if category == "pothole" and not photo:
            errors.append("Inclua uma foto para a análise do dano na pavimentação.")
        if photo and photo.size > 5_000_000:
            errors.append("A foto ultrapassa 5 MB. Use uma versão menor.")
        if not consent:
            errors.append("Confira a privacidade e a origem dos dados antes de continuar.")
        if sound_event and category != "sound":
            errors.append("Para usar esta análise, escolha Relato sonoro. Para pavimentação, continue sem esta análise.")
        if not sound_confirmed:
            errors.append("Confirme que o resultado sonoro corresponde a este relato antes de vinculá-lo.")
        if errors:
            for error in errors:
                st.error(error)
        else:
            payload = {"description": description.strip(), "neighborhood": neighborhood.strip(),
                       "latitude": latitude, "longitude": longitude, "location_confirmed": True, "category": category}
            if photo:
                payload["image_base64"] = base64.b64encode(photo.getvalue()).decode("ascii")
            if sound_event:
                payload["sound_event_id"] = sound_event["event_id"]
            payload["client_request_id"] = request_id_for(payload)
            try:
                with st.spinner("Analisando o relato e consultando orientações..."):
                    report = api.post("/reports", payload)
                if not isinstance(report, dict) or not all(k in report for k in ("id", "status")):
                    raise api.APIError("A resposta recebida está incompleta. Atualize os relatos antes de repetir o cadastro.")
                remember_report(report)
                if photo and not report.get("image_available"):
                    st.session_state.report_photos[report["id"]] = photo.getvalue()
                st.success("Relato registrado para revisão. Nenhum protocolo foi enviado a uma autoridade.")
                st.session_state.last_created = report
            except api.APIError as error:
                st.error(str(error))
    report = st.session_state.get("last_created")
    if report:
        heading("Próximo passo: confira e confirme", "Revise os dados e a análise para decidir sobre o protocolo interno.")
        st.button("Conferir este relato", type="primary", on_click=open_report, args=(report["id"],))
        show_report(report)
