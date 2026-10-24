"""Diagnóstico da integração com o Gemini, para rodar no servidor.

Uso: python src/manage.py diagnosticar_ia [--matricula U00001]

Mostra qual Config seria usada, se o servidor alcança a API do Google (rede/TLS)
e o resultado de uma chamada mínima ao modelo configurado. Nunca imprime a chave.
"""

import ssl
import urllib.error
import urllib.request

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.escolas.models import Config
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.services.llm import normalizar_modelo

URL_API = "https://generativelanguage.googleapis.com/"


class Command(BaseCommand):
    help = "Verifica Config, rede e uma chamada mínima ao Gemini (não imprime a chave)."

    def add_arguments(self, parser):
        parser.add_argument("--matricula", help="professor cuja escola/Config será usada")

    def handle(self, *args, **options):
        config = self._config(options.get("matricula"))
        chave = config.api_key.strip()
        modelo = normalizar_modelo(config.modelo)
        self.stdout.write(
            f"Config #{config.pk}: modelo='{modelo}', chave com {len(chave)} caracteres"
        )
        if not chave:
            raise CommandError("A Config não tem chave. Cadastre em /admin > Configs.")

        self._rede()
        self._modelo(chave, modelo)

    def _config(self, matricula):
        if matricula:
            user = get_user_model().objects.filter(matricula=matricula).first()
            if user is None:
                raise CommandError(f"Professor com matrícula {matricula} não encontrado.")
            escola = getattr(user, "escola", None)
            self.stdout.write(f"Professor {matricula}: escola={getattr(escola, 'nome', None)!r}")
            config = config_ia_do_usuario(user)
        else:
            config = Config.objects.exclude(api_key="").first()
        if config is None:
            raise CommandError(
                "Nenhuma Config com chave encontrada para este professor. "
                "Ligue a escola do professor a uma Config com chave no /admin."
            )
        return config

    def _rede(self):
        try:
            with urllib.request.urlopen(URL_API, timeout=10) as resp:
                status = resp.status
        except urllib.error.HTTPError as erro:
            status = erro.code  # 404 na raiz é esperado: a rede e o TLS funcionaram
        except (ssl.SSLError, urllib.error.URLError) as erro:
            raise CommandError(
                f"O servidor não alcança {URL_API}: {erro}. "
                "Se for erro de certificado, um proxy/firewall está interceptando o TLS; "
                "libere generativelanguage.googleapis.com na rede do servidor."
            ) from erro
        self.stdout.write(self.style.SUCCESS(f"Rede/TLS até a API do Google: ok (HTTP {status})"))

    def _modelo(self, chave, modelo):
        try:
            from google import genai

            cliente = genai.Client(api_key=chave)
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=['Responda apenas com o JSON {"ok": true}.'],
                config=genai.types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except Exception as erro:
            raise CommandError(
                f"Chamada ao modelo '{modelo}' falhou: {type(erro).__name__}: {erro}"
            ) from erro
        self.stdout.write(
            self.style.SUCCESS(f"Modelo '{modelo}' respondeu: {(resposta.text or '').strip()!r}")
        )
