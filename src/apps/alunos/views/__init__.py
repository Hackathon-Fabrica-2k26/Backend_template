from .aluno import AlunoViewSet
from .codigo_acesso import AlunoCodigoAcessoRevogarView, AlunoCodigoAcessoView
from .consentimento import ConsentimentoViewSet
from .meta_dados import MetaDadosViewSet
from .responsavel import ResponsavelViewSet
from .responsavel_acesso import (
    ResponsavelAcessoView,
    ResponsavelAlunoView,
    ResponsavelConsentimentoRevogarView,
    ResponsavelConsentimentoView,
)

__all__ = [
    "AlunoCodigoAcessoRevogarView",
    "AlunoCodigoAcessoView",
    "AlunoViewSet",
    "ConsentimentoViewSet",
    "MetaDadosViewSet",
    "ResponsavelAcessoView",
    "ResponsavelAlunoView",
    "ResponsavelConsentimentoRevogarView",
    "ResponsavelConsentimentoView",
    "ResponsavelViewSet",
]
