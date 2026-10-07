from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from clinica.models import Cita, Especialidad, Mascota, Perfil

User = get_user_model()
CLAVE = "Demo12345!"


class Command(BaseCommand):
    help = "Carga datos de demostración (admin, veterinario, cliente, mascota y cita)."

    def handle(self, *args, **options):
        admin, creado = User.objects.get_or_create(
            username="admin_demo", defaults={"email": "admin@demo.cl", "is_staff": True, "is_superuser": True}
        )
        if creado:
            admin.set_password(CLAVE)
            admin.save()
        Perfil.objects.get_or_create(usuario=admin, defaults={"rol": Perfil.Rol.ADMIN})

        vet, creado = User.objects.get_or_create(username="vet_demo", defaults={"email": "vet@demo.cl"})
        if creado:
            vet.set_password(CLAVE)
            vet.save()
        perfil_vet, _ = Perfil.objects.get_or_create(usuario=vet, defaults={"rol": Perfil.Rol.VETERINARIO})
        esp, _ = Especialidad.objects.get_or_create(nombre="Medicina general", defaults={"descripcion": "Control y vacunas"})
        perfil_vet.especialidades.add(esp)

        cli, creado = User.objects.get_or_create(username="cliente_demo", defaults={"email": "cliente@demo.cl"})
        if creado:
            cli.set_password(CLAVE)
            cli.save()
        Perfil.objects.get_or_create(usuario=cli, defaults={"rol": Perfil.Rol.CLIENTE})

        mascota, _ = Mascota.objects.get_or_create(duenio=cli, nombre="Firulais", defaults={"especie": "PERRO", "raza": "Quiltro"})
        manana = (timezone.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        Cita.objects.get_or_create(mascota=mascota, veterinario=vet, fecha_hora=manana, defaults={"motivo": "Vacuna anual"})

        self.stdout.write(self.style.SUCCESS(
            f"Datos cargados. Usuarios: admin_demo / vet_demo / cliente_demo (clave: {CLAVE})"
        ))
