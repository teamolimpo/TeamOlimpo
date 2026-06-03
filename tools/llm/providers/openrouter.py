"""
Provider OpenRouter per il tool llm.

OpenRouter e' un gateway unificato per decine di provider LLM (OpenAI, Anthropic,
Google, Meta, Mistral, DeepSeek, ecc.) con una singola API OpenAI-compatible.

Usa l'SDK OpenAI con base_url https://openrouter.ai/api/v1.
Richiede: uv add openai

Documentazione: https://openrouter.ai/docs/api-reference
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from loguru import logger

from tools.llm.providers.base import ChatResponse, ModelInfo

if TYPE_CHECKING:
    pass


class OpenRouterProvider:
    """
    Provider per OpenRouter.

    Singolo endpoint OpenAI-compatible per >300 modelli di decine di provider.
    Modello di default: openai/gpt-4o-mini (economico e veloce).
    """

    default_model: str = "deepseek/deepseek-v4-flash"
    _BASE_URL: str = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str) -> None:
        """
        Inizializza il client OpenAI configurato per OpenRouter.

        Args:
            api_key: Chiave API OpenRouter (ottenibile da https://openrouter.ai/keys)

        Raises:
            ImportError: Se la libreria openai non e' installata
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "La libreria 'openai' non e' installata. Esegui: uv add openai"
            ) from exc

        self._api_key = api_key
        self._client = OpenAI(
            api_key=api_key,
            base_url=self._BASE_URL,
            default_headers={
                # Identificativo per le classifiche pubbliche OpenRouter
                "HTTP-Referer": "https://github.com/stra/TeamOlimpo",
                "X-Title": "Team Olimpo",
            },
        )
        logger.debug(f"OpenRouterProvider inizializzato con base_url={self._BASE_URL}")

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        agent_count: int = 4,
    ) -> ChatResponse:
        """
        Invia un prompt a OpenRouter e restituisce la risposta.

        Args:
            prompt: Testo del prompt da inviare
            model: Override del modello (None = usa default_model)
            system: Messaggio di sistema opzionale

        Returns:
            ChatResponse con testo della risposta e metadati token/tempo

        Raises:
            RuntimeError: Se la chiamata API fallisce
        """
        effective_model = model or self.default_model

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug(
            f"OpenRouterProvider: chiamata a modello={effective_model}, messaggi={len(messages)}"
        )

        start = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=effective_model,
                messages=messages,  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.error(f"OpenRouterProvider: errore durante la chiamata API — {exc}")
            raise RuntimeError(f"Errore chiamata OpenRouter: {exc}") from exc

        elapsed = time.monotonic() - start

        text = response.choices[0].message.content or ""
        input_tokens: int | None = None
        output_tokens: int | None = None

        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

        logger.debug(
            f"OpenRouterProvider: risposta ricevuta in {elapsed:.2f}s, "
            f"token input={input_tokens}, output={output_tokens}"
        )

        return ChatResponse(
            text=text,
            model_used=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Lista modelli
    # ------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """
        Recupera i modelli disponibili dall'API OpenRouter.

        L'endpoint /api/v1/models restituisce TUTTI i modelli accessibili
        (centinaia). La risposta include id, name, pricing, context_length.

        Returns:
            Lista di ModelInfo ordinata per id

        Raises:
            RuntimeError: Se la chiamata API fallisce
        """
        logger.debug("OpenRouterProvider: recupero lista modelli")
        try:
            page = self._client.models.list()
            ids = sorted(m.id for m in page)
        except Exception as exc:
            logger.error(f"OpenRouterProvider: errore list_models — {exc}")
            raise RuntimeError(f"Errore recupero modelli OpenRouter: {exc}") from exc

        models = [ModelInfo(id=mid, is_default=(mid == self.default_model)) for mid in ids]
        logger.debug(f"OpenRouterProvider: {len(models)} modelli trovati")
        return models

    # ------------------------------------------------------------------
    # Sessione chat (non supportata — OpenRouter e' stateless)
    # ------------------------------------------------------------------

    def start_chat_session(
        self,
        model: str | None = None,
        system: str | None = None,
    ) -> None:
        """
        OpenRouter non supporta sessioni di chat stateful.

        Raises:
            NotImplementedError: Sempre — OpenRouter e' un proxy stateless.
        """
        raise NotImplementedError(
            "OpenRouterProvider non supporta sessioni di chat multi-turn. "
            "Usa il metodo chat() con history gestita manualmente."
        )
