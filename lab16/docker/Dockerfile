# ЛР16 · єдиний образ демонстратора (сервіси graph / api / ui відрізняються командою запуску).
# Контекст збірки — корінь Hub (docker-compose.yml: context: ..); що потрапляє в образ — див. Dockerfile.dockerignore.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 HUB_DENSE=0
WORKDIR /hub
COPY lab16/docker/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY . /hub
# непривілейований користувач; запис лише в журнали, том графа і службові теки агента
RUN useradd --create-home --uid 1000 hub \
 && mkdir -p /logs /data /hub/lab15/traces /hub/lab15/llm_log /hub/lab16/llm_log \
 && chown -R hub /logs /data /hub/lab15/traces /hub/lab15/llm_log /hub/lab16/llm_log
USER hub
EXPOSE 7878 8000 8501
CMD ["python", "lab16/api/app.py"]
