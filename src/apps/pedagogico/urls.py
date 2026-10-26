from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.pedagogico.views import (
    AtividadeExtrairView,
    AtividadeVariacaoViewSet,
    AtividadeViewSet,
    HabilidadeListView,
    PerfilApoioViewSet,
    RelatorioViewSet,
    TrabalhoViewSet,
)
from apps.pedagogico.views.relatorio_gerar import RelatorioGerarView

router = SimpleRouter()
router.register("atividades", AtividadeViewSet, basename="atividade")
router.register("variacoes", AtividadeVariacaoViewSet, basename="variacao")
router.register("perfis-apoio", PerfilApoioViewSet, basename="perfil-apoio")
router.register("trabalhos", TrabalhoViewSet, basename="trabalho")
router.register("relatorios", RelatorioViewSet, basename="relatorio")

# Antepostas ao router para não serem interpretadas como detail (pk="extrair" / pk="gerar").
urlpatterns = [
    path("atividades/extrair/", AtividadeExtrairView.as_view(), name="atividade-extrair"),
    path("habilidades/", HabilidadeListView.as_view(), name="habilidades"),
    path("relatorios/gerar/", RelatorioGerarView.as_view(), name="relatorio-gerar"),
] + router.urls
