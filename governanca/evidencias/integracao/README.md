# Evidências da integração para Governança

Este complemento permite conferir as afirmações quantitativas do relatório. Reúne registros históricos, entradas de avaliação, configurações e código de instrumentação. Não inclui os PDFs dos trabalhos das outras matérias, pesos de modelos nem gravações pessoais. O aplicativo continua independente destes estudos.

## Conferência reproduzível sem instalar o aplicativo

Na raiz do repositório, com Python 3.10 ou superior:

```console
python governanca/evidencias/integracao/verificar_evidencias.py
```

O comando usa apenas a biblioteca padrão, não acessa a rede e não altera arquivos. Retorna `status: passed` e os resultados recalculados, ou encerra com código 1 se encontrar inconsistência. O resultado desta revisão está em [validacao.json](validacao.json). Esta é uma conferência dos registros existentes, não uma nova execução dos modelos ou uma avaliação humana.

| Afirmação no relatório | Dados que permitem conferir | O que o verificador faz |
|---|---|---|
| Visão: 12 imagens, 27 caixas, TP 12, FP 13, FN 15 | [Predições](originais/visao/predictions.json), [rótulos](originais/visao/labels), [métricas](originais/visao/metrics.json) | Reconstrói caixas YOLO e refaz o pareamento por IoU 0,50, com confiança mínima 0,25; recalcula precisão e revocação |
| NLP: 125 trechos, 102 pares, 30 diálogos e 20 testes | [Corpus consumido pelo app](../../../app/resources/corpus_texto.jsonl), [conjuntos e qualidade](originais/nlp) | Conta registros, verifica metadados, hash do teste congelado e ausência de perguntas de teste idênticas no treino |
| Capacidade: 120 tarefas, dois ou quatro workers; redução de 49,9714% | [Seis execuções](originais/capacidade/results), [dois modelos iSPD](originais/capacidade/models), [síntese](originais/capacidade/resultados-integracao.json) | Confere conclusão e distribuição das tarefas, conservação do trabalho, tempos e redução |
| Desempenho: 153 inferências em 27 lotes; espera de 0,002 ms e 187,128 ms | [Chamadas e execuções](originais/desempenho/visao-real) | Recalcula a espera média pelo bloqueio a partir das chamadas e compara com os resumos |
| Ensaio HTTP: 51 chamadas bem-sucedidas | [Registros HTTP](originais/desempenho/http-visao-real) | Confere respostas 200 e modo de inferência real |
| Avaliação histórica do assistente com Qwen2.5:3b | [13 casos, fontes e respostas](originais/assistente/avaliacao-final.json) | Confere identidade do modelo e quantidade; não atribui fidelidade semântica |
| YAMNet: sugestão da fonte sonora | [Manifesto e três resultados](originais/som) | Confere hashes de entrada e concordância entre referência e categoria sugerida |

## Interpretação e limites

As predições de visão e os rótulos bastam para recalcular os indicadores do relatório, mas não para inspecionar visualmente as imagens. O [manifesto público](originais/visao/manifest.json) registra origem e revisão do conjunto. A independência em relação ao treinamento do detector externo não foi auditada.

Os limites de tokens de NLP são conferidos pelos metadados gravados; o verificador não reexecuta o tokenizador. A revisão humana de fidelidade permanece pendente e a [planilha de revisão](originais/nlp/revisao.csv) não é apresentada como preenchida. Ausência de pergunta idêntica não exclui vazamento semântico. Os [metadados das fontes oficiais](originais/nlp/fontes.json) preservam referências e hashes; os PDFs originais não são redistribuídos neste pacote.

O iSPD simula uma carga hipotética não calibrada pela aplicação. Os benchmarks de contenção e HTTP são clássicos e foram feitos na máquina descrita nos manifestos. Não constituem execução quântica, vantagem quântica ou capacidade de produção. As medições não devem ser somadas: têm instrumentos e objetivos diferentes.

O assistente foi avaliado historicamente com Qwen2.5:3b. A demonstração atual usa Gemma3:1b; os resultados não são transferíveis automaticamente. As respostas originais, inclusive erros, foram preservadas para revisão. A existência de citações não comprova correção semântica.

Nos três exemplos sonoros, música e obra coincidiram com a categoria de referência; furadeira foi sugerida como **obra/ferramentas**. São exemplos exploratórios de fontes públicas CC0, não uma estimativa de acurácia. O reconhecimento não mede decibéis nem determina infração. Áudios pessoais dos integrantes não integram este complemento.

## Proveniência e nova execução dos experimentos

[proveniencia.json](proveniencia.json) relaciona cada arquivo à sua localização no acervo original, tamanho e SHA-256. Os bytes históricos foram preservados, inclusive quebras de linha e caminhos locais informativos. A regra em `.gitattributes` impede que o Git altere esses bytes. Esses caminhos não concedem acesso à máquina e não são necessários ao verificador.

O diretório `originais` contém código arquivado para explicar como os resultados foram produzidos. Esses scripts ainda usam a organização original das disciplinas; **não são lançadores portáveis deste repositório**. Para obter uma nova medida, é preciso reconstruir as dependências e os caminhos abaixo, gravar a saída em outro diretório e registrar novas versões e hashes. Não sobrescreva os ensaios históricos.

| Experimento | Código e dependências para uma nova execução |
|---|---|
| Visão | `originais/visao/evaluate.py`, imagens da revisão indicada no manifesto, rótulos, provedor ONNX do app, OpenCV, NumPy, Pillow e modelo instalado pelas instruções do app |
| Preparação NLP | `originais/nlp/codigo/`, fontes do manifesto e tokenizador `Qwen/Qwen2.5-0.5B-Instruct`; exige revisão das dependências e da disponibilidade das fontes antes de regenerar |
| iSPD | `originais/capacidade/RunISPD.java`, modelos `.imsx`, Java e iSPD 2.0; SHA-256 do JAR usado: `411e1bf4751ec9a6f2e4b450a178f092584bd1ac0a55ece44757ce53cc9808f1`; projeto de origem: https://github.com/gspd-unesp/ispd. Outra versão pode produzir resultados diferentes |
| Desempenho clássico | `originais/desempenho/codigo/`, provedor congelado em `visao-real/fontes/vision.py`, entradas e versões dos manifestos; o ensaio HTTP também exige a API ativa |
| Assistente | Repetir as perguntas registradas no assistente do app com Ollama, Qwen2.5:3b e corpus correspondente à avaliação, preservando fontes e respostas; respostas de nova geração podem variar |
| Som | `originais/som/prepare_samples.py` e `verify_http.py`, fontes CC0 do manifesto, conversor de áudio e aplicativo com YAMNet instalado; verificar argumentos e caminhos antes de executar |

A conferência offline acima é a reprodução oferecida diretamente por este pacote. A repetição completa das inferências depende dos artefatos externos e do ambiente descritos; ela não foi novamente realizada para esta revisão documental.
