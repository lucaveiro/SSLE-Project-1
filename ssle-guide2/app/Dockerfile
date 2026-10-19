# Um só Dockerfile, uma imagem por serviço:
#   docker build --build-arg SERVICE=ingestion -t ssle/ingestion:v1 .
FROM python:3.13-slim

ARG SERVICE
RUN test -n "$SERVICE" || (echo "Falta --build-arg SERVICE=<nome>" && false)

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cada imagem só leva o common.py e o código do SEU serviço
COPY common.py ${SERVICE}.py ./

RUN useradd -r -u 10001 appuser
USER 10001

ENV SERVICE=${SERVICE} \
    BIND_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

# exec -> o Python fica como PID 1 e recebe o SIGTERM (desregisto limpo no registry)
CMD ["sh", "-c", "exec python ${SERVICE}.py"]
