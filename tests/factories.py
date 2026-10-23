# pyright: reportIncompatibleVariableOverride=false
import factory
from django.contrib.auth import get_user_model

from apps.items.models import Item

SENHA = "Senha-forte-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    matricula = factory.Sequence(lambda n: f"TESTE{n:06d}")
    email = factory.Sequence(lambda n: f"usuario{n}@example.com")
    name = factory.Sequence(lambda n: f"Usuário {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("password", SENHA)
        return model_class.objects.create_user(*args, **kwargs)

class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    title = factory.Sequence(lambda n: f"Item {n}")
    owner = factory.SubFactory(UserFactory)
