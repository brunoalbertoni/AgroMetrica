import enum

from sqlalchemy import Enum


class Perfil(enum.StrEnum):
    ADMIN = "ADMIN"
    AGRONOMO = "AGRONOMO"


class Sistema(enum.StrEnum):
    AGRO_4_0 = "AGRO_4_0"
    CONVENCIONAL = "CONVENCIONAL"


class Finalidade(enum.StrEnum):
    GRAO = "GRAO"
    SILAGEM = "SILAGEM"


class TipoImagem(enum.StrEnum):
    FOLHA = "FOLHA"
    ORTOMOSAICO = "ORTOMOSAICO"
    NDVI_GEOTIFF = "NDVI_GEOTIFF"
    ARMADILHA = "ARMADILHA"


class StatusImagem(enum.StrEnum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    PROCESSADO = "PROCESSADO"
    ERRO = "ERRO"


class ClasseProduto(enum.StrEnum):
    INSETICIDA = "INSETICIDA"
    FUNGICIDA = "FUNGICIDA"
    HERBICIDA = "HERBICIDA"
    FERTILIZANTE = "FERTILIZANTE"
    CORRETIVO = "CORRETIVO"


class TipoDiagnostico(enum.StrEnum):
    PRAGA = "PRAGA"
    VIGOR = "VIGOR"
    NUTRICIONAL = "NUTRICIONAL"
    HIDRICO = "HIDRICO"


class Severidade(enum.StrEnum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class StatusPrescricao(enum.StrEnum):
    SUGERIDA = "SUGERIDA"
    APROVADA = "APROVADA"
    APLICADA = "APLICADA"
    DESCARTADA = "DESCARTADA"


class TipoUpload(enum.StrEnum):
    CLIMA = "CLIMA"
    SOLO = "SOLO"
    NDVI = "NDVI"
    COLHEITA = "COLHEITA"


def sa_enum(py_enum: type[enum.Enum]) -> Enum:
    """Enum do SQLAlchemy que grava o valor em texto: nativo no MySQL, CHECK no SQLite."""
    return Enum(py_enum, name=py_enum.__name__.lower(), values_callable=lambda e: [m.value for m in e])
