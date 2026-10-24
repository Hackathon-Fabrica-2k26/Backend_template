from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """Manager para usuários autenticados por matrícula."""

    use_in_migrations = True

    def _create_user(self, matricula, email, password, **extra_fields):
        if not matricula:
            raise ValueError("A matrícula é obrigatória.")
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        if not password:
            raise ValueError("A senha é obrigatória.")

        email = self.normalize_email(email)

        user = self.model(
            matricula=matricula,
            email=email,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, matricula=None, email=None, password=None, **extra_fields):
        if matricula is None:
            matricula = extra_fields.pop("username", None)
        if email is None:
            raise ValueError("O e-mail é obrigatório.")
        if password is None:
            raise ValueError("A senha é obrigatória.")

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if extra_fields["is_staff"] is True:
            raise ValueError("Usuário comum não pode ter is_staff=True.")
        if extra_fields["is_superuser"] is True:
            raise ValueError("Usuário comum não pode ter is_superuser=True.")
        return self._create_user(matricula, email, password, **extra_fields)

    def create_superuser(self, matricula=None, email=None, password=None, **extra_fields):
        if matricula is None:
            matricula = extra_fields.pop("username", None)
        if email is None:
            raise ValueError("O e-mail é obrigatório.")
        if password is None:
            raise ValueError("A senha é obrigatória.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")
        return self._create_user(matricula, email, password, **extra_fields)
