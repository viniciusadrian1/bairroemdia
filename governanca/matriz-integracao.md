# Matriz de integração do Bairro em Dia

Esta matriz sintetiza a contribuição de cada disciplina para Governança e distingue o que é executado pelo aplicativo do que constitui estudo ou proposta. O relatório final contém a discussão e os resultados dos ensaios do grupo.

| Disciplina | Contribuição e localização | Limite declarado |
|---|---|---|
| Front End and Mobile Development | Interface responsiva, cadastro, revisão, filtros e painel em `app/frontend/` | Aplicação web; não é APK/IPA. Avaliação com usuários finais ainda necessária |
| Visão Computacional | Provedor ONNX e caixas para revisão em `app/backend/providers/vision.py` | Detector externo pré-treinado de pavimentação; instalação dos pesos via script; não reconhece todo problema urbano |
| NLP Chatbots e Virtual Agents | Corpus de 125 trechos em `app/resources/corpus_texto.jsonl` e recuperação documental | Conjuntos e código de preparação em `evidencias/integracao/originais/nlp/`; revisão humana da fidelidade continua necessária |
| Generative AI Advanced Nets | Orientação com fontes e Ollama em `app/backend/providers/llm.py` | Geração depende do modelo local; validações estruturais não asseguram fidelidade semântica |
| AI for Robotic Process Automation | Importação, checkpoint e protocolo idempotente em `app/automation/robot.py` | Não aprova registros nem envia solicitações a órgãos públicos; gravação atual em `evidencias/rpa-v3/`, ensaio anterior em `evidencias/rpa/` |
| Physical Computing e Cognitive IoT | WAV, YAMNet no servidor, eventos e vínculo ao relato | Não mede decibéis; não substitui coleta, treinamento e demonstração no celular exigidos na entrega específica de IoT |
| Cluster Computing | Simulação iSPD no relatório e vídeo; modelos e seis execuções em `evidencias/integracao/originais/capacidade/` | Sem cluster físico ou inferência distribuída no aplicativo; carga hipotética não calibrada |
| Computação Quântica e IA | Diagnóstico clássico e proposta de evolução; medições em `evidencias/integracao/originais/desempenho/` | Nenhuma execução ou vantagem quântica demonstrada; PDFs de outras matérias não incluídos |
| Governança em IA e Business Analytics | Validação, revisão humana antes do protocolo, histórico, estados e indicadores | Piloto local sem autenticação de produção, sem garantia de inviolabilidade do histórico e sem validação com cidadãos |

## Versão gravada e versão distribuída

A versão local gravada consultava arquivos de estudos acadêmicos na área de transparência. A publicação do aplicativo foi organizada para funcionar sem as pastas das disciplinas. Assim, a cópia pública identifica os estudos de Cluster e Quântica como externos e os sintetiza nos materiais de Governança, sem depender dos arquivos acadêmicos originais. O complemento `evidencias/integracao/` fornece os registros necessários para conferir os números apresentados, com verificador offline e limitações explícitas. As funções de registro, análise, revisão, RPA e acompanhamento permanecem no código publicado.

## Supervisão e rastreabilidade

A IA faz sugestões; o fluxo exige uma revisão explícita antes do protocolo. Importação, análise e registros de histórico são automatizados, portanto não se afirma que cada operação interna passa por revisão humana. O robô só protocola itens já aprovados. Os protocolos `SIM` pertencem à demonstração.

O painel apresenta contagens e distribuições dos registros locais. Não representa demanda municipal nem impacto social comprovado. A demonstração utiliza dados sintéticos; a operação capturada foi assistida, sem constituir teste com participantes humanos.
