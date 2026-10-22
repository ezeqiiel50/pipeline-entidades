import asyncio

from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableLambda

from chain import process_text

CASOS = {
    "Arquitectura": (
        "Nuestra API en FastAPI usa Redis como caché y PostgreSQL para persistencia. "
        "En horas pico se saturan las conexiones concurrentes y los usuarios reciben timeouts."
    ),
    "Log de error": (
        "ERROR 2026-10-16 03:12:44 sqlalchemy.exc.OperationalError: connection to "
        "server at 'db-prod' (10.0.0.5), port 5432 failed: too many clients already. "
        "Servicio: payments-api (Django + Celery)."
    ),
    "Ambiguo": "Algo anda raro con el sistema, a veces se cae y no sabemos por qué.",
    "No técnico": "Ayer almorcé milanesas con puré y después salí a caminar.",
    "Vacío": "",
}


async def demo_reintentos():
    """Demuestra with_retry con un paso que falla 2 veces y luego funciona."""
    intentos = {"n": 0}

    def inestable(x):
        intentos["n"] += 1
        print(f"  intento {intentos['n']}")
        if intentos["n"] < 3:
            raise OutputParserException("JSON mal formado simulado")
        return "OK tras reintentos"

    cadena = RunnableLambda(inestable).with_retry(stop_after_attempt=3)
    print(await cadena.ainvoke("x"))


async def main():
    for nombre, texto in CASOS.items():
        print(f"\n=== {nombre} ===")
        try:
            r = await process_text(texto)
            print(r.model_dump_json(indent=2))
        except Exception as e:
            print(f"[ERROR controlado] {type(e).__name__}: {str(e).splitlines()[0][:200]}")

    print("\n=== Demo de reintentos (simulada) ===")
    await demo_reintentos()


if __name__ == "__main__":
    asyncio.run(main())