"""Text-to-SQL API entrypoint."""

from fastapi import FastAPI

from app.routers import router


app = FastAPI(title="Text-to-SQL API")
app.include_router(router)


def main() -> None:
	"""Run the API with uvicorn when executed as a script."""
	import uvicorn

	uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
	main()