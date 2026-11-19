# Detector de pavimentação

Execute `python app/scripts/setup_vision.py` na raiz do repositório. O instalador baixa `best.onnx` da revisão fixada em `provenance.json` e verifica SHA-256 antes de gravar o arquivo. Os pesos não são versionados.

Modelo pré-treinado de [peterhdd/pothole-detection-yolov8](https://huggingface.co/peterhdd/pothole-detection-yolov8), com licença declarada Apache-2.0 no registro de procedência. Não foi treinado pelo grupo. A procedência de uma separação independente de treino e teste não foi estabelecida. Não representa um detector geral de problemas urbanos.
