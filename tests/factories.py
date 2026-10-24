# pyright: reportIncompatibleVariableOverride=false
import os
from typing import cast

import factory
from django.contrib.auth import get_user_model

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.items.models import Item
from apps.pedagogico.models import Atividade, Relatorio

SENHA = os.getenv("SEED_DEMO_PASSWORD") or "Senha-forte-123"

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    matricula = factory.declarations.Sequence(lambda n: f"TESTE{n:06d}")
    email = factory.declarations.Sequence(lambda n: f"usuario{n}@example.com")
    name = factory.declarations.Sequence(lambda n: f"Usuário {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("password", SENHA)
        return model_class.objects.create_user(*args, **kwargs)

class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    title = factory.declarations.Sequence(lambda n: f"Item {n}")
    owner = factory.declarations.SubFactory(UserFactory)


class ConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Config

    api_key = factory.declarations.Sequence(lambda n: f"key-{n}")
    modelo = factory.declarations.Sequence(lambda n: f"modelo-{n}")
    campos_form = factory.declarations.LazyFunction(dict)


class EscolaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Escola

    nome = factory.declarations.Sequence(lambda n: f"Escola {n}")
    endereco = factory.declarations.Sequence(lambda n: f"Rua {n}")
    config = factory.declarations.SubFactory(ConfigFactory)


class TurmaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Turma
        skip_postgeneration_save = True

    nome = factory.declarations.Sequence(lambda n: f"Turma {n}")
    escola = factory.declarations.SubFactory(EscolaFactory)

    @factory.declarations.PostGeneration
    def professores(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            turma = cast(Turma, self)
            for professor in extracted:
                turma.professores.add(professor)


class ResponsavelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Responsavel

    nome = factory.declarations.Sequence(lambda n: f"Responsável {n}")
    email = factory.declarations.Sequence(lambda n: f"responsavel{n}@example.com")
    cpf = factory.declarations.Sequence(lambda n: f"1234567890{n % 9 + 1}")
    telefone = factory.declarations.Sequence(lambda n: f"1198765432{n % 9 + 1}")
    endereco = factory.declarations.Sequence(lambda n: f"Endereço {n}")


class MetaDadosFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetaDados

    perfil_disc = factory.declarations.Iterator(["D", "I", "S", "C"])
    caracteristicas = factory.declarations.LazyAttribute(lambda o: {})


class AlunoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Aluno

    nome = factory.declarations.Sequence(lambda n: f"Aluno {n}")
    turma = factory.declarations.SubFactory(TurmaFactory)


class RelatorioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Relatorio

    aluno = factory.declarations.SubFactory(AlunoFactory)
    dados = factory.declarations.LazyFunction(dict)


class AtividadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Atividade
        skip_postgeneration_save = True

    nome = factory.declarations.Sequence(lambda n: f"Atividade {n}")
    tipo = factory.declarations.Sequence(lambda n: f"Tipo {n}")
    aluno = factory.declarations.SubFactory(AlunoFactory)

    @factory.declarations.PostGeneration
    def relatorios(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            atividade = cast(Atividade, self)
            for relatorio in extracted:
                atividade.relatorios.add(relatorio)
