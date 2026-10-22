import asyncio
import logging
import os

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from schemas import EntidadesTecnicas
import warnings
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("pipeline")

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-5-5",
    "gemini": "gemini-3.5-flash-lite",
}


def get_model():
    """Crea el modelo de LangChain según LLM_PROVIDER (misma idea que el Módulo 1)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"Proveedor no soportado: {provider}")

    model_name = os.getenv(f"{provider.upper()}_MODEL") or DEFAULT_MODELS[provider]
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    logger.info("Proveedor=%s | modelo=%s", provider, model_name)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, temperature=temperature, max_tokens=max_tokens)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_name, temperature=temperature, max_tokens=max_tokens)

    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        max_output_tokens=max_tokens,
        google_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
    )


# 1) Prompt modular: LangChain gestiona {text}, sin f-strings
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un extractor de entidades técnicas. Analiza el texto del usuario y "
            "devuelve: las tecnologías mencionadas, el nivel de criticidad "
            "(baja, media o alta) y un resumen técnico breve en español. "
            "Incluye SOLO tecnologías, lenguajes, frameworks o servicios nombrados "
            "explícitamente en el texto. Si no hay ninguna, devuelve la lista vacía; "
            "no inventes ni uses términos genéricos.",
        ),
        ("human", "Texto a analizar:\n{text}"),
    ]
)

# 2) Salida estructurada.
# Variante de: chain = prompt | model.with_structured_output(Schema)
# include_raw=True permite leer el finish_reason antes de aceptar el objeto.
structured_model = get_model().with_structured_output(EntidadesTecnicas, include_raw=True)

# Valores de corte por límite de tokens: Gemini, OpenAI y Anthropic
TRUNCADO = {"MAX_TOKENS", "length", "max_tokens"}


def validar_resultado(resultado: dict) -> EntidadesTecnicas:
    """Detecta respuestas truncadas o mal formadas. Si lanza error, with_retry reintenta."""
    meta = resultado["raw"].response_metadata
    finish_reason = meta.get("finish_reason") or meta.get("stop_reason")
    logger.info("finish_reason=%s", finish_reason)

    if finish_reason in TRUNCADO:
        logger.warning("Respuesta truncada: se reintentará")
        raise OutputParserException("Respuesta truncada por límite de tokens.")

    if resultado.get("parsing_error") or resultado.get("parsed") is None:
        logger.warning("Salida mal formada o incompleta: se reintentará")
        raise OutputParserException(
            f"Salida mal formada: {resultado.get('parsing_error')}"
        )

    return resultado["parsed"]


# 3) Cadena LCEL + resiliencia
chain = (prompt | structured_model | RunnableLambda(validar_resultado)).with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=True,
)


async def process_text(text: str) -> EntidadesTecnicas:
    """Procesa un texto y devuelve un objeto EntidadesTecnicas validado."""
    if not text or not text.strip():
        raise ValueError("El texto de entrada está vacío.")

    logger.info("Procesando texto (%d caracteres)", len(text))
    try:
        resultado = await chain.ainvoke({"text": text})
        logger.info("Validación OK: %s", resultado.model_dump(mode="json"))
        return resultado
    except Exception as e:
        primera_linea = str(e).splitlines()[0][:200]
        logger.error("Falló tras todos los reintentos: %s: %s", type(e).__name__, primera_linea)
        raise