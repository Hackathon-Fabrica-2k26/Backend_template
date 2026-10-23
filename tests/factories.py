# pyright: reportIncompatibleVariableOverride=false
import factory
from django.contrib.auth import get_user_model

from apps.alunos.models import Aluno, MetaDados, Responsavel
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


class ResponsavelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Responsavel

    nome = factory.Sequence(lambda n: f"Responsável {n}")
    email = factory.Sequence(lambda n: f"responsavel{n}@example.com")
    cpf = factory.Sequence(lambda n: f"1234567890{n % 9 + 1}")
    telefone = factory.Sequence(lambda n: f"1198765432{n % 9 + 1}")
    endereco = factory.Sequence(lambda n: f"Endereço {n}")


class MetaDadosFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetaDados

    perfil_disc = factory.Iterator(["D", "I", "S", "C"])
    caracteristicas = factory.LazyAttribute(lambda o: {})


class AlunoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Aluno

    nome = factory.Sequence(lambda n: f"Aluno {n}")
