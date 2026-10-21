from fastapi import APIRouter
from app.api.v1.endpoints import config, tickets, kb

api_router = APIRouter()

api_router.include_router(config.router, tags=["Configuration"])
api_router.include_router(tickets.router, tags=["Tickets"])
api_router.include_router(kb.router, tags=["Knowledge Base & RAG"])
