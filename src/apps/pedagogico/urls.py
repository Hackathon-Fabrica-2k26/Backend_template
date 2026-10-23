from rest_framework.routers import SimpleRouter

from apps.pedagogico.views import AtividadeViewSet, RelatorioViewSet

router = SimpleRouter()
router.register("atividades", AtividadeViewSet, basename="atividade")
router.register("relatorios", RelatorioViewSet, basename="relatorio")

urlpatterns = router.urls
