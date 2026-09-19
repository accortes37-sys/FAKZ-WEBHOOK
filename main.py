import os
import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO)

async def health(request):
    return web.json_response({"status": "online", "service": "FAKZ WEBHOOK"})

async def webhook(request):
    try:
        data = await request.json()
    except Exception:
        data = {"raw": await request.text()}

    logging.info("Webhook recebido: %s", data)
    return web.json_response({"received": True})

app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_post("/webhook", webhook)

port = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))
host = os.getenv("WEBHOOK_HOST", "0.0.0.0")

if __name__ == "__main__":
    web.run_app(app, host=host, port=port)