from rest_framework.routers import DefaultRouter

from apps.escolas.views import (
    ConfigViewSet,
    EscolaViewSet,
    TurmaViewSet,
)

router = DefaultRouter()
router.register("configs", ConfigViewSet, basename="config")
router.register("escolas", EscolaViewSet, basename="escola")
router.register("turmas", TurmaViewSet, basename="turma")

urlpatterns = router.urls