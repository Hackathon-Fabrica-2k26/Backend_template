from rest_framework.routers import SimpleRouter

from apps.escolas.views import (
    ConfigViewSet,
    EscolaViewSet,
    TurmaViewSet,
)

router = SimpleRouter()
router.register("configs", ConfigViewSet, basename="config")
router.register("escolas", EscolaViewSet, basename="escola")
router.register("turmas", TurmaViewSet, basename="turma")

urlpatterns = router.urls
