from rest_framework.routers import SimpleRouter

from apps.alunos.views import (
    AlunoViewSet,
    MetaDadosViewSet,
    ResponsavelViewSet,
)

router = SimpleRouter()
router.register("alunos", AlunoViewSet, basename="aluno")
router.register("responsaveis", ResponsavelViewSet, basename="responsavel")
router.register("meta-dados", MetaDadosViewSet, basename="meta-dados")

urlpatterns = router.urls
