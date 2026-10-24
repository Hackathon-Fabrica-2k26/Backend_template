from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.alunos.views import (
    AlunoCodigoAcessoRevogarView,
    AlunoCodigoAcessoView,
    AlunoViewSet,
    ConsentimentoViewSet,
    MetaDadosViewSet,
    ResponsavelAcessoView,
    ResponsavelAlunoView,
    ResponsavelConsentimentoRevogarView,
    ResponsavelConsentimentoView,
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
        "alunos/<int:id>/codigo-acesso/",
        AlunoCodigoAcessoView.as_view(),
        name="aluno-codigo-acesso",
    ),
    path(
        "alunos/<int:id>/codigo-acesso/revogar/",
        AlunoCodigoAcessoRevogarView.as_view(),
        name="aluno-codigo-acesso-revogar",
    ),
    path("responsavel/acesso/", ResponsavelAcessoView.as_view(), name="responsavel-acesso"),
    path("responsavel/aluno/", ResponsavelAlunoView.as_view(), name="responsavel-aluno"),
    path(
        "responsavel/consentimento/",
        ResponsavelConsentimentoView.as_view(),
        name="responsavel-consentimento",
    ),
    path(
        "responsavel/consentimento/revogar/",
        ResponsavelConsentimentoRevogarView.as_view(),
        name="responsavel-consentimento-revogar",
    ),
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
