"""Portuguese, offline file picker with server-side envelope validation."""
import base64
import binascii
from io import BytesIO
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component

from frontend.ui.brand import asset_uri

_picker = declare_component("arquivo_em_portugues", path=str(Path(__file__).with_name("upload_component")))


def decode_upload(value, extensions, max_bytes):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Não foi possível ler o arquivo. Selecione-o novamente.")
    name, encoded = value.get("name"), value.get("base64")
    if not isinstance(name, str) or Path(name).suffix.lower().lstrip(".") not in extensions:
        raise ValueError("Formato de arquivo não permitido.")
    if not isinstance(encoded, str) or len(encoded) > 4 * ((max_bytes + 2) // 3):
        raise ValueError("O arquivo ultrapassa o limite permitido.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("O arquivo está incompleto. Selecione-o novamente.") from error
    if not data or len(data) > max_bytes:
        raise ValueError("O arquivo está vazio ou ultrapassa o limite permitido.")
    result = BytesIO(data)
    result.name, result.size = name, len(data)
    return result


def file_picker(label, *, extensions, max_bytes, help_text, key, max_files=1):
    value = _picker(label=label, extensions=extensions, maxBytes=max_bytes,
                    helpText=help_text, font=asset_uri("bricolage.woff2", "font/woff2"),
                    maxFiles=max_files, key=key, default=None)
    try:
        if max_files > 1:
            if value is None:
                return []
            if not isinstance(value, list) or len(value) > max_files or any(not isinstance(item, dict) for item in value):
                raise ValueError(f"Selecione no máximo {max_files} arquivos.")
            return [decode_upload(item, extensions, max_bytes) for item in value]
        return decode_upload(value, extensions, max_bytes)
    except ValueError as error:
        st.error(str(error))
        return [] if max_files > 1 else None
