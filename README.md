# Gestor de gastos (Telegram + Google Sheets)

Registra ingresos y gastos enviando mensajes a un bot de Telegram (`concepto importe [fecha]`). Sin LLM: parseo determinista.

## Uso
- `Cena -32,5` · `Nómina 1500 ayer` · `Gasolina -60 15/11` · `Alquiler -800 01/11/2026`
- `/resumen [mes] [año]` · `/grafico [mes] [año]` · `/ultimos [n]` · `/borrar <ID>` · `/borrar ultimo`
- Importe: coma o punto decimal; `1.500` = 1500 (punto de miles si van 3 cifras exactas).

## Puesta en marcha local
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env      # rellena los valores (nunca se sube al repo)
.\.venv\Scripts\python -m pytest
```
1. Crea el bot con @BotFather y obtén tu `user_id` (p. ej. @userinfobot).
2. Google Cloud: crea una cuenta de servicio, descarga su clave JSON y comparte la hoja con su email (Editor).
3. Carga las variables de `.env` en el entorno y ejecuta:
```powershell
.\.venv\Scripts\python scripts\setup_sheet.py          # crea Registro, Resumen, Categorías, Dashboard
$env:MODE="polling"; .\.venv\Scripts\python -m gastos_bot.main
```
`setup_sheet.py` es idempotente: no toca el Registro y reconstruye el Dashboard.

## Despliegue en Cloud Run (0 €, webhook)
```powershell
gcloud run deploy gastos-bot --source . --region europe-southwest1 `
  --min-instances 0 --max-instances 1 --concurrency 1 --memory 512Mi --cpu-throttling `
  --allow-unauthenticated --set-env-vars MODE=webhook `
  --set-secrets TELEGRAM_TOKEN=telegram-token:latest,WEBHOOK_SECRET=webhook-secret:latest,GOOGLE_SERVICE_ACCOUNT_JSON=sa-json:latest `
  --set-env-vars ALLOWED_USER_ID=...,SPREADSHEET_ID=...
$env:WEBHOOK_URL="https://<tu-servicio>.run.app"; python scripts\set_webhook.py set
```
Para mantener el coste en 0 €: crea una política de limpieza en Artifact Registry (conservar 2 imágenes), un presupuesto con alertas y revisa los límites vigentes del free tier antes de desplegar.

## Estructura
`src/gastos_bot/` (parser, formatting, categories, sheets/, services/, bot/, charts, webhook, main) · `scripts/` · `tests/`
