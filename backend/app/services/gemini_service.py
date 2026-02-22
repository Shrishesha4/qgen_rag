"""
Gemini API service for Google's Generative AI.

Provides the same interface as the Ollama LLM service for seamless swapping.
Uses the new google-genai SDK.
"""

import json
import asyncio
import logging
from typing import Optional, AsyncGenerator, Any, Dict, List
from abc import ABC, abstractmethod

from app.core.config import settings


logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini errors."""
    pass


class GeminiConnectionError(GeminiError):
    """Raised when unable to connect to Gemini API."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when Gemini request times out."""
    pass


class GeminiResponseError(GeminiError):
    """Raised when Gemini returns invalid response."""
    pass


class GeminiRateLimitError(GeminiError):
    """Raised when hitting Gemini rate limits."""
    pass


class GeminiService:
    """Service for interacting with Google Gemini API using the new google-genai SDK."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = (api_key or settings.GEMINI_API_KEY or "").strip()
        self.model_name = model or settings.GEMINI_MODEL
        self._client = None
        
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when using Gemini provider. "
                "Set it in your .env file: GEMINI_API_KEY=your-key-from-aistudio.google.com"
            )
        
        logger.info(f"GeminiService initialized with model: {self.model_name}")
        
    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "google-genai is not installed. "
                    "Install it with: pip install google-genai"
                )
        return self._client

    def _get_safety_settings(self) -> Optional[List[Dict[str, str]]]:
        """Get safety settings configuration."""
        if settings.GEMINI_SAFETY_BLOCK_NONE:
            return [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            ]
        return None

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a response from Gemini with retry logic."""
        from google import genai
        from google.genai import types
        
        client = self._get_client()
        
        # Build contents with system instruction
        contents = []
        if system_prompt:
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"System Instructions:\n{system_prompt}\n\nUser Request:\n{prompt}")]
            ))
        else:
            contents.append(types.Content(
                role="user", 
                parts=[types.Part(text=prompt)]
            ))
        
        # Configure generation parameters
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            candidate_count=1,
            safety_settings=self._get_safety_settings(),
        )
        
        # Retry logic
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use async client
                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                
                # Check for blocked content
                if not response.candidates:
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                        if block_reason:
                            raise GeminiResponseError(f"Content blocked: {block_reason}")
                    raise GeminiResponseError("No response generated")
                
                # Extract text from response
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, 'finish_reason', None)
                if finish_reason and str(finish_reason).upper() == "SAFETY":
                    raise GeminiResponseError("Response blocked for safety reasons")
                
                if not candidate.content or not candidate.content.parts:
                    raise GeminiResponseError("Empty response from Gemini")
                
                return candidate.content.parts[0].text
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for rate limiting
                if "429" in str(e) or "quota" in error_str or "rate" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  # Progressive backoff
                        logger.warning(f"Gemini rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    raise GeminiRateLimitError(f"Rate limit exceeded: {e}") from e
                
                # Check for timeout
                if "timeout" in error_str or "deadline" in error_str:
                    if attempt < max_retries - 1:
                        logger.warning(f"Gemini timeout (attempt {attempt + 1}), retrying...")
                        await asyncio.sleep(1)
                        continue
                    raise GeminiTimeoutError(f"Request timed out: {e}") from e
                
                # For other errors, retry with backoff
                if attempt < max_retries - 1:
                    logger.warning(f"Gemini error (attempt {attempt + 1}): {e}, retrying...")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                
                # Re-raise as appropriate error type
                if isinstance(e, GeminiError):
                    raise
                raise GeminiResponseError(f"Generation failed: {e}") from e
        
        raise last_error or GeminiResponseError("Generation failed after retries")

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
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
        except GeminiError as e:
            logger.warning(f"Gemini generation failed, using fallback: {e}")
            if fallback_response is not None:
                return fallback_response
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from Gemini."""
        from google.genai import types
        
        client = self._get_client()
        
        # Build contents
        contents = []
        if system_prompt:
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"System Instructions:\n{system_prompt}\n\nUser Request:\n{prompt}")]
            ))
        else:
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
            ))
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            candidate_count=1,
            safety_settings=self._get_safety_settings(),
        )
        
        try:
            async for chunk in client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise GeminiResponseError(f"Streaming failed: {e}") from e

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON response from Gemini using structured output."""
        from google.genai import types
        
        client = self._get_client()
        
        # Build contents with system instruction
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Request:\n{prompt}"
        
        contents = [types.Content(
            role="user",
            parts=[types.Part(text=full_prompt)]
        )]
        
        # Configure generation with JSON response format
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=4096,
            candidate_count=1,
            safety_settings=self._get_safety_settings(),
            response_mime_type="application/json",  # Force JSON output
        )
        
        # Retry logic
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                
                # Check for blocked content
                if not response.candidates:
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                        if block_reason:
                            raise GeminiResponseError(f"Content blocked: {block_reason}")
                    raise GeminiResponseError("No response generated")
                
                # Extract text from response
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, 'finish_reason', None)
                if finish_reason and str(finish_reason).upper() == "SAFETY":
                    raise GeminiResponseError("Response blocked for safety reasons")
                
                if not candidate.content or not candidate.content.parts:
                    raise GeminiResponseError("Empty response from Gemini")
                
                response_text = candidate.content.parts[0].text
                
                # Parse and return JSON - should be valid due to response_mime_type
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Fallback: try to extract JSON object
                    return self._extract_json_object(response_text)
                    
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}, retrying...")
                    await asyncio.sleep(1)
                    continue
                raise
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                if "429" in str(e) or "quota" in error_str or "rate" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Gemini rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    raise GeminiRateLimitError(f"Rate limit exceeded: {e}") from e
                
                if attempt < max_retries - 1:
                    logger.warning(f"Gemini error (attempt {attempt + 1}): {e}, retrying...")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                
                if isinstance(e, GeminiError):
                    raise
                raise GeminiResponseError(f"JSON generation failed: {e}") from e
        
        raise last_error or GeminiResponseError("JSON generation failed after retries")
    
    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """Extract the first valid JSON object from text."""
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
                    json_str = text[start:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        return json.loads(self._fix_json_syntax(json_str))
        
        raise json.JSONDecodeError("No valid JSON object found", text, 0)
    
    def _sanitize_control_chars(self, text: str) -> str:
        """Sanitize control characters that break JSON parsing.
        
        Control characters (0x00-0x1F) inside JSON strings must be escaped.
        This function properly escapes them while preserving valid escape sequences.
        """
        import re
        
        def escape_control_chars_in_strings(match):
            """Escape control chars inside a matched JSON string."""
            s = match.group(0)
            content = s[1:-1]  # Remove surrounding quotes
            
            result = []
            i = 0
            while i < len(content):
                char = content[i]
                if char == '\\' and i + 1 < len(content):
                    result.append(content[i:i+2])
                    i += 2
                elif ord(char) < 32:  # Control character
                    if char == '\n':
                        result.append('\\n')
                    elif char == '\r':
                        result.append('\\r')
                    elif char == '\t':
                        result.append('\\t')
                    elif char == '\x08':
                        result.append('\\b')
                    elif char == '\x0c':
                        result.append('\\f')
                    else:
                        result.append(f'\\u{ord(char):04x}')
                    i += 1
                else:
                    result.append(char)
                    i += 1
            
            return '"' + ''.join(result) + '"'
        
        json_string_pattern = r'"(?:[^"\\]|\\.)*"'
        return re.sub(json_string_pattern, escape_control_chars_in_strings, text)

    def _fix_json_syntax(self, text: str) -> str:
        """Try to fix common JSON syntax errors."""
        import re
        
        # First sanitize control characters
        text = self._sanitize_control_chars(text)
        
        # Handle newlines inside strings
        lines = text.split('\n')
        fixed_lines = []
        in_string = False
        for line in lines:
            quote_count = 0
            i = 0
            while i < len(line):
                if line[i] == '"' and (i == 0 or line[i-1] != '\\'):
                    quote_count += 1
                i += 1
            
            if in_string:
                fixed_lines[-1] = fixed_lines[-1] + '\\n' + line
            else:
                fixed_lines.append(line)
            
            if quote_count % 2 == 1:
                in_string = not in_string
        
        text = '\n'.join(fixed_lines)
        
        # Remove trailing commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        
        # Fix unquoted keys
        text = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
        
        # Escape remaining control characters (fallback)
        text = text.replace('\t', '\\t')
        text = text.replace('\r', '')
        
        return text

    async def check_health(self) -> bool:
        """Check if Gemini API is available."""
        try:
            # Try a minimal generation
            response = await self.generate(
                prompt="Say 'ok'",
                max_tokens=5,
            )
            return len(response) > 0
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False


# Alias exceptions to match LLM service interface
LLMError = GeminiError
LLMConnectionError = GeminiConnectionError
LLMTimeoutError = GeminiTimeoutError
LLMResponseError = GeminiResponseError
