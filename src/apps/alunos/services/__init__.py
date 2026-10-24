from .consentimento import (
    alunos_com_consentimento,
    revogar_consentimento,
    tem_consentimento_ativo,
)
from .laudo import processar_laudo

__all__ = [
    "alunos_com_consentimento",
    "processar_laudo",
    "revogar_consentimento",
    "tem_consentimento_ativo",
]
