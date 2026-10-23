"""Comando customizado para popular o banco de dados (Database Seeding).

Uso:
    pdm run populate
    python src/manage.py seed_db
    python src/manage.py seed_db --clear
    python src/manage.py seed_db --users 10 --alunos-por-turma 5
    python src/manage.py seed_db --count 20

Idempotente: executar múltiplas vezes sem a flag --clear não duplica dados nem viola constraints.
Com a flag --clear: limpa as tabelas de forma segura antes de recriar os registros.
"""

import os
from collections import defaultdict
from itertools import cycle

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker
from safedelete.models import HARD_DELETE

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.items.models import Item
from apps.pedagogico.models import Atividade, Relatorio

User = get_user_model()


class Command(BaseCommand):
    help = "Popula o banco de dados com dados essenciais e mockados realistas (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Limpa os registros antes de semear novos dados.",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=5,
            help="Quantidade de usuários comuns/professores a criar (padrão: 5).",
        )
        parser.add_argument(
            "--escolas",
            type=int,
            default=2,
            help="Quantidade de escolas a criar (padrão: 2).",
        )
        parser.add_argument(
            "--turmas-por-escola",
            type=int,
            default=2,
            help="Quantidade de turmas por escola (padrão: 2).",
        )
        parser.add_argument(
            "--alunos-por-turma",
            type=int,
            default=4,
            help="Quantidade de alunos por turma (padrão: 4).",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=None,
            help="Volume base geral para registros mockados (sobrescreve contagens padrão).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker("pt_BR")
        Faker.seed(42)

        should_clear = options["clear"]
        users_count = options["users"]
        escolas_count = options["escolas"]
        turmas_per_escola = options["turmas_por_escola"]
        alunos_per_turma = options["alunos_por_turma"]

        if options["count"] is not None:
            base_count = max(1, options["count"])
            users_count = base_count
            alunos_per_turma = max(2, base_count // 2)

        self.stdout.write(self.style.MIGRATE_HEADING("=== Iniciando Database Seeding ==="))

        if should_clear:
            self._clear_database()

        stats = defaultdict(lambda: {"criados": 0, "existentes": 0})

        # 1. Superusuário
        _admin_user, admin_created = self._seed_superuser()
        if admin_created:
            stats["Superusuários"]["criados"] += 1
        else:
            stats["Superusuários"]["existentes"] += 1

        # 2. Catálogo / Domínio Fixo (Configurações de IA)
        config, config_created = Config.objects.get_or_create(
            modelo="gemini-2.5-flash",
            defaults={
                "api_key": "seed-api-key-desenvolvimento",
                "campos_form": {
                    "criterios": ["foco", "social", "raciocinio", "sensorial", "motor"],
                    "versao_form": "1.0",
                },
            },
        )
        if config_created:
            stats["Configurações"]["criados"] += 1
        else:
            stats["Configurações"]["existentes"] += 1

        # 3. Escolas
        escolas = []
        for i in range(1, escolas_count + 1):
            nome_escola = f"Escola Modelo {i:02d}"
            endereco_escola = f"Avenida da Educação, {100 * i}, Bairro Universitário"
            escola, created = Escola.objects.get_or_create(
                nome=nome_escola,
                defaults={
                    "endereco": endereco_escola,
                    "config": config,
                },
            )
            if created:
                stats["Escolas"]["criados"] += 1
            else:
                stats["Escolas"]["existentes"] += 1
            escolas.append(escola)

        # 4. Usuários Comuns / Professores
        professores = []
        senha_padrao_prof = os.getenv("SEED_USER_PASSWORD", "senha123")
        escola_cycle = cycle(escolas)

        for i in range(1, users_count + 1):
            matricula = f"PROF{i:04d}"
            email = f"professor{i}@exemplo.com"
            escola_alocada = next(escola_cycle)

            user, created = User.objects.get_or_create(
                matricula=matricula,
                defaults={
                    "email": email,
                    "name": f"Professor {fake.first_name()} {fake.last_name()}",
                    "ano": f"{(i % 5) + 1}º ano",
                    "escola": escola_alocada,
                },
            )
            if created:
                user.set_password(senha_padrao_prof)
                user.save()
                stats["Usuários/Professores"]["criados"] += 1
            else:
                stats["Usuários/Professores"]["existentes"] += 1

            professores.append(user)

        # 5. Turmas
        turnos = cycle([
            Turma.TurnoChoices.MANHA,
            Turma.TurnoChoices.TARDE,
            Turma.TurnoChoices.INTEGRAL,
        ])
        letras_turmas = ["A", "B", "C", "D", "E"]
        turmas = []
        prof_index = 0

        for escola in escolas:
            for t_idx in range(turmas_per_escola):
                letra = letras_turmas[t_idx % len(letras_turmas)]
                nome_turma = f"Turma {letra} - {escola.nome}"
                turno = next(turnos)

                turma, created = Turma.objects.get_or_create(
                    nome=nome_turma,
                    escola=escola,
                    defaults={"turno": turno},
                )
                if created:
                    stats["Turmas"]["criados"] += 1
                else:
                    stats["Turmas"]["existentes"] += 1

                # Vincula pelo menos um professor
                if professores:
                    prof_alocado = professores[prof_index % len(professores)]
                    turma.professores.add(prof_alocado)
                    prof_index += 1

                turmas.append(turma)

        # 6. Alunos, Responsáveis, MetaDados DISC, Relatórios e Atividades
        perfis_disc = cycle(["D", "I", "S", "C"])
        aluno_seq = 1

        for turma in turmas:
            for _ in range(alunos_per_turma):
                # Responsável
                resp_email = f"responsavel{aluno_seq}@exemplo.com"
                resp_cpf = f"{30000000000 + aluno_seq:011d}"[:11]
                responsavel, r_created = Responsavel.objects.get_or_create(
                    email=resp_email,
                    defaults={
                        "nome": f"Responsável {fake.name()}",
                        "cpf": resp_cpf,
                        "telefone": f"1198{aluno_seq:07d}"[:11],
                        "endereco": f"Rua das Acácias, {10 + aluno_seq}",
                    },
                )
                if r_created:
                    stats["Responsáveis"]["criados"] += 1
                else:
                    stats["Responsáveis"]["existentes"] += 1

                perfil = next(perfis_disc)

                # Aluno
                nome_aluno = f"Aluno {fake.first_name()} {chr(65 + (aluno_seq % 26))}"
                aluno, a_created = Aluno.objects.get_or_create(
                    nome=nome_aluno,
                    turma=turma,
                    defaults={
                        "responsavel": responsavel,
                    },
                )
                if a_created:
                    stats["Alunos"]["criados"] += 1
                else:
                    stats["Alunos"]["existentes"] += 1

                if aluno.responsavel != responsavel:
                    aluno.responsavel = responsavel

                # MetaDados DISC (OneToOneField com Aluno)
                if aluno.meta_dados is None:
                    meta_dados = MetaDados.objects.create(
                        perfil_disc=perfil,
                        caracteristicas=self._gerar_caracteristicas_disc(perfil),
                    )
                    aluno.meta_dados = meta_dados
                    aluno.save()
                    stats["MetaDados DISC"]["criados"] += 1
                else:
                    meta_dados = aluno.meta_dados
                    perfil = meta_dados.perfil_disc or perfil
                    stats["MetaDados DISC"]["existentes"] += 1

                # Relatório Diagnóstico (1 por aluno para manter realista)
                if not aluno.relatorios.exists():
                    relatorio_dados = self._gerar_dados_relatorio(aluno.nome, perfil)
                    relatorio = Relatorio.objects.create(
                        aluno=aluno,
                        dados=relatorio_dados,
                    )
                    stats["Relatórios"]["criados"] += 1
                else:
                    relatorio = aluno.relatorios.first()
                    stats["Relatórios"]["existentes"] += 1

                # Atividade pedagógica adaptada
                atividade, ativ_created = Atividade.objects.get_or_create(
                    nome=f"Atividade Adaptada {perfil} - {aluno.nome}",
                    aluno=aluno,
                    defaults={"tipo": f"Reforço Perfil {perfil}"},
                )
                if ativ_created:
                    atividade.relatorios.add(relatorio)
                    stats["Atividades"]["criados"] += 1
                else:
                    stats["Atividades"]["existentes"] += 1

                aluno_seq += 1

        # 7. Itens mockados para usuários
        for prof in professores:
            item, item_created = Item.objects.get_or_create(
                title=f"Plano de Aula Semanal - {prof.name}",
                owner=prof,
                defaults={
                    "description": (
                        "Elaboração de dinâmicas inclusivas baseadas no perfil dos alunos."
                    ),
                    "done": False,
                },
            )
            if item_created:
                stats["Itens"]["criados"] += 1
            else:
                stats["Itens"]["existentes"] += 1

        # Resumo final
        self._exibir_resumo(stats)

    def _clear_database(self):
        self.stdout.write(self.style.WARNING("Limpando dados antigos com exclusão permanente..."))
        Atividade.all_objects.all().delete(force_policy=HARD_DELETE)
        Relatorio.all_objects.all().delete(force_policy=HARD_DELETE)
        Aluno.all_objects.all().delete(force_policy=HARD_DELETE)
        MetaDados.all_objects.all().delete(force_policy=HARD_DELETE)
        Responsavel.all_objects.all().delete(force_policy=HARD_DELETE)
        Turma.all_objects.all().delete(force_policy=HARD_DELETE)
        Escola.all_objects.all().delete(force_policy=HARD_DELETE)
        Config.all_objects.all().delete(force_policy=HARD_DELETE)
        Item.all_objects.all().delete(force_policy=HARD_DELETE)
        User.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Banco de dados limpo com sucesso!"))

    def _seed_superuser(self):
        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@exemplo.com")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
        admin_matricula = "ADMIN0001"

        user = User.objects.filter(matricula=admin_matricula).first()
        if not user:
            user = User.objects.filter(email=admin_email).first()

        if user:
            user.is_staff = True
            user.is_superuser = True
            user.set_password(admin_password)
            user.save()
            return user, False

        user = User.objects.create_superuser(
            matricula=admin_matricula,
            email=admin_email,
            password=admin_password,
            name="Administrador Padrão",
        )
        return user, True

    def _gerar_caracteristicas_disc(self, perfil):
        mapa = {
            "D": {"estilo": "Objetivo e direto", "motivacao": "Desafios e metas"},
            "I": {"estilo": "Comunicativo e criativo", "motivacao": "Reconhecimento e grupos"},
            "S": {"estilo": "Paciente e colaborativo", "motivacao": "Segurança e rotina"},
            "C": {"estilo": "Analítico e detalhista", "motivacao": "Qualidade e precisão"},
        }
        return mapa.get(perfil, {"estilo": "Versátil", "motivacao": "Aprendizado contínuo"})

    def _gerar_dados_relatorio(self, nome_aluno, perfil):
        perfis_radar = {
            "D": {
                "foco_sustentado": 75,
                "raciocinio_visual": 80,
                "interacao_social": 85,
                "regulacao_sensorial": 70,
                "coordenacao_fina": 65,
            },
            "I": {
                "foco_sustentado": 60,
                "raciocinio_visual": 85,
                "interacao_social": 95,
                "regulacao_sensorial": 60,
                "coordenacao_fina": 70,
            },
            "S": {
                "foco_sustentado": 80,
                "raciocinio_visual": 70,
                "interacao_social": 75,
                "regulacao_sensorial": 85,
                "coordenacao_fina": 75,
            },
            "C": {
                "foco_sustentado": 90,
                "raciocinio_visual": 85,
                "interacao_social": 60,
                "regulacao_sensorial": 75,
                "coordenacao_fina": 85,
            },
        }
        radar = perfis_radar.get(perfil, perfis_radar["I"])

        return {
            "profile_summary": (
                f"Perfil comportamental {perfil} de {nome_aluno}, "
                "com forte engajamento em atividades estruturadas."
            ),
            "radar_metrics": radar,
            "strengths": [
                f"Capacidade de resposta rápida alinhada ao perfil {perfil}",
                "Excelente cooperação nas instruções orientadas pelo professor",
            ],
            "support_needs": [
                "Manutenção de previsibilidade e orientações visuais claras",
                "Estímulo com pausas ativas regulares",
            ],
            "adapted_activities": [
                {
                    "title": f"Desafio Pedagógico Adaptado ({perfil})",
                    "objective": "Desenvolver foco e interação através de resolução colaborativa.",
                    "duration": "15 minutos",
                    "instructions": "O estudante atua em etapa chave do projeto de aprendizagem.",
                    "inclusive_tip": (
                        "Permitir rotação de papéis no grupo para fortalecer a integração."
                    ),
                }
            ],
            "autonomy_coaching_tip": (
                "Estimule o aluno a liderar a verificação de conclusão de sua própria atividade."
            ),
        }

    def _exibir_resumo(self, stats):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Relatório de Povoamento do Banco de Dados ==="))
        self.stdout.write(f"{'Entidade':<25} | {'Novos':<8} | {'Existentes':<10}")
        self.stdout.write("-" * 50)
        for entidade, dados in stats.items():
            self.stdout.write(
                f"{entidade:<25} | {dados['criados']:<8} | {dados['existentes']:<10}"
            )
        self.stdout.write("-" * 50)

        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@exemplo.com")
        admin_pass = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
        prof_pass = os.getenv("SEED_USER_PASSWORD", "senha123")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Credenciais de Teste Geradas:"))
        self.stdout.write(
            f"  • Superusuário: {admin_email} (Matrícula: ADMIN0001) / Senha: {admin_pass}"
        )
        self.stdout.write(
            f"  • Professores: professor1@exemplo.com (Matrícula: PROF0001) / Senha: {prof_pass}"
        )
        self.stdout.write(self.style.SUCCESS("✓ Database seeding finalizado com sucesso!"))
