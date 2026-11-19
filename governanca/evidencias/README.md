# Evidências da entrega integrada

Os arquivos deste diretório apoiam a demonstração de Governança. Não são bancos de produção nem avaliações com usuários finais.

| Evidência | Conteúdo |
|---|---|
| `rpa-v3/execucao-01.json` a `execucao-03.json` | Gravação atual de 19/11: importação, retomada e protocolo somente do aprovado; dois pendentes |
| `rpa-v3/validacao.json` | Conferência offline dos registros atuais; comando em [RPA V3](rpa-v3/README.md) |
| `rpa/execucao-01.json` a `execucao-03.json` | Ensaio anterior de 18/11, preservado como evidência histórica, com aprovação, rejeição e pendência |
| `rpa/lote-video.csv` | Três entradas sintéticas válidas e uma com latitude inválida |
| `rpa/robot.jsonl` | Resultados registrados pelo robô |
| `rpa/validacao.json` | Nove verificações: bloqueio antes da revisão, protocolo somente do aprovado e ausência de duplicação |
| `validacao-video.json` | Duração, resolução, integridade do MP4 V3 e preservação integral da narração; 77,9% de captura real |
| `publicacao-video.json` | Metadados públicos consultados no YouTube: identificador, duração, disponibilidade e Não Listado |
| `validacao-documento.json` | Paginação, estrutura, formato e integridade do relatório final |
| `verificacao-codigo.json` | Resultado dos testes da aplicação publicada e escopo da verificação |

A revisão nas demonstrações do RPA foi assistida na interface. Uma orientação incorreta do modelo sobre volume sonoro foi identificada e corrigida. A evidência confirma o comportamento dos fluxos demonstrados, não a confiabilidade semântica de toda resposta do modelo. A V3 mostra um aprovado e dois pendentes; rejeição e repetição após emitir protocolo pertencem ao ensaio anterior. Seus arquivos não foram sobrescritos.

Para reproduzir o recebimento de um lote e sua retomada, siga o tópico RPA do [README principal](../../README.md). Use somente dados sintéticos e preserve a identificação do lote ao repetir uma execução.

## Dados dos estudos de integração

O [complemento de evidências](integracao/README.md) relaciona dados, parâmetros e código histórico aos resultados do relatório, com verificador offline. Ele não repete as inferências nem substitui revisão humana.
