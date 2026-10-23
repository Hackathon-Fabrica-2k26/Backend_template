from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

from core.views import health


@api_view(["GET"])
def api_root(request, format=None):
    return Response(
        {
            "items": reverse("item-list", request=request, format=format),
            "configs": reverse("config-list", request=request, format=format),
            "escolas": reverse("escola-list", request=request, format=format),
            "turmas": reverse("turma-list", request=request, format=format),
            "me": reverse("me", request=request, format=format),
            "login": reverse("login", request=request, format=format),
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
    path("api/", include("apps.items.urls")),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
