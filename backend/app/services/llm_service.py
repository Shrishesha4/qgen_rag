"""
LLM service for interacting with LLM providers (Ollama, Gemini).

Features:
- Multiple provider support (Ollama local, Gemini cloud)
- Retry logic with exponential backoff
- Connection error recovery
- JSON response parsing with error handling
- Factory pattern for provider selection
"""

import json
import asyncio
import logging
from typing import Optional, AsyncGenerator, Any, Dict, Protocol, runtime_checkable
import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMConnectionError(LLMError):
    """Raised when unable to connect to LLM service."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


class LLMResponseError(LLMError):
    """Raised when LLM returns invalid response."""
    pass


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface for LLM providers."""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
    ) -> str:
        """Generate a response from the LLM."""
        ...
    
    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
        fallback_response: Optional[str] = None,
    ) -> str:
        """Generate response with optional fallback on failure."""
        ...
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        ...
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response."""
        ...
    
    async def check_health(self) -> bool:
        """Check if the LLM service is available."""
        ...


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retry_exceptions: tuple = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout),
):
    """
    Decorator for adding retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        retry_exceptions: Exception types to retry on
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff + jitter
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        # Add jitter (±25%)
                        import random
                        jitter = delay * 0.25 * (2 * random.random() - 1)
                        delay = delay + jitter
                        
                        logger.warning(
                            f"LLM request failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"LLM request failed after {max_retries + 1} attempts: {e}"
                        )
                except httpx.HTTPStatusError as e:
                    # Don't retry on HTTP errors (4xx, 5xx) - usually not transient
                    logger.error(f"LLM HTTP error: {e}")
                    raise LLMResponseError(f"LLM returned HTTP {e.response.status_code}") from e
            
            # All retries exhausted
            if isinstance(last_exception, (httpx.ConnectError, httpx.ConnectTimeout)):
                raise LLMConnectionError(
                    f"Failed to connect to Ollama after {max_retries + 1} attempts"
                ) from last_exception
            elif isinstance(last_exception, httpx.ReadTimeout):
                raise LLMTimeoutError(
                    f"Ollama request timed out after {max_retries + 1} attempts"
                ) from last_exception
            else:
                raise last_exception
        
        return wrapper
    return decorator


class OllamaLLMService:
    """Service for interacting with Ollama LLM (local)."""

    def __init__(self, model: Optional[str] = None):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        logger.info(f"OllamaLLMService initialized - base_url={self.base_url}, model={self.model}")
        self._timeout = httpx.Timeout(
            connect=10.0,   # Connection timeout
            read=120.0,     # Read timeout (LLM can be slow)
            write=10.0,     # Write timeout
            pool=5.0,       # Pool timeout
        )

    @with_retry(max_retries=3, base_delay=1.0)
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a response from the LLM with retry logic."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            
            if not content:
                logger.warning(f"Ollama returned empty content. Full response: {result}")
            
            return content

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
        fallback_response: Optional[str] = None,
    ) -> str:
        """
        Generate response with optional fallback on failure.
        
        Use this when you want to gracefully handle failures without
        raising exceptions to the caller.
        """
        try:
            return await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMError as e:
            logger.warning(f"LLM generation failed, using fallback: {e}")
            if fallback_response is not None:
                return fallback_response
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 5000,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]

    @with_retry(max_retries=2, base_delay=0.5)
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response from the LLM with retry logic."""
        json_system = (system_prompt or "") + "\n\nYou must respond with valid JSON only. No extra text. Keep responses concise."
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature,
            max_tokens=6000,  # Increased to avoid truncation
        )
        
        # Log raw response for debugging
        raw_preview = response[:500] if response else "(empty)"
        logger.debug(f"LLM raw response preview: {raw_preview}")
        
        # Clean response - strip markdown code blocks
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        # Extract first valid JSON object from response
        # LLMs sometimes output extra text after the JSON
        try:
            json_obj = self._extract_json_object(response)
            return json_obj
        except json.JSONDecodeError as e:
            logger.warning(f"JSON extraction failed: {e}. Cleaned response was: {response[:800]}")
            raise
    
    def _sanitize_control_chars(self, text: str) -> str:
        """Sanitize control characters that break JSON parsing.
        
        Control characters (0x00-0x1F) inside JSON strings must be escaped.
        This function properly escapes them while preserving valid escape sequences.
        """
        import re
        
        def escape_control_chars_in_strings(match):
            """Escape control chars inside a matched JSON string."""
            s = match.group(0)
            # Preserve the quotes, process the content
            content = s[1:-1]  # Remove surrounding quotes
            
            # Replace unescaped control characters with their escaped forms
            result = []
            i = 0
            while i < len(content):
                char = content[i]
                if char == '\\' and i + 1 < len(content):
                    # This is an escape sequence, keep it as-is
                    result.append(content[i:i+2])
                    i += 2
                elif ord(char) < 32:  # Control character
                    # Escape it properly
                    if char == '\n':
                        result.append('\\n')
                    elif char == '\r':
                        result.append('\\r')
                    elif char == '\t':
                        result.append('\\t')
                    elif char == '\x08':  # backspace
                        result.append('\\b')
                    elif char == '\x0c':  # form feed
                        result.append('\\f')
                    else:
                        # Use unicode escape for other control chars
                        result.append(f'\\u{ord(char):04x}')
                    i += 1
                else:
                    result.append(char)
                    i += 1
            
            return '"' + ''.join(result) + '"'
        
        # Match JSON strings (handling escaped quotes)
        # This regex matches strings like "..." including escaped quotes inside
        json_string_pattern = r'"(?:[^"\\]|\\.)*"'
        return re.sub(json_string_pattern, escape_control_chars_in_strings, text)

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """Extract the first valid JSON object from text."""
        import re
        
        # First, sanitize control characters
        text = self._sanitize_control_chars(text)
        
        # Try parsing as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to fix common JSON issues
        fixed_text = self._fix_json_syntax(text)
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            pass
        
        # Find the first { and try to find matching }
        start = text.find('{')
        if start == -1:
            raise json.JSONDecodeError("No JSON object found", text, 0)
        
        # Track brace depth to find the end of the first JSON object
        depth = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    # Found complete JSON object
                    json_str = text[start:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        # Try fixing syntax on extracted JSON
                        return json.loads(self._fix_json_syntax(json_str))
        
        # JSON appears truncated - try to repair it
        logger.warning(f"JSON appears truncated (depth={depth}, in_string={in_string}). Attempting repair.")
        repaired = self._repair_truncated_json(text[start:], depth, in_string)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        
        # If we get here, try parsing from start to end of text
        raise json.JSONDecodeError("No valid JSON object found", text, 0)
    
    def _repair_truncated_json(self, text: str, depth: int, in_string: bool) -> Optional[str]:
        """Attempt to repair truncated JSON by closing incomplete structures.
        
        Args:
            text: The partial JSON text starting from '{'
            depth: Current brace depth (how many unclosed {)
            in_string: Whether we're currently inside a string
        
        Returns:
            Repaired JSON string or None if repair failed
        """
        if not text:
            return None
        
        result = text.rstrip()
        
        # If we're inside a string, close it
        if in_string:
            # Remove trailing incomplete content that might be a broken escape sequence
            while result and result[-1] == '\\':
                result = result[:-1]
            result += '"'
        
        # Check if we need to add a colon and value (key without value)
        # Pattern: ..."key"  (missing : "value")
        import re
        if re.search(r'"[^"]*"\s*$', result) and not re.search(r':\s*"[^"]*"\s*$', result):
            # Check if this looks like a key (preceded by { or ,)
            stripped = result.rstrip()
            if re.search(r'[{,]\s*"[^"]*"\s*$', stripped):
                result += ': ""'
        
        # Close any open arrays
        # Count [ and ]
        open_arrays = result.count('[') - result.count(']')
        for _ in range(open_arrays):
            result += ']'
        
        # Close any open objects
        for _ in range(depth):
            result += '}'
        
        logger.debug(f"Repaired JSON: {result[:200]}...{result[-100:]}")
        return result

    def _fix_json_syntax(self, text: str) -> str:
        """Try to fix common JSON syntax errors."""
        import re
        
        # First, handle newlines inside strings - this is the most common issue
        # We need to escape actual newlines that are inside string values
        lines = text.split('\n')
        fixed_lines = []
        in_string = False
        for line in lines:
            # Count unescaped quotes to track if we're in a string
            quote_count = 0
            i = 0
            while i < len(line):
                if line[i] == '"' and (i == 0 or line[i-1] != '\\'):
                    quote_count += 1
                i += 1
            
            if in_string:
                # We're continuing a string from previous line  
                fixed_lines[-1] = fixed_lines[-1] + '\\n' + line
            else:
                fixed_lines.append(line)
            
            # If odd number of quotes, we've toggled string state
            if quote_count % 2 == 1:
                in_string = not in_string
        
        text = '\n'.join(fixed_lines)
        
        # Remove trailing commas before closing brackets
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        
        # Fix unquoted keys (common LLM error)
        text = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
        
        # Escape remaining control characters
        # Note: Most control chars should already be handled by _sanitize_control_chars
        # but this catches any edge cases in the syntax-fixing path
        text = text.replace('\t', '\\t')
        text = text.replace('\r', '')
        
        # Handle any remaining raw newlines that might be inside strings
        # (This is a fallback - the per-line logic above should catch most cases)
        
        # NOTE: We intentionally do NOT do text.replace("'", '"') because
        # LLM output often contains apostrophes inside strings (e.g., "'for' loop")
        # and blindly replacing them corrupts the JSON structure.
        
        return text

    async def check_health(self) -> bool:
        """Check if Ollama is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


# Factory function to create the appropriate LLM service based on configuration
def LLMService(model: Optional[str] = None) -> LLMProvider:
    """
    Factory function to create the appropriate LLM service based on configuration.
    
    Uses LLM_PROVIDER environment variable to select provider:
    - "ollama": Local Ollama instance (default)
    - "gemini": Google Gemini API
    
    Args:
        model: Optional model name override. If not provided, uses the default
               model for the configured provider.
    
    Returns:
        An LLM service instance that implements the LLMProvider protocol.
    
    Example:
        # Uses provider from LLM_PROVIDER env var
        llm = LLMService()
        
        # Override model
        llm = LLMService(model="gemini-1.5-pro")
    """
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "gemini":
        from app.services.gemini_service import GeminiService
        logger.info(f"Creating GeminiService (provider={provider})")
        return GeminiService(model=model)
    elif provider == "ollama":
        logger.info(f"Creating OllamaLLMService (provider={provider})")
        return OllamaLLMService(model=model)
    else:
        logger.warning(f"Unknown LLM provider '{provider}', falling back to Ollama")
        return OllamaLLMService(model=model)


def get_llm_provider_info() -> Dict[str, Any]:
    """Get information about the current LLM provider configuration."""
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "gemini":
        return {
            "provider": "gemini",
            "model": settings.GEMINI_MODEL,
            "api_configured": bool(settings.GEMINI_API_KEY),
        }
    else:
        return {
            "provider": "ollama",
            "model": settings.OLLAMA_MODEL,
            "base_url": settings.OLLAMA_BASE_URL,
        }
