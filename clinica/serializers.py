import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import serializers

from .models import Cita, Especialidad, Mascota, Perfil
from .permissions import CLIENTE, VETERINARIO, obtener_rol

User = get_user_model()

TELEFONO_RE = re.compile(r"^\+?[0-9 ]{7,20}$")


def limpiar_texto(valor, campo="Este campo"):
    """Sanitiza texto: elimina etiquetas HTML y espacios sobrantes."""
    limpio = strip_tags(valor).strip()
    if not limpio:
        raise serializers.ValidationError(f"{campo} no puede estar vacío ni contener solo HTML.")
    return limpio


# ---------------------------------------------------------------- Usuarios
class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})
    telefono = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=20
    )
    rol = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "password2", "telefono", "rol"]
        read_only_fields = ["id"]
        extra_kwargs = {"email": {"required": True, "allow_blank": False}}

    def get_rol(self, obj):
        return obj.perfil.rol

    def validate_username(self, value):
        if len(value) < 4:
            raise serializers.ValidationError("El usuario debe tener al menos 4 caracteres.")
        return value

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def validate_telefono(self, value):
        if value and not TELEFONO_RE.match(value):
            raise serializers.ValidationError(
                "Teléfono inválido. Use solo números, espacios y un '+' inicial opcional."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        try:
            validate_password(
                attrs["password"], user=User(username=attrs["username"], email=attrs["email"])
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password2")
        telefono = validated_data.pop("telefono", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        # El rol NUNCA viene del cliente: todo registro público es CLIENTE
        Perfil.objects.create(usuario=user, rol=Perfil.Rol.CLIENTE, telefono=telefono)
        return user


class EspecialidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Especialidad
        fields = ["id", "nombre", "descripcion"]

    def validate_nombre(self, value):
        value = limpiar_texto(value, "El nombre")
        if len(value) < 3:
            raise serializers.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return value

    def validate_descripcion(self, value):
        return strip_tags(value).strip()


class PerfilSerializer(serializers.ModelSerializer):
    usuario = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source="usuario.username", read_only=True)
    email = serializers.EmailField(source="usuario.email", read_only=True)
    especialidades = EspecialidadSerializer(many=True, read_only=True)

    class Meta:
        model = Perfil
        fields = ["id", "usuario", "username", "email", "rol", "telefono", "especialidades"]
        read_only_fields = fields


# ---------------------------------------------------------------- Mascotas
class MascotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mascota
        fields = ["id", "nombre", "especie", "raza", "fecha_nacimiento", "duenio", "creada_en"]
        read_only_fields = ["id", "duenio", "creada_en"]

    def validate_nombre(self, value):
        value = limpiar_texto(value, "El nombre")
        if len(value) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return value

    def validate_raza(self, value):
        return strip_tags(value).strip()

    def validate_fecha_nacimiento(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("La fecha de nacimiento no puede ser futura.")
        return value


# ------------------------------------------------------------------- Citas
class CitaSerializer(serializers.ModelSerializer):
    veterinario = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(perfil__rol=VETERINARIO)
    )
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)
    veterinario_nombre = serializers.CharField(source="veterinario.username", read_only=True)

    class Meta:
        model = Cita
        fields = [
            "id", "mascota", "mascota_nombre", "veterinario", "veterinario_nombre",
            "fecha_hora", "motivo", "estado", "creada_en",
        ]
        read_only_fields = ["id", "creada_en"]

    @property
    def _usuario(self):
        return self.context["request"].user

    def validate_mascota(self, value):
        if obtener_rol(self._usuario) == CLIENTE and value.duenio_id != self._usuario.id:
            raise serializers.ValidationError("Solo puedes agendar citas para tus mascotas.")
        return value

    def validate_fecha_hora(self, value):
        cambio = self.instance is None or value != self.instance.fecha_hora
        if cambio and value <= timezone.now():
            raise serializers.ValidationError("La fecha de la cita debe ser futura.")
        return value

    def validate_motivo(self, value):
        value = limpiar_texto(value, "El motivo")
        if len(value) < 5:
            raise serializers.ValidationError("Describe el motivo con al menos 5 caracteres.")
        return value

    def validate_estado(self, value):
        if obtener_rol(self._usuario) == CLIENTE and value != Cita.Estado.CANCELADA:
            raise serializers.ValidationError("Un cliente solo puede cancelar su cita.")
        return value

    def validate(self, attrs):
        rol = obtener_rol(self._usuario)

        # El veterinario solo puede cambiar el estado de la cita
        if rol == VETERINARIO and self.instance is not None:
            extras = set(self.initial_data.keys()) - {"estado"}
            if extras:
                raise serializers.ValidationError(
                    {"detail": "El veterinario solo puede modificar el estado de la cita."}
                )

        # Un veterinario no puede tener dos citas activas a la misma hora
        veterinario = attrs.get("veterinario", getattr(self.instance, "veterinario", None))
        fecha_hora = attrs.get("fecha_hora", getattr(self.instance, "fecha_hora", None))
        if self.instance is None:
            estado = Cita.Estado.PENDIENTE  # toda cita nueva nace pendiente
        else:
            estado = attrs.get("estado", self.instance.estado)
        if veterinario and fecha_hora and estado != Cita.Estado.CANCELADA:
            choque = Cita.objects.filter(veterinario=veterinario, fecha_hora=fecha_hora).exclude(
                estado=Cita.Estado.CANCELADA
            )
            if self.instance is not None:
                choque = choque.exclude(pk=self.instance.pk)
            if choque.exists():
                raise serializers.ValidationError(
                    {"fecha_hora": "El veterinario ya tiene una cita a esa hora."}
                )
        return attrs
