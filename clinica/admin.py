from django.contrib import admin

from .models import Cita, Especialidad, Mascota, Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rol", "telefono")
    list_filter = ("rol",)
    filter_horizontal = ("especialidades",)


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "especie", "duenio")
    search_fields = ("nombre", "raza")


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("id", "mascota", "veterinario", "fecha_hora", "estado")
    list_filter = ("estado",)
