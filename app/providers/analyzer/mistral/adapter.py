"""Mistral AI structured JSON analysis adapter."""

import logging

from mistralai import Mistral
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.ai_models import AIMessage, AIResponse
from app.providers.llm.mistral.adapter import _extract_text
from app.providers.mistral_utils import RETRYABLE_ERRORS, convert_message, raise_provider_error

logger = logging.getLogger(__name__)


class MistralAnalyzerAdapter:
    """Mistral AI structured JSON analysis adapter.

    Always uses JSON mode (response_format={"type": "json_object"}).
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "mistral-small-latest",
        timeout: float = 30.0,
    ) -> None:
        self._client = Mistral(api_key=api_key, timeout_ms=int(timeout * 1000))
        self._default_model = default_model
        logger.info("Initialized MistralAnalyzerAdapter with model %s", default_model)

    @retry(
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def analyze_json(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> AIResponse:
        try:
            mistral_messages = [convert_message(m) for m in messages]

            response = await self._client.chat.complete_async(
                model=self._default_model,
                messages=mistral_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            choice = response.choices[0]
            return AIResponse(
                content=_extract_text(choice.message.content),
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=choice.finish_reason,
            )

        except RETRYABLE_ERRORS:
            raise
        except Exception as e:
            raise_provider_error("analyzer", e)
