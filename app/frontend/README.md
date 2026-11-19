# Interface Bairro em Dia

Consulte a [instalação na raiz](../../README.md). A interface usa Streamlit e se comunica com a API FastAPI por HTTP. `API_BASE_URL` define o endereço e `API_TIMEOUT_SECONDS` o limite de espera. O frontend não carrega `.env` sozinho; o launcher injeta as configurações.

- `features/`: registro, revisão, assistente, painel e reconhecimento sonoro.
- `providers/api.py`: transporte HTTP, erros e consulta de disponibilidade.
- `state/session.py`: estado da sessão e identificadores de repetição.
- `ui/`: componentes, upload, anotações e identidade visual.

Fotos são recuperadas da API para revisão, inclusive em uma nova sessão. O backend guarda a versão JPEG sem EXIF no banco local. Relatos, fotos e mensagens não têm cache global. A disponibilidade da API tem cache de dez segundos.

As fontes WOFF2 e as licenças OFL estão em `assets/brand/`. O tema fica em `app/.streamlit/config.toml`; execute a interface a partir de `app/` para carregá-lo. Esta aplicação é web responsiva; não inclui APK ou IPA.
