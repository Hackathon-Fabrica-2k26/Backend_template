from .aluno import AlunoViewSet
from .consentimento import ConsentimentoViewSet
from .laudo import AlunoLaudoView
from .meta_dados import MetaDadosViewSet
from .responsavel import ResponsavelViewSet

__all__ = [
    "AlunoLaudoView",
    "AlunoViewSet",
    "ConsentimentoViewSet",
    "MetaDadosViewSet",
    "ResponsavelViewSet",
]
