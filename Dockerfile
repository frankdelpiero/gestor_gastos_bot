FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl \
    MODE=webhook PORT=8080
COPY --from=builder /install /usr/local
WORKDIR /app
COPY src ./src
ENV PYTHONPATH=/app/src
RUN useradd -m bot
USER bot
EXPOSE 8080
CMD ["python", "-m", "gastos_bot.main"]
