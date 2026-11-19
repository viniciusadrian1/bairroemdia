# RPA na gravação V3 de 19 de novembro de 2026

Estes registros pertencem à execução mostrada no [vídeo atual](https://youtu.be/66U-OigDVys). São dados sintéticos do protótipo local. Os arquivos históricos da [demonstração anterior](../rpa) foram preservados separadamente.

| Execução | Resultado |
|---|---|
| 1 | Três relatos válidos importados; latitude inválida recusada por HTTP 422; todos aguardando revisão, sem protocolo. |
| 2 | Três importações retomadas pelo checkpoint; nenhuma duplicação e nenhum protocolo. |
| Revisão na interface | Um relato aprovado após conferência e correção da orientação sobre volume sonoro. A revisão foi assistida; o robô não aprova registros. |
| 3 | Um protocolo interno emitido para o aprovado; dois relatos permaneceram pendentes. |

A captura atual não contém rejeição de um relato nem uma quarta execução após emitir o protocolo. As verificações desses comportamentos na captura anterior permanecem em `../rpa/validacao.json`. A validação atual não reaproveita a contagem de nove verificações do ensaio anterior.

Na raiz do repositório, execute `python governanca/evidencias/rpa-v3/verificar_registros.py`. O comando confere hashes, identificadores, resultados e estados preservados, sem rede e sem alterar dados. `validacao.json` registra essa conferência; não é uma nova execução do sistema.

`monitor-captura.py` é a cópia histórica exata do monitor usado, que chama o robô original. Seus caminhos correspondem à organização do acervo original e não são um lançador deste repositório. Para executar um novo lote, siga o tópico RPA do README principal e use novos caminhos de saída; não sobrescreva estes registros. `proveniencia.json` permite conferir a integridade dos originais.

O monitor registra retornos reais da API; não representa um estudo com participantes. Reconhecimento de som não mede volume nem comprova infração. O protocolo é interno, sem envio a autoridades.
