"""HTTP only. Never call a model provider from the browser layer."""
import os
from urllib.parse import quote

import requests
import streamlit as st


class APIError(Exception):
    """Safe, citizen-facing error. Never includes raw server content."""


def base_url():
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def request(method, path, payload=None):
    try:
        timeout = min(180, max(1, float(os.getenv("API_TIMEOUT_SECONDS", "40"))))
    except ValueError:
        timeout = 40
    try:
        response = requests.request(method, base_url() + path, json=payload,
                                    timeout=(4, timeout))
        if response.status_code == 422:
            raise APIError("Não foi possível validar os dados. Confira os campos e o formato do arquivo.")
        if response.status_code == 409:
            raise APIError("O registro mudou ou ainda não permite essa ação. Atualize a lista e confira a revisão.")
        if response.status_code == 404:
            raise APIError("Este registro não foi encontrado. Atualize a lista para continuar.")
        if response.status_code == 413:
            raise APIError("O arquivo é muito grande. Use um arquivo menor e tente novamente.")
        if response.status_code == 503 and path.startswith("/audio/"):
            raise APIError("O modelo de áudio está indisponível no momento. Tente novamente quando o serviço estiver disponível.")
        if response.status_code >= 500:
            raise APIError("O serviço não conseguiu concluir a operação. Tente novamente em instantes.")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, (dict, list)):
            raise APIError("A resposta do serviço está incompleta. Tente novamente em instantes.")
        return data
    except requests.Timeout:
        raise APIError("O serviço demorou para responder. Antes de repetir um cadastro, atualize a lista para conferir se foi salvo.") from None
    except requests.ConnectionError:
        raise APIError("O serviço está indisponível no momento. Seus campos continuam nesta tela; tente novamente em instantes.") from None
    except (requests.RequestException, ValueError):
        raise APIError("Não foi possível ler a resposta do serviço. Tente novamente em instantes.") from None


def get(path):
    return request("GET", path)


def post(path, payload=None):
    return request("POST", path, payload or {})


def report_path(report_id, action=""):
    return "/reports/" + quote(str(report_id), safe="") + ("/" + action if action else "")


def get_image(report_id):
    """Read sanitized review media; never cache citizen media globally."""
    try:
        response = requests.request("GET", base_url() + report_path(report_id, "image"), timeout=(4, 40))
        if response.status_code == 404:
            raise APIError("A imagem deste registro não está disponível. Atualize os relatos para conferir.")
        if response.status_code >= 400:
            raise APIError("O serviço não conseguiu carregar a imagem. Tente novamente em instantes.")
        response.raise_for_status()
        if response.headers.get("Content-Type", "").split(";")[0].strip().lower() not in {"image/png", "image/jpeg"}:
            raise APIError("O serviço retornou um formato de imagem inválido.")
        data = response.content
        if not data or len(data) > 20_000_000:
            raise APIError("A imagem recebida está vazia ou ultrapassa o limite de leitura.")
        return data
    except requests.Timeout:
        raise APIError("O serviço demorou para carregar a imagem. Tente novamente em instantes.") from None
    except requests.RequestException:
        raise APIError("Não foi possível carregar a imagem. Confira a conexão e tente novamente.") from None


@st.cache_data(ttl=10, show_spinner=False)
def health(url):
    """Cache only public availability; no report, chat or image crosses sessions."""
    return get("/health")
