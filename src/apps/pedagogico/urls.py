from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.pedagogico.views import AtividadeViewSet, RelatorioViewSet, TrabalhoViewSet
from apps.pedagogico.views.relatorio_gerar import RelatorioGerarView

router = SimpleRouter()
router.register("atividades", AtividadeViewSet, basename="atividade")
router.register("relatorios", RelatorioViewSet, basename="relatorio")
router.register("trabalhos", TrabalhoViewSet, basename="trabalho")

# Anteposta ao router para não ser interpretada como detail (pk="gerar").
urlpatterns = [
    path("relatorios/gerar/", RelatorioGerarView.as_view(), name="relatorio-gerar"),
] + router.urls
