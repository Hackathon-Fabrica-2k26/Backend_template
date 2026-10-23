from django.contrib.auth.models import AbstractUser
from django.db import models

from ..managers import UserManager


class User(AbstractUser):
    """Usuário do sistema: login por e-mail, sem username.

    Adicione aqui os campos do domínio (perfil, tipo de usuário, matrícula, etc.).
    """

    username = None
    email = models.EmailField("e-mail", unique=True, db_index=True)
    name = models.CharField("nome", max_length=255, blank=True)
    ano = models.CharField("ano", max_length=45, blank=True)
    escola = models.ForeignKey(
        "escolas.Escola",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="professores",
    )

    matricula = models.CharField(max_length=100, unique=True)

    USERNAME_FIELD = "matricula"
    REQUIRED_FIELDS = ["name"]
    EMAIL_FIELD = "email"

    objects = UserManager()  # pyright: ignore[reportAssignmentType]

    class Meta(AbstractUser.Meta):
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.email} - {self.name or 'Sem nome'}"
