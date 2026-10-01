from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from bxk_app.services.chatbot_service import (
    ChatbotConfigurationError,
    ChatbotRateLimitError,
    ask_chatbot,
    chatbot_config,
    enforce_rate_limit,
)


router = APIRouter(
    prefix="/api/chat",
    tags=["Public AI Assistant"],
)


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=2000,
    )
    history: list[ChatHistoryItem] = Field(
        default_factory=list,
        max_length=8,
    )
    page_url: str | None = Field(
        default=None,
        max_length=500,
    )
    page_title: str | None = Field(
        default=None,
        max_length=200,
    )
    page_context: str | None = Field(
        default=None,
        max_length=4000,
    )


def _client_key(request: Request) -> str:
    forwarded = str(
        request.headers.get(
            "x-forwarded-for",
            "",
        )
    ).split(",")[0].strip()

    if forwarded:
        return forwarded

    if request.client:
        return request.client.host

    return "unknown"


@router.get("/status")
def chatbot_status():
    config = chatbot_config()

    return {
        "enabled": (
            config["enabled"]
            and config["api_key_configured"]
        ),
    }


@router.post("")
def public_chat(
    request_data: ChatRequest,
    request: Request,
):
    try:
        enforce_rate_limit(
            _client_key(request)
        )

        result = ask_chatbot(
            message=request_data.message,
            history=[
                item.model_dump()
                for item in request_data.history
            ],
            page_url=request_data.page_url,
            page_title=request_data.page_title,
            page_context=request_data.page_context,
        )

        return result

    except ChatbotRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    except (
        ChatbotConfigurationError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
