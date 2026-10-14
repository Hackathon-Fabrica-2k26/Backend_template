from django.db import transaction
from rest_framework import viewsets

from .models import Item
from .serializers import ItemSerializer
from .tasks import enfileirar_notificacao


class ItemViewSet(viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    filterset_fields = ["done"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Item.objects.none()
        return Item.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        item = serializer.save(owner=self.request.user)
        transaction.on_commit(lambda: enfileirar_notificacao(item.id))
