import os
import hmac
import hashlib
import logging
from aiohttp import web, ClientSession

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET")


async def health(request):
    return web.json_response({
        "status": "online",
        "service": "FAKZ WEBHOOK"
    })


def validar_assinatura(request):
    if not WEBHOOK_SECRET:
        logging.error("MERCADO_PAGO_WEBHOOK_SECRET não configurado")
        return False

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    data_id = request.query.get("data.id", "")

    if not x_signature or not x_request_id or not data_id:
        logging.warning("Dados necessários para validar assinatura ausentes")
        return False

    ts = None
    v1 = None

    for part in x_signature.split(","):
        key_value = part.split("=", 1)

        if len(key_value) != 2:
            continue

        key = key_value[0].strip()
        value = key_value[1].strip()

        if key == "ts":
            ts = value
        elif key == "v1":
            v1 = value

    if not ts or not v1:
        return False

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, v1)


async def consultar_pagamento(payment_id):
    if not ACCESS_TOKEN:
        logging.error("MERCADO_PAGO_ACCESS_TOKEN não configurado")
        return None

    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    async with ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            texto = await response.text()

            if response.status != 200:
                logging.error(
                    "Erro ao consultar pagamento %s: HTTP %s - %s",
                    payment_id,
                    response.status,
                    texto
                )
                return None

            return await response.json()


async def webhook(request):
    if not validar_assinatura(request):
        logging.warning("Webhook rejeitado: assinatura inválida")
        return web.json_response(
            {"error": "invalid signature"},
            status=401
        )

    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"error": "invalid json"},
            status=400
        )

    logging.info("Webhook Mercado Pago recebido: %s", data)

    if data.get("type") != "payment":
        return web.json_response({
            "received": True,
            "processed": False
        })

    payment_id = data.get("data", {}).get("id")

    if not payment_id:
        logging.warning("Webhook sem ID do pagamento")
        return web.json_response({
            "received": True,
            "processed": False
        })

    pagamento = await consultar_pagamento(payment_id)

    if not pagamento:
        return web.json_response({
            "received": True,
            "processed": False
        })

    status = pagamento.get("status")
    status_detail = pagamento.get("status_detail")
    valor = pagamento.get("transaction_amount")
    external_reference = pagamento.get("external_reference")

    logging.info("========== PAGAMENTO ==========")
    logging.info("ID: %s", pagamento.get("id"))
    logging.info("Status: %s", status)
    logging.info("Detalhe: %s", status_detail)
    logging.info("Valor: %s", valor)
    logging.info("External Reference: %s", external_reference)
    logging.info("===============================")

    if status == "approved":
        logging.info("PAGAMENTO APROVADO")

    return web.json_response({
        "received": True,
        "processed": True,
        "payment_id": pagamento.get("id"),
        "status": status
    })


app = web.Application()

app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_post("/webhook", webhook)

port = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))
host = os.getenv("WEBHOOK_HOST", "0.0.0.0")

if __name__ == "__main__":
    web.run_app(app, host=host, port=port)
