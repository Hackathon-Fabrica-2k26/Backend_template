from .atividade import AtividadeSerializer
from .envio_trabalhos import EnvioTrabalhosSerializer, EnvioTrabalhosUploadSerializer
from .perfil_apoio import PerfilApoioSerializer
from .relatorio import RelatorioSerializer
from .trabalho import TrabalhoConfirmacaoSerializer, TrabalhoSerializer
from .variacao import AtividadeVariacaoSerializer

__all__ = [
    "AtividadeSerializer",
    "AtividadeVariacaoSerializer",
    "EnvioTrabalhosSerializer",
    "EnvioTrabalhosUploadSerializer",
    "PerfilApoioSerializer",
    "RelatorioSerializer",
    "TrabalhoConfirmacaoSerializer",
    "TrabalhoSerializer",
]
