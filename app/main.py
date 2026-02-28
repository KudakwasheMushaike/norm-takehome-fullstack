from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.utils import DocumentService, Output, QdrantService

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

index_service = QdrantService(k=3)


@app.on_event("startup")
def initialize_index() -> None:
    try:
        docs = DocumentService().create_documents()
        index_service.connect()
        index_service.load(docs)
        app.state.startup_error = None
    except Exception as exc:  # noqa: BLE001
        app.state.startup_error = str(exc)


@app.get("/query", response_model=Output)
def query_laws(
    query: str = Query(..., min_length=3, description="Natural language query over laws."),
) -> Output:
    startup_error = getattr(app.state, "startup_error", None)
    if startup_error:
        raise HTTPException(status_code=500, detail=f"Service unavailable: {startup_error}")

    try:
        return index_service.query(query)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
