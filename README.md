# Bairro em Dia

Aplicação piloto para registrar, revisar e acompanhar problemas do bairro. Reúne relatos de pavimentação e de incômodo sonoro, orientação com fontes, reconhecimento de sons e painel de acompanhamento.

Este repositório contém o código executável, testes, recursos usados pela aplicação e a [entrega de Governança em IA e Business Analytics](governanca/README.md). Os trabalhos autônomos das outras disciplinas, como os PDFs de Cluster e Computação Quântica, permanecem nas entregas próprias.

## Entrega de Governança

- [Relatório final em PDF](governanca/relatorio/Bairro_em_Dia_Governanca_ABNT.pdf) — 15 páginas.
- [Relatório editável em Word](governanca/relatorio/Bairro_em_Dia_Governanca_ABNT.docx).
- [Vídeo final no YouTube, Não Listado](https://youtu.be/kFcjvWzllZc) — aproximadamente 6min45s, com demonstração real de RPA.
- [Índice dos materiais, requisitos e evidências](governanca/README.md).

A tag `governanca-v1.1` identifica a versão organizada para entrega. Publicação no GitHub não substitui submissão no Portal acadêmico.

## O que funciona

- Registro de ocorrências com localização confirmada, foto e histórico em SQLite.
- Detector ONNX de pavimentação com caixas sobre a imagem para revisão humana.
- Assistente que consulta uma base documental e apresenta as fontes; geração opcional com Ollama.
- Análise de WAV com YAMNet no servidor, incluindo eventos de acessibilidade e sugestões de classes de incômodo sonoro.
- Aprovação ou rejeição humana antes de emitir protocolo interno, acompanhamento por estados e indicadores.
- Robô RPA que importa lotes, retoma a execução com checkpoint e evita duplicação. A aprovação continua manual.

Os modelos são de terceiros, pré-treinados, e precisam ser instalados. Sem eles, o sistema informa a indisponibilidade; a consulta extrativa e o fluxo de revisão continuam disponíveis.

## Instalação local — Windows / PowerShell

Pré-requisitos: Git e Python 3.12 ou 3.13 de 64 bits. Para geração de texto, instale e execute o Ollama separadamente. Os downloads dos modelos e das dependências precisam de internet.

```powershell
git clone https://github.com/viniciusadrian1/bairroemdia.git
cd bairroemdia
py -3.13 -m venv app/.venv
& ./app/.venv/Scripts/python.exe -m pip install -r app/requirements-dev.txt
Copy-Item app/.env.example app/.env
& ./app/scripts/start_local.ps1
```

Abra http://127.0.0.1:8502. A API fica em http://127.0.0.1:8000 e sua documentação interativa em http://127.0.0.1:8000/docs. O modo inicial `extractive` consulta os documentos sem gerar texto com LLM. Se a política do PowerShell bloquear scripts locais, utilize o comando equivalente abaixo, sem alterar a política do sistema:

```powershell
& ./app/.venv/Scripts/python.exe app/scripts/runtime_manager.py start
```

### Ativar os modelos

```powershell
& ./app/.venv/Scripts/python.exe app/scripts/setup_vision.py
& ./app/.venv/Scripts/python.exe app/scripts/setup_yamnet.py --install-runtime --verify
ollama pull gemma3:1b
& ./app/scripts/runtime_stop.ps1
& ./app/scripts/start_local.ps1 -WithModels
```

O YAMNet utiliza um ambiente separado em `.venv-audio`; não instale o TensorFlow no ambiente global. O instalador verifica hashes e faz uma inferência com silêncio sintético. Isso verifica execução, não acurácia em situações reais. A configuração `OLLAMA_MODEL` pode ser alterada em `app/.env`; o tempo de resposta depende do computador. Para usar somente visão, configure `VISION_MODEL_PATH=modelos/vision/best.onnx` em `app/.env` e inicie sem `-WithModels`.

O launcher gerencia somente os processos que ele próprio iniciou. Logs e identificação dos processos ficam em `app/runtime/`. Para consultar ou parar:

```powershell
& ./app/scripts/runtime_diagnose.ps1
& ./app/scripts/runtime_stop.ps1
```

### Linux/macOS ou execução manual

Crie `app/.venv` com `python3 -m venv app/.venv`, instale os mesmos requisitos com esse interpretador e execute os instaladores dos modelos se desejado. O launcher PowerShell é específico do Windows. Em dois terminais, a partir de `app/` e com o ambiente ativado:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8502
```

As variáveis de ambiente são descritas em `app/.env.example`. Na execução manual, exporte as configurações desejadas nos terminais. O corpus e o YAMNet têm caminhos padrão relativos ao próprio código. Configure `VISION_MODEL_PATH` e `LLM_MODE=ollama` quando quiser ativá-los.

## Demonstrar o RPA

Com a API em execução:

```powershell
& ./app/.venv/Scripts/python.exe app/automation/robot.py
```

O lote de exemplo contém três registros sintéticos válidos e um inválido. Na interface, abra as ocorrências importadas, revise e aprove uma delas. Execute o mesmo comando novamente: o robô emite protocolo apenas para a aprovada e não duplica as importações. Preserve o checkpoint e o `--batch-id` ao repetir o mesmo lote. Use um novo identificador para um lote diferente. O robô registra resultados em `app/automation/runtime/`.

## Testes

Na raiz do repositório:

```powershell
& ./app/.venv/Scripts/python.exe -m pytest -q
& ./app/.venv/Scripts/python.exe app/scripts/runtime_selftest.py
```

Os testes cobrem fluxo de revisão e protocolo, persistência de fotos, repetição de requisições, recuperação do RPA, validação de áudio, decisões de classificação e interação da interface. Os testes numéricos de reamostragem usam o ambiente isolado de áudio e são ignorados quando ele não está instalado. O segundo comando testa início, reutilização e parada de processos em portas isoladas no Windows. Fixtures sintéticas e testes com provedores simulados não demonstram acurácia dos modelos nem usabilidade com usuários finais.

## Docker Compose (alternativa)

Após instalar os arquivos dos modelos no host, execute `docker compose up --build`. O Compose monta `app/modelos` somente para leitura e guarda o banco em volume próprio. Para usar Ollama do host, configure `LLM_MODE=ollama` no ambiente do Compose; os contêineres usam `host.docker.internal`. Os serviços ficam restritos a portas locais. A construção inclui um runtime TensorFlow separado e pode ser demorada. Não confundir a validação da configuração do Compose com um teste de execução dos contêineres.

## Estrutura

```text
app/backend/        API FastAPI, regras, persistência e provedores de IA
app/frontend/       interface Streamlit e componentes de upload
app/automation/     robô RPA e lote sintético de exemplo
app/resources/      corpus de consulta e descrição dos módulos
app/modelos/        procedência, licenças e classes; pesos via instaladores
app/scripts/        instalação de modelos e controle de execução
app/tests/          testes da API, provedores, RPA e interface
docs/               contratos de funcionamento e limites do piloto
governanca/         relatório, vídeo e evidências da entrega integrada
```

## Governança e limites

A IA sugere informações; a revisão humana aprova ou rejeita a ocorrência antes do protocolo. Importação, análise e registros de auditoria são automatizados. Os protocolos com prefixo `SIM` são internos: não são enviados a órgãos públicos e não asseguram atendimento. O histórico local auxilia a rastreabilidade, mas não é um registro inviolável.

O YAMNet identifica classes de som; não mede decibéis, não comprova infração e não determina sozinho a origem de um ruído. Não há inferência Edge Impulse no celular nesta implementação. Visão computacional é voltada a pavimentação e não reconhece todos os problemas urbanos. Não há execução em cluster ou computação quântica dentro da aplicação.

Este é um piloto sem autenticação, autorização por papéis ou validação com usuários finais. Execute localmente com dados sintéticos. Fotos são armazenadas como JPEG sem EXIF, junto à ocorrência, no SQLite; a remoção de EXIF não apaga rostos ou placas visíveis. Não inclua dados pessoais, imagens de terceiros ou credenciais nos relatos. Consulte [os contratos do protótipo](docs/CONTRATOS.md).

## Autores do projeto

- Gabriel Tonelli Avelino dos Santos — RM 564705
- Marcelo Roberto Maso Junior — RM 562163
- Vinícius Adrian Siqueira de Oliveira — RM 564962

Publicação e manutenção deste repositório: [viniciusadrian1](https://github.com/viniciusadrian1).

Modelos e fontes tipográficas preservam a autoria e as licenças de seus respectivos fornecedores. Sua inclusão não significa treinamento dos modelos pelo grupo.
