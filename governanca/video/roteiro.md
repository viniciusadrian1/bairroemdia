# Roteiro do vídeo de Governança

Referência das falas utilizadas na gravação. Vídeo final: https://youtu.be/kFcjvWzllZc (aproximadamente 6min45s). O trecho de RPA recebeu imagens da execução real do robô, mantendo a narração.

## Áudio 01 — Abertura

“Como transformar um problema percebido na rua em uma ocorrência organizada, que possa ser acompanhada? O Bairro em Dia reúne registro, orientação e acompanhamento para apoiar o cuidado com o bairro.

Nossa proposta abrange diferentes necessidades da comunidade. Nesta versão, demonstramos problemas de pavimentação, relatos sonoros e reconhecimento de sons para acessibilidade. A inteligência artificial ajuda a analisar as informações, enquanto a pessoa mantém o controle sobre o registro. Vamos mostrar essa jornada e como as nove disciplinas contribuem para uma mesma aplicação.”

## Áudio 02 — Do problema ao registro

“Imagine encontrar um buraco no caminho de casa. No Bairro em Dia, você pode registrar a foto, descrever o problema e informar o local.

É aqui que entra Visão Computacional: um detector pré-treinado analisa a imagem e destaca regiões que podem conter buracos. A marcação ajuda a localizar o que merece atenção e pode ser conferida junto à descrição.

Assim, o relato reúne imagem, contexto e localização para facilitar a análise e o acompanhamento.”

## Áudio 03 — Conferência e protocolo

“Antes de gerar o protocolo, a pessoa confere a análise e pode aprovar, corrigir ou rejeitar a sugestão. Essa revisão faz parte do funcionamento da aplicação: sem aprovação, o sistema bloqueia a emissão.

Depois da conferência, o registro recebe um protocolo interno, que permite identificá-lo no acompanhamento. Se houver uma tentativa repetida do mesmo envio, o sistema recupera a ocorrência existente, evitando duplicação.

Nesta demonstração, os protocolos ficam na própria plataforma, sem envio à prefeitura.”

## Áudio 04 — Acompanhamento e interface

“Registrar é o começo. Depois, o cidadão precisa conseguir encontrar sua ocorrência e consultar a situação.

Front-end e Mobile contribui com a interface que conecta essas etapas: cadastro, revisão e acompanhamento. O painel permite filtrar registros por categoria e situação, além de visualizar gráficos.

Na área do gestor simulado, mostramos uma ocorrência passando para atendimento e depois para resolvida. Essas mudanças ficam registradas e aparecem na consulta, mantendo o histórico acessível.”

## Áudio 05 — Orientação com NLP e Inteligência Generativa

“E quando o cidadão não sabe como descrever a situação ou quais informações apresentar? O assistente oferece orientação apoiada em documentos.

Processamento de Linguagem Natural, ou NLP, prepara essa base: limpa os textos, trata dados pessoais e organiza trechos com suas fontes.

Inteligência Generativa utiliza o conteúdo recuperado para elaborar a resposta com um modelo local. Na tela, podemos consultar as referências e conferir a orientação.

As duas disciplinas se complementam: uma organiza o conhecimento; a outra ajuda a transformá-lo em uma explicação para o usuário.”

## Áudio 06 — Automação com RPA

“Quando várias solicitações chegam juntas, o trabalho de organização também aumenta. A contribuição de AI for RPA é automatizar esse recebimento em lote.

O robô importa uma planilha, separa as entradas inválidas e encaminha as válidas para revisão. Cada item tem seu processamento registrado, e uma etapa pode ser retomada sem duplicar protocolos.

A aprovação continua necessária. Dessa forma, automatizamos tarefas repetitivas e preservamos a conferência que permite corrigir o registro antes de ele seguir no fluxo.”

## Áudio 07 — Análise de várias imagens

“A aplicação também permite analisar uma sequência de imagens. Cada foto passa pelo detector e apresenta seu próprio resultado, facilitando a comparação entre diferentes registros visuais.

Podemos observar onde o modelo encontrou uma possível ocorrência e onde sua sugestão precisa ser corrigida.

A análise fica separada do cadastro, permitindo explorar as imagens antes de compor um relato.”

## Áudio 08 — Reconhecimento de sons e relato sonoro

“Além da pavimentação, o Bairro em Dia ajuda a organizar relatos de incômodo sonoro. Na frente de IoT, o microfone funciona como sensor: o áudio captado pode ser enviado à plataforma, onde o YAMNet sugere o tipo de som.

Podemos analisar sons de ferramentas de obra e música, além de campainhas e batidas para acessibilidade. Aqui, mostramos uma análise real e vinculamos o resultado ao relato.

O morador informa o local, descreve o horário e o incômodo percebido e confere a sugestão antes do protocolo. Assim, a classificação ajuda a explicar o que foi ouvido, enquanto a revisão humana mantém o controle sobre o registro.”

## Áudio 09 — Cluster e Computação Quântica

“Para pensar na evolução da plataforma, também estudamos capacidade de processamento.

Em Cluster, simulamos no iSPD uma carga de cento e vinte tarefas. Ao passar de dois para quatro trabalhadores, o tempo simulado caiu de aproximadamente cento e oitenta para noventa segundos. Isso permite discutir distribuição de trabalho; não é uma medição de velocidade do aplicativo.

Em Computação Quântica, usamos medições clássicas do detector para estudar gargalos e propor caminhos futuros. A contribuição atual é esse estudo, sem execução ou vantagem quântica demonstrada.”

## Áudio 10 — Governança e encerramento

“Na disciplina de Governança em Inteligência Artificial e Business Analytics, transformamos princípios de responsabilidade em controles dentro da aplicação.

A IA analisa e sugere, mas a aprovação do registro depende de uma pessoa. Ela pode conferir, corrigir ou rejeitar a sugestão. Sem aprovação humana, o sistema bloqueia a emissão do protocolo, inclusive no processamento em lote.

Também implementamos o histórico das decisões e das mudanças de situação, permitindo acompanhar o que aconteceu com cada ocorrência. As orientações apresentam fontes para conferência, e os modelos têm avaliações e limitações documentadas.

Em Business Analytics, os gráficos e filtros ajudam a visualizar as demandas por categoria e situação.

O Bairro em Dia reúne tecnologia, participação humana e acompanhamento para apoiar o cuidado com o bairro, alinhado ao ODS onze: cidades e comunidades sustentáveis.”

## Direção de montagem — não narrar

1. Abertura: tela inicial, proposta e identificação do grupo; sem prometer categorias adicionais já implementadas.
2. Cadastro: foto pública, descrição e local confirmado; exibir detecções reais e identificar modelo externo.
3. Revisão: mostrar bloqueio antes da aprovação, decisão e protocolo SIM. Não sugerir envio a órgão público.
4. Acompanhamento: filtros e avanço real no gestor simulado; consultar o mesmo registro após a mudança. Usar legenda “Demonstração local — gestor simulado”.
5. Assistente: pergunta respondida com referências verificadas. Capturar resposta real; não apresentar modo alternativo como geração pelo LLM. Mostrar brevemente o tratamento de uma pergunta sem suporte documental.
6. RPA: lote de demonstração com entradas válidas e inválidas, revisão e retomada; identificar dados fictícios e aprovações de teste quando usados.
7. Sequência: mostrar resultados independentes, incluindo uma falha real documentada; não sugerir rastreamento de objetos ou criação automática de ocorrências.
8. Som: usar o áudio público creditado na demonstração. Mostrar classificação de música ou obra/ferramentas → Criar relato com esta análise → contexto/local/confirmação → revisão com análise vinculada. O horário é descrito no texto; `observed_at` é o horário de análise, não de captura. Manter legenda “Tipo de som sugerido — não mede decibéis”. Não sugerir teste físico de microfone/celular se a cena usa upload. Os três exemplos exploratórios tiveram duas correspondências exatas; a furadeira foi classificada de forma mais ampla como obra/ferramentas. Não prometer identificação garantida de ferramenta específica. Mostrar essa ressalva na evidência visual, sem reutilizar o resultado antigo de 3/4 como avaliação das novas categorias. As avaliações anteriores de acessibilidade permanecem separadas. Esta cena não substitui a entrega específica de IoT com Edge Impulse e celular. O bloco 08 foi atualizado para esta demonstração.
9. Cluster/Quântica: mostrar resultados e identificação inequívoca de simulação, medição clássica e proposta futura. Nenhum efeito visual deve sugerir processamento quântico real.
10. Governança e encerramento: acompanhar a fala com revisão e bloqueio de protocolo sem aprovação, decisão registrada, histórico de mudanças, fontes do assistente e gráficos por categoria/situação. Exibir a pendência de validação com pessoas na tela de próximos passos. A IA executa análises automaticamente; o controle humano obrigatório demonstrado é a aprovação antes do protocolo. Não afirmar que toda operação da IA exige aprovação prévia. Esta fala encerra o vídeo, não substitui a conclusão humana do relatório. Conferir a duração total com os novos áudios e ajustar a montagem para o limite de 7 minutos sem acelerar a voz.

Base factual: EVOLUCAO-PARA-COMPETICAO.md; evidências locais de integração e validação sonora. O ensaio técnico da nova jornada sonora está em ../front-end-mobile/evidencias/sound-journey-http-20261118.json; ainda é necessário capturar e revisar a demonstração visual atual para a montagem. O vídeo de Governança deve terminar entre 5 e 7 minutos. Os silêncios de margem podem ser cortados na edição, sem acelerar a voz.
