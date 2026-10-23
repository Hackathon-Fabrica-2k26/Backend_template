from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.pedagogico.views import AtividadeViewSet, RelatorioViewSet
from apps.pedagogico.views.relatorio_gerar import RelatorioGerarView

router = SimpleRouter()
router.register("atividades", AtividadeViewSet, basename="atividade")
router.register("relatorios", RelatorioViewSet, basename="relatorio")

# Anteposta ao router para não ser interpretada como detail (pk="gerar").
urlpatterns = [
    path("relatorios/gerar/", RelatorioGerarView.as_view(), name="relatorio-gerar"),
] + router.urls
