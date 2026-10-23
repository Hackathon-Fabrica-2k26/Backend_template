# pyright: reportIncompatibleVariableOverride=false
import factory
from django.contrib.auth import get_user_model

from apps.escolas.models import Config, Escola, Turma
from apps.items.models import Item

SENHA = "Senha-forte-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

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


class ConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Config

    api_key = factory.Sequence(lambda n: f"key-{n}")
    modelo = factory.Sequence(lambda n: f"modelo-{n}")
    campos_form = factory.LazyFunction(dict)


class EscolaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Escola

    nome = factory.Sequence(lambda n: f"Escola {n}")
    endereco = factory.Sequence(lambda n: f"Rua {n}")
    config = factory.SubFactory(ConfigFactory)


class TurmaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Turma
        skip_postgeneration_save = True

    nome = factory.Sequence(lambda n: f"Turma {n}")
    escola = factory.SubFactory(EscolaFactory)

    @factory.post_generation
    def professores(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for professor in extracted:
                self.professores.add(professor)
