import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def notificar_item_criado(item_id):
    """Exemplo de tarefa em segundo plano. Troque por envio de e-mail, webhook, etc."""
    logger.info("Item %s criado", item_id)
    return item_id


def enfileirar_notificacao(item_id):
    """Enfileira a notificação sem derrubar a requisição se o broker estiver fora do ar."""
    try:
        notificar_item_criado.delay(item_id)  # pyright: ignore[reportFunctionMemberAccess]
    except Exception:
        logger.exception("Não foi possível enfileirar a notificação do item %s", item_id)
