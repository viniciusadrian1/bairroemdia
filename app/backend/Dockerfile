FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace/app
COPY app/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY app/requirements-audio.txt /tmp/requirements-audio.txt
RUN python -m venv /opt/yamnet && /opt/yamnet/bin/pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements-audio.txt
ENV YAMNET_PYTHON=/opt/yamnet/bin/python YAMNET_MODEL_PATH=/models/yamnet/saved_model YAMNET_LABELS_PATH=/models/yamnet/yamnet_class_map.csv
COPY app/backend ./backend
COPY app/resources ./resources
CMD ["python","-m","uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
