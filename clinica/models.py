from django.conf import settings
from django.db import models
from django.db.models import Q


class Especialidad(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "especialidades"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Perfil(models.Model):
    """Extiende al User de Django con un rol (relación One-to-One)."""

    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        VETERINARIO = "VETERINARIO", "Veterinario"
        CLIENTE = "CLIENTE", "Cliente"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    rol = models.CharField(max_length=15, choices=Rol.choices, default=Rol.CLIENTE)
    telefono = models.CharField(max_length=20, blank=True)
    # Many-to-Many: un veterinario puede tener varias especialidades y viceversa
    especialidades = models.ManyToManyField(
        Especialidad, blank=True, related_name="veterinarios"
    )

    def __str__(self):
        return f"{self.usuario.username} ({self.rol})"


class Mascota(models.Model):
    class Especie(models.TextChoices):
        PERRO = "PERRO", "Perro"
        GATO = "GATO", "Gato"
        AVE = "AVE", "Ave"
        ROEDOR = "ROEDOR", "Roedor"
        OTRO = "OTRO", "Otro"

    # One-to-Many: un dueño tiene muchas mascotas
    duenio = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mascotas"
    )
    nombre = models.CharField(max_length=60)
    especie = models.CharField(max_length=10, choices=Especie.choices, default=Especie.PERRO)
    raza = models.CharField(max_length=60, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.nombre} ({self.especie})"


class Cita(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        COMPLETADA = "COMPLETADA", "Completada"
        CANCELADA = "CANCELADA", "Cancelada"

    # One-to-Many: una mascota tiene muchas citas / un veterinario atiende muchas citas
    mascota = models.ForeignKey(Mascota, on_delete=models.CASCADE, related_name="citas")
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="citas_asignadas",
        limit_choices_to={"perfil__rol": "VETERINARIO"},
    )
    fecha_hora = models.DateTimeField()
    motivo = models.CharField(max_length=255)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_hora"]
        constraints = [
            # Un veterinario no puede tener dos citas activas a la misma hora
            models.UniqueConstraint(
                fields=["veterinario", "fecha_hora"],
                condition=~Q(estado="CANCELADA"),
                name="cita_unica_por_veterinario_y_hora",
            )
        ]

    def __str__(self):
        return f"Cita #{self.pk} - {self.mascota.nombre} - {self.fecha_hora:%d/%m/%Y %H:%M}"
