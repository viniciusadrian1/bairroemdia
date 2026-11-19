# Evidências da entrega integrada

Os arquivos deste diretório apoiam a demonstração de Governança. Não são bancos de produção nem avaliações com usuários finais.

| Evidência | Conteúdo |
|---|---|
| `rpa/execucao-01.json` a `execucao-03.json` | Registros das três execuções reais do robô contra a API local, usados na gravação |
| `rpa/lote-video.csv` | Três entradas sintéticas válidas e uma com latitude inválida |
| `rpa/robot.jsonl` | Resultados registrados pelo robô |
| `rpa/validacao.json` | Nove verificações: bloqueio antes da revisão, protocolo somente do aprovado e ausência de duplicação |
| `validacao-video.json` | Duração, resolução, integridade do vídeo final e preservação do áudio na revisão do trecho de RPA |
| `publicacao-video.json` | Metadados públicos consultados no YouTube: identificador, duração, disponibilidade e Não Listado |
| `validacao-documento.json` | Paginação, estrutura, formato e integridade do relatório final |
| `verificacao-codigo.json` | Resultado dos testes da aplicação publicada e escopo da verificação |

A revisão na demonstração do RPA foi assistida na interface. Uma orientação incorreta do modelo sobre volume sonoro foi identificada e tratada durante o ensaio, como registrado em `rpa/validacao.json`. A evidência confirma o comportamento do fluxo demonstrado, não a confiabilidade semântica de toda resposta do modelo.

Para reproduzir o recebimento de um lote e sua retomada, siga o tópico RPA do [README principal](../../README.md). Use somente dados sintéticos e preserve a identificação do lote ao repetir uma execução.

## Dados dos estudos de integração

O [complemento de evidências](integracao/README.md) relaciona dados, parâmetros e código histórico aos resultados do relatório, com verificador offline. Ele não repete as inferências nem substitui revisão humana.
