# YAMNet

Execute `python app/scripts/setup_yamnet.py --install-runtime --verify` na raiz. O modelo oficial Google YAMNet SavedModel, os arquivos auxiliares e o ambiente de áudio são instalados localmente. Arquivos são verificados por hashes fixados no código. A inferência é feita no servidor, com áudio WAV; nenhum áudio é enviado ao fornecedor do modelo pelo instalador ou pelo provedor.

Fonte: https://tfhub.dev/google/yamnet/1 — licença Apache-2.0 preservada em `LICENSE`. As 521 classes oficiais estão em `yamnet_class_map.csv`. O modelo não foi treinado pelo grupo. A verificação usa silêncio sintético e não mede acurácia. O TFLite baixado pelo instalador é uma referência de verificação; a inferência da aplicação usa SavedModel.
