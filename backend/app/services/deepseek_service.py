"""
DeepSeek API service for DeepSeek's LLM.

Provides the same interface as the Ollama LLM service for seamless swapping.
Uses the OpenAI-compatible API endpoint that DeepSeek provides.
"""

import json
import asyncio
import logging
import re
from typing import Optional, AsyncGenerator, Any, Dict

import httpx

from app.core.config import settings
from app.services.llm_service import (
    LLMError,
    LLMConnectionError,
    LLMTimeoutError,
    LLMResponseError,
)


logger = logging.getLogger(__name__)


class DeepSeekError(LLMError):
    """Base exception for DeepSeek errors."""
    pass


class DeepSeekConnectionError(DeepSeekError, LLMConnectionError):
    """Raised when unable to connect to DeepSeek API."""
    pass


class DeepSeekTimeoutError(DeepSeekError, LLMTimeoutError):
    """Raised when DeepSeek request times out."""
    pass


class DeepSeekResponseError(DeepSeekError, LLMResponseError):
    """Raised when DeepSeek returns invalid response."""
    pass


class DeepSeekRateLimitError(DeepSeekError):
    """Raised when hitting DeepSeek rate limits."""
    pass


class DeepSeekService:
    """Service for interacting with DeepSeek API (OpenAI-compatible)."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = (api_key or settings.DEEPSEEK_API_KEY or "").strip()
        self.model = model or settings.DEEPSEEK_MODEL
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")

        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is required when using DeepSeek provider. "
                "Set it in your .env file: DEEPSEEK_API_KEY=your-key-from-platform.deepseek.com"
            )

        self._timeout = httpx.Timeout(
            connect=10.0,
            read=120.0,
            write=10.0,
            pool=5.0,
        )

        # Token usage tracking
        self._total_tokens_used: int = 0
        self._total_calls: int = 0

        logger.info(
            f"DeepSeekService initialized - base_url={self.base_url}, model={self.model}"
        )

    @property
    def total_tokens_used(self) -> int:
        """Return cumulative tokens used across all calls."""
        return self._total_tokens_used

    @property
    def total_calls(self) -> int:
        """Return cumulative LLM call count."""
        return self._total_calls

    def reset_usage(self) -> None:
        """Reset token and call counters (call at start of a generation session)."""
        self._total_tokens_used = 0
        self._total_calls = 0

    def _track_usage(self, result: dict) -> None:
        """Extract and accumulate token usage from API response."""
        usage = result.get("usage", {})
        total = usage.get("total_tokens", 0)
        if total:
            self._total_tokens_used += total
            self._total_calls += 1
            logger.debug(f"DeepSeek usage: +{total} tokens (cumulative: {self._total_tokens_used})")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
    ) -> str:
        """Generate a response from DeepSeek with retry logic."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )

                    # Handle rate-limiting
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 5
                            logger.warning(
                                f"DeepSeek rate limited, waiting {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        raise DeepSeekRateLimitError(
                            f"Rate limit exceeded (HTTP 429)"
                        )

                    response.raise_for_status()
                    result = response.json()

                self._track_usage(result)

                content = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                if not content:
                    logger.warning(
                        f"DeepSeek returned empty content. Full response: {result}"
                    )

                return content

            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                if status == 429:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        logger.warning(
                            f"DeepSeek rate limited, waiting {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    raise DeepSeekRateLimitError(
                        f"Rate limit exceeded: {e}"
                    ) from e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"DeepSeek HTTP error (attempt {attempt + 1}): {e}, retrying..."
                    )
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise DeepSeekResponseError(
                    f"DeepSeek returned HTTP {status}"
                ) from e

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    logger.warning(
                        f"DeepSeek connection error (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                raise DeepSeekConnectionError(
                    f"Failed to connect after {max_retries} attempts"
                ) from e

            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"DeepSeek timeout (attempt {attempt + 1}), retrying..."
                    )
                    await asyncio.sleep(1)
                    continue
                raise DeepSeekTimeoutError(
                    f"Request timed out after {max_retries} attempts"
                ) from e

            except DeepSeekError:
                raise

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"DeepSeek error (attempt {attempt + 1}): {e}, retrying..."
                    )
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise DeepSeekResponseError(
                    f"Generation failed: {e}"
                ) from e

        raise last_error or DeepSeekResponseError("Generation failed after retries")

    # ------------------------------------------------------------------
    # Fallback wrapper
    # ------------------------------------------------------------------

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
        fallback_response: Optional[str] = None,
    ) -> str:
        """Generate response with optional fallback on failure."""
        try:
            return await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except DeepSeekError as e:
            logger.warning(f"DeepSeek generation failed, using fallback: {e}")
            if fallback_response is not None:
                return fallback_response
            raise

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from DeepSeek (SSE)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # strip "data: "
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise DeepSeekResponseError(f"Streaming failed: {e}") from e

    # ------------------------------------------------------------------
    # Structured JSON generation
    # ------------------------------------------------------------------

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> Dict[str, Any]:
        """Generate a JSON response from DeepSeek with retry logic."""
        json_system = (system_prompt or "") + (
            "\n\nIMPORTANT: You must respond with ONLY a valid JSON object. "
            "Do NOT include any prose, commentary, or markdown code fences (```json) before or after the JSON. "
            "Output ALL fields specified in the format above, including the 'explanation' field. "
            "Start your response with { and end with }."
        )

        # DeepSeek supports json_object response format
        messages = []
        if json_system:
            messages.append({"role": "system", "content": json_system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    try:
                        resp = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._headers(),
                            json=payload,
                        )
                    except Exception:
                        raise

                    if resp.status_code == 400 and "response_format" in payload:
                        fallback_payload = dict(payload)
                        fallback_payload.pop("response_format", None)
                        logger.warning(
                            "Provider rejected response_format=json_object for model=%s base_url=%s; retrying without response_format",
                            self.model,
                            self.base_url,
                        )
                        resp = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._headers(),
                            json=fallback_payload,
                        )

                    if resp.status_code == 429:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 5
                            logger.warning(
                                f"DeepSeek rate limited, waiting {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        raise DeepSeekRateLimitError("Rate limit exceeded (HTTP 429)")

                    resp.raise_for_status()
                    result = resp.json()

                self._track_usage(result)

                content = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                if not content:
                    raise DeepSeekResponseError("Empty response from DeepSeek")

                # Log raw response for debugging
                raw_preview = content[:500]
                logger.debug(f"DeepSeek raw JSON response preview: {raw_preview}")

                # Clean markdown fences if present
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                # Parse JSON
                try:
                    return self._extract_json_object(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"JSON extraction failed: {e}. Cleaned response was: {content[:800]}"
                    )
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"JSON parse error (attempt {attempt + 1}), retrying..."
                        )
                        await asyncio.sleep(1)
                        continue
                    raise

            except (DeepSeekError, json.JSONDecodeError):
                last_error = last_error  # keep original
                raise

            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"DeepSeek HTTP error (attempt {attempt + 1}): {e}, retrying..."
                    )
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise DeepSeekResponseError(
                    f"JSON generation failed: HTTP {e.response.status_code}"
                ) from e

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"DeepSeek error (attempt {attempt + 1}): {e}, retrying..."
                    )
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                if isinstance(e, DeepSeekError):
                    raise
                raise DeepSeekResponseError(
                    f"JSON generation failed: {e}"
                ) from e

        raise last_error or DeepSeekResponseError(
            "JSON generation failed after retries"
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def check_health(self) -> bool:
        """Check if DeepSeek API is reachable."""
        try:
            response = await self.generate(
                prompt="Say 'ok'",
                max_tokens=5,
            )
            return len(response) > 0
        except Exception as e:
            logger.warning(f"DeepSeek health check failed: {e}")
            return False

    # ------------------------------------------------------------------
    # JSON repair utilities (mirrored from OllamaLLMService)
    # ------------------------------------------------------------------

    def _sanitize_control_chars(self, text: str) -> str:
        """Sanitize control characters that break JSON parsing.

        Control characters (0x00-0x1F) inside JSON strings must be escaped.
        This function properly escapes them while preserving valid escape sequences.
        """

        def escape_control_chars_in_strings(match):
            s = match.group(0)
            content = s[1:-1]
            valid_escapes = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't'}
            hexdigits = set('0123456789abcdefABCDEF')

            result = []
            i = 0
            while i < len(content):
                char = content[i]
                if char == "\\":
                    if i + 1 >= len(content):
                        result.append("\\\\")
                        i += 1
                    else:
                        nxt = content[i + 1]
                        if nxt in valid_escapes:
                            result.append("\\" + nxt)
                            i += 2
                        elif nxt == "u":
                            hex_part = content[i + 2:i + 6]
                            if len(hex_part) == 4 and all(ch in hexdigits for ch in hex_part):
                                result.append("\\u" + hex_part)
                                i += 6
                            else:
                                result.append("\\\\u")
                                i += 2
                        else:
                            result.append("\\\\" + nxt)
                            i += 2
                elif ord(char) < 32:
                    if char == "\n":
                        result.append("\\n")
                    elif char == "\r":
                        result.append("\\r")
                    elif char == "\t":
                        result.append("\\t")
                    elif char == "\x08":
                        result.append("\\b")
                    elif char == "\x0c":
                        result.append("\\f")
                    else:
                        result.append(f"\\u{ord(char):04x}")
                    i += 1
                else:
                    result.append(char)
                    i += 1

            return '"' + "".join(result) + '"'

        json_string_pattern = r'"(?:[^"\\]|\\.)*"'
        return re.sub(json_string_pattern, escape_control_chars_in_strings, text)

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """Extract the first valid JSON object or array from text."""
        text = self._sanitize_control_chars(text)

        # Try as-is
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try fixing common syntax issues
        fixed_text = self._fix_json_syntax(text)
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            pass

        # Find first JSON root token
        first_obj = text.find("{")
        first_arr = text.find("[")
        if first_obj == -1 and first_arr == -1:
            raise json.JSONDecodeError("No JSON structure found", text, 0)

        if first_arr != -1 and (first_obj == -1 or first_arr < first_obj):
            start = first_arr
            open_char, close_char = "[", "]"
        else:
            start = first_obj
            open_char, close_char = "{", "}"

        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    json_str = text[start : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        return json.loads(self._fix_json_syntax(json_str))

        # Truncated — attempt repair
        logger.warning(
            f"JSON appears truncated (depth={depth}, in_string={in_string}). "
            "Attempting repair."
        )
        repaired = self._repair_truncated_json(text[start:], depth, in_string)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError("No valid JSON structure found", text, 0)

    def _repair_truncated_json(
        self, text: str, depth: int, in_string: bool
    ) -> Optional[str]:
        """Attempt to repair truncated JSON by closing incomplete structures."""
        if not text:
            return None

        result = text.rstrip()

        stack = []
        in_str = False
        escape = False

        for ch in result:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in ("}", "]"):
                if stack:
                    stack.pop()

        if in_str:
            while result and result[-1] == "\\":
                result = result[:-1]
            result += '"'

        result = result.rstrip()
        if result.endswith(","):
            result = result[:-1]

        while stack:
            result += stack.pop()

        logger.debug(f"Repaired JSON: {result[:200]}...{result[-100:]}")
        return result

    def _fix_json_syntax(self, text: str) -> str:
        """Try to fix common JSON syntax errors."""
        text = self._sanitize_control_chars(text)

        # Handle newlines inside strings
        lines = text.split("\n")
        fixed_lines = []
        in_string = False
        for line in lines:
            quote_count = 0
            i = 0
            while i < len(line):
                if line[i] == '"' and (i == 0 or line[i - 1] != "\\"):
                    quote_count += 1
                i += 1

            if in_string:
                fixed_lines[-1] = fixed_lines[-1] + "\\n" + line
            else:
                fixed_lines.append(line)

            if quote_count % 2 == 1:
                in_string = not in_string

        text = "\n".join(fixed_lines)

        # Remove trailing commas before closing brackets
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)

        # Fix missing commas between adjacent JSON properties
        text = re.sub(
            r'(["\]\}]|true|false|null|\d)\n(\s*"[^"\\\n]{0,100}"\s*:)',
            r"\1,\n\2",
            text,
        )

        # Fix keyless string values inside objects → convert to arrays
        text = re.sub(
            r'\{(\s*"(?:[^"\\]|\\.)*"\s*(?:,\s*"(?:[^"\\]|\\.)*"\s*)*)\}',
            lambda m: "[" + m.group(1) + "]",
            text,
        )

        # Fix unquoted keys
        text = re.sub(r"(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)

        # Escape remaining control characters
        text = text.replace("\t", "\\t")
        text = text.replace("\r", "")

        return text


