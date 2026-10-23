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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    EMAIL_FIELD = "email"

    objects = UserManager()  # pyright: ignore[reportAssignmentType]

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.email} - {self.name or 'Sem nome'}"
