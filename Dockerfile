FROM python:3.11-slim

WORKDIR /app

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ .
COPY entrypoint.sh /entrypoint.sh

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app \
    && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
