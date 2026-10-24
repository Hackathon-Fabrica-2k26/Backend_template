from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.alunos.views import (
    AlunoViewSet,
    ConsentimentoViewSet,
    MetaDadosViewSet,
    ResponsavelViewSet,
)
from apps.pedagogico.views.pei import AlunoRascunhoPEIPDFView, AlunoRascunhoPEIView
from apps.pedagogico.views.pontos_atencao import AlunoPontosAtencaoView

router = SimpleRouter()
router.register("alunos", AlunoViewSet, basename="aluno")
router.register("responsaveis", ResponsavelViewSet, basename="responsavel")
router.register("consentimentos", ConsentimentoViewSet, basename="consentimento")
router.register("meta-dados", MetaDadosViewSet, basename="meta-dados")

urlpatterns = [
    path(
        "alunos/<int:id>/pontos-atencao/",
        AlunoPontosAtencaoView.as_view(),
        name="aluno-pontos-atencao",
    ),
    path(
        "alunos/<int:id>/rascunho-pei/",
        AlunoRascunhoPEIView.as_view(),
        name="aluno-rascunho-pei",
    ),
    path(
        "alunos/<int:id>/rascunho-pei/pdf/",
        AlunoRascunhoPEIPDFView.as_view(),
        name="aluno-rascunho-pei-pdf",
    ),
] + router.urls
