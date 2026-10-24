from .atividade import AtividadeSerializer
from .envio_trabalhos import EnvioTrabalhosSerializer, TrabalhoUploadSerializer
from .relatorio import RelatorioSerializer
from .trabalho import TrabalhoPatchSerializer, TrabalhoSerializer

__all__ = [
    "AtividadeSerializer",
    "EnvioTrabalhosSerializer",
    "RelatorioSerializer",
    "TrabalhoPatchSerializer",
    "TrabalhoSerializer",
    "TrabalhoUploadSerializer",
]
