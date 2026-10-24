from django.contrib import admin
from django.urls import include, path
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

from core.views import health


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def api_root(request, format=None):
    return Response(
        {
            "items": reverse("item-list", request=request, format=format),
            "configs": reverse("config-list", request=request, format=format),
            "escolas": reverse("escola-list", request=request, format=format),
            "turmas": reverse("turma-list", request=request, format=format),
            "chamada-reconhecer": reverse("chamada-reconhecer", request=request, format=format),
            "alunos": reverse("aluno-list", request=request, format=format),
            "aluno-pontos-atencao": (
                f"{reverse('aluno-list', request=request, format=format)}{{id}}/pontos-atencao/"
            ),
            "aluno-rascunho-pei": (
                f"{reverse('aluno-list', request=request, format=format)}{{id}}/rascunho-pei/"
            ),
            "aluno-rascunho-pei-pdf": (
                f"{reverse('aluno-list', request=request, format=format)}{{id}}/rascunho-pei/pdf/"
            ),
            "responsaveis": reverse("responsavel-list", request=request, format=format),
            "consentimentos": reverse("consentimento-list", request=request, format=format),
            "meta-dados": reverse("meta-dados-list", request=request, format=format),
            "atividades": reverse("atividade-list", request=request, format=format),
            "atividades-extrair": reverse("atividade-extrair", request=request, format=format),
            "variacoes": reverse("variacao-list", request=request, format=format),
            "perfis-apoio": reverse("perfil-apoio-list", request=request, format=format),
            "trabalhos": reverse("trabalho-list", request=request, format=format),
            "relatorios": reverse("relatorio-list", request=request, format=format),
            "relatorios-gerar": reverse("relatorio-gerar", request=request, format=format),
            "me": reverse("me", request=request, format=format),
            "login": reverse("login", request=request, format=format),
            "otp-verify": reverse("otp-verify", request=request, format=format),
            "otp-resend": reverse("otp-resend", request=request, format=format),
            "register": reverse("register", request=request, format=format),
            "refresh": reverse("refresh", request=request, format=format),
            "docs": reverse("docs", request=request, format=format),
        }
    )


urlpatterns = [
    path("health/", health, name="health"),
    path("api/", api_root, name="api-root"),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.escolas.urls")),
    path("api/", include("apps.alunos.urls")),
    path("api/", include("apps.pedagogico.urls")),
    path("api/", include("apps.items.urls")),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
