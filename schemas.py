from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class Criticidad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"

class EntidadesTecnicas(BaseModel):
    """Entidades técnicas extraídas de un texto."""

    es_texto_tecnico: bool = Field(
        ...,
        description="True solo si el texto describe sistemas, software, infraestructura o errores técnicos.",
    )
    tecnologias: list[str] = Field(
        default_factory=list,
        description="Tecnologías nombradas explícitamente en el texto. Lista vacía si no hay ninguna.",
    )
    nivel_de_criticidad: Criticidad = Field(
        ...,
        description="Criticidad del problema o sistema: baja, media o alta.",
    )
    resumen_tecnico: str = Field(
        ...,
        min_length=10,
        description="Resumen breve en una o dos oraciones.",
    )

    @field_validator("tecnologias")
    @classmethod
    def limpiar(cls, valores: list[str]) -> list[str]:
        return [v.strip() for v in valores if v and v.strip()]

    @model_validator(mode="after")
    def coherencia(self):
        # Si el texto no es técnico, no puede haber tecnologías: se normaliza, no se rechaza.
        if not self.es_texto_tecnico:
            self.tecnologias = []
        return self