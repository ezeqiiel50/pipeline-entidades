# Pipeline de Extracción de Entidades Técnicas

Pipeline asíncrono que recibe un texto sin procesar (descripción de arquitectura o log de error) y devuelve un **objeto Pydantic validado** con las tecnologías mencionadas, el nivel de criticidad y un resumen técnico. Construido con **LangChain (LCEL)**.

> Pre-entrega 2: Pipeline de procesamiento validado.
> La selección de proveedor (OpenAI, Anthropic o Gemini) por configuración reutiliza la lógica de la Pre-entrega 1 (Unified Async LLM Client).

---

## 1. Definición de la tarea

### Qué pedía la consigna

Desarrollar un pipeline que:

1. Defina un **esquema Pydantic** con `tecnologias` (lista de strings), `nivel_de_criticidad` (enum: baja, media, alta) y `resumen_tecnico` (string).
2. Use un **Prompt Template** modular que acepte el texto de entrada.
3. Compone una **cadena LCEL**: Prompt + LLM + Output Parser.
4. Tenga **resiliencia**: al menos un reintento automático si el LLM devuelve una salida mal formada o incompleta.
5. Exponga una función asíncrona `process_text(text: str)` con `.ainvoke()` y logs, más un mini-script de prueba.

### Qué se construyó

| Requisito | Implementación |
| --- | --- |
| Esquema Pydantic | `schemas.py`: `EntidadesTecnicas` y enum `Criticidad`. La lista de tecnologías no puede estar vacía (`min_length=1` + validador que descarta strings en blanco) y el resumen exige un mínimo de 10 caracteres |
| Prompt Template | `ChatPromptTemplate` con la variable `{text}`; sin f-strings |
| Cadena LCEL | `prompt \| model.with_structured_output(EntidadesTecnicas, include_raw=True) \| RunnableLambda(validar_resultado)` |
| Resiliencia | `.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)` sobre toda la cadena |
| `finish_reason` | `validar_resultado` lee `finish_reason` / `stop_reason` y lanza error si la respuesta fue truncada por límite de tokens, lo que dispara el reintento |
| Función asíncrona | `process_text()` con `.ainvoke()` y logs de cada etapa |
| Proveedor por configuración | `get_model()` elige OpenAI, Anthropic o Gemini según `LLM_PROVIDER` en el `.env` |
| Script de prueba | `test_pipeline.py`: 4 casos (arquitectura, log de error, ambiguo, vacío) y una demo de reintentos |

---

## 2. Estructura del proyecto

```
pipeline-entidades/
├── schemas.py          # Modelo Pydantic (contrato de salida)
├── chain.py            # Prompt + modelo + cadena LCEL + reintentos + process_text()
├── test_pipeline.py    # Script de prueba asíncrono
├── .env.example        # Plantilla de variables
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3. Requisitos

- Python 3.12 o superior. Se desarrolló y probó con **Python 3.14** (Windows).
- Una API key de al menos un proveedor:
  * OpenAI: <https://platform.openai.com/api-keys>
  * Anthropic: <https://console.anthropic.com/>
  * Gemini (con plan gratuito): <https://aistudio.google.com/apikey>

## 4. Instalación

**Windows (PowerShell o CMD)**

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**Linux / macOS**

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Después abrí el archivo `.env` y pegá tu API key. **Nunca subas el `.env` a GitHub** (ya está en `.gitignore`).

## 5. Variables de entorno

| Variable | Obligatoria | Descripción |
| --- | --- | --- |
| `LLM_PROVIDER` | No | `openai`, `anthropic` o `gemini`. Default: `openai` |
| `LLM_TEMPERATURE` | No | Default: `0` |
| `LLM_MAX_TOKENS` | No | Default: `1024` |
| `OPENAI_API_KEY` | Si usás OpenAI | API key de OpenAI |
| `ANTHROPIC_API_KEY` | Si usás Anthropic | API key de Anthropic |
| `GEMINI_API_KEY` | Si usás Gemini | API key de Google AI Studio (también se acepta `GOOGLE_API_KEY`) |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` / `GEMINI_MODEL` | No | Pisan el modelo por defecto de cada proveedor |

Modelos por defecto: `gpt-4o-mini`, `claude-haiku-5-5`, `gemini-3.5-flash-lite`.

Las keys de los proveedores que no uses tienen que quedar **vacías** (`OPENAI_API_KEY=`). Los nombres de modelos cambian con el tiempo; si aparece un error `404` de modelo inexistente, definí otro con `<PROVEEDOR>_MODEL` en el `.env`.

---

## 6. Cómo probarlo

```
python test_pipeline.py
```

### Qué hace `test_pipeline.py`, en orden

1. **Arquitectura:** descripción de una API con FastAPI, Redis y PostgreSQL.
2. **Log de error:** un error de conexión a PostgreSQL en un servicio Django + Celery.
3. **Texto ambiguo:** prueba de estrés sin tecnologías identificables.
4. **Texto vacío:** debe rechazarse antes de llamar al LLM.
5. **Demo de reintentos:** un paso que falla dos veces y funciona a la tercera, para mostrar `.with_retry()` (es una simulación, no un fallo real del LLM).

### Ejemplo de salida esperada

```json
{
  "tecnologias": ["FastAPI", "Redis", "PostgreSQL"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "API con caché en Redis y persistencia en PostgreSQL; cuello de botella en conexiones concurrentes."
}
```

### Salida real obtenida (Gemini, `gemini-3.5-flash-lite`)

**Caso 1: Arquitectura**

```json
{
  "tecnologias": ["FastAPI", "Redis", "PostgreSQL"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "El sistema presenta problemas de saturación de conexiones concurrentes y timeouts en horas pico, afectando a la API construida con FastAPI, Redis y PostgreSQL."
}
```

**Caso 2: Log de error**

```json
{
  "tecnologias": ["Django", "Celery", "PostgreSQL", "SQLAlchemy"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "El servicio payments-api no puede establecer conexion con la base de datos de produccion debido a que se ha alcanzado el limite maximo de clientes permitidos."
}
```

**Logs del proceso de validación (caso 1)**

```
INFO | Proveedor=gemini | modelo=gemini-3.5-flash-lite
INFO | Procesando texto (161 caracteres)
INFO | HTTP Request: POST .../gemini-3.5-flash-lite:generateContent "HTTP/1.1 200 OK"
INFO | finish_reason=STOP
INFO | Validación OK: {...}
```

**Demo de reintentos (simulada)**

```
  intento 1
  intento 2
  intento 3
OK tras reintentos
```

### Estado de las pruebas

- **Gemini:** probado de punta a punta con una API key real.
- **OpenAI y Anthropic:** implementados con el mismo diseño (`get_model()`), pero no probados con una key real.

---

## 7. Prueba de estrés

### Texto ambiguo

Entrada: `"Algo anda raro con el sistema, a veces se cae y no sabemos por qué."`

Resultado con la **primera versión del prompt**:

```json
{
  "tecnologias": ["Sistema genérico"],
  "nivel_de_criticidad": "media",
  "resumen_tecnico": "Se reportan fallas intermitentes y desconoce la causa raíz del problema en el sistema."
}
```

### Texto vacío

Entrada: `""`

Resultado: rechazado antes de llamar al LLM, sin gastar tokens ni reintentos:

```
[ERROR controlado] ValueError: El texto de entrada está vacío.
```
---

## 8. Manejo de errores y resiliencia

| Situación | Cómo se maneja |
| --- | --- |
| Respuesta truncada (`finish_reason` = `MAX_TOKENS`, `length` o `max_tokens`) | `validar_resultado` lanza `OutputParserException` y `.with_retry()` reintenta |
| Salida mal formada o incompleta (`parsing_error` o `parsed` nulo) | Misma ruta: se lanza excepción y se reintenta |
| Violación del esquema (lista de tecnologías vacía, enum inválido, resumen corto) | Pydantic lo rechaza y la excepción dispara el reintento |
| Texto de entrada vacío | `process_text` lanza `ValueError` antes de llamar al LLM |
| Fallo tras 3 intentos | Se registra el error en el log y la excepción se propaga a quien llama |

- **Reintentos:** 3 intentos con backoff exponencial y jitter (`stop_after_attempt=3`, `wait_exponential_jitter=True`).
- **Logs:** se registran el proveedor y modelo, el tamaño del texto, la petición HTTP, el `finish_reason` y el resultado de la validación o el error final.