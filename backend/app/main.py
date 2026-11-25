"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import admin, respondent

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Concave Insights - Custom Survey System API",
    description="Backend API for parsing, validating, running, and exporting custom consumer surveys.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(respondent.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
