#!/usr/bin/env python
"""
Local Model Inference Service

Handles local LLM inference for DGX Spark deployment.
Supports multiple model backends (vLLM, Ollama, Transformers) and GPU optimization.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
import threading
from datetime import datetime

import torch
import numpy as np
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    pipeline,
    BitsAndBytesConfig
)
from peft import PeftModel

from app.core.config import settings
from app.services.training_service import TrainingService

logger = logging.getLogger(__name__)

class LocalModelConfig:
    """Configuration for local model deployment."""
    
    def __init__(self):
        # Model paths and settings
        self.base_model_path = os.environ.get(
            "LOCAL_MODEL_PATH", 
            "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
        )
        self.lora_adapter_path = os.environ.get("LORA_ADAPTER_PATH", None)
        self.model_cache_dir = os.environ.get("MODEL_CACHE_DIR", "./models")
        
        # Hardware optimization
        self.device_map = "auto"
        self.torch_dtype = "auto"
        self.use_flash_attention = os.environ.get("USE_FLASH_ATTN", "true").lower() == "true"
        self.max_memory = self._get_max_memory_config()
        
        # Generation settings
        self.max_new_tokens = int(os.environ.get("MAX_NEW_TOKENS", "2048"))
        self.temperature = float(os.environ.get("TEMPERATURE", "0.7"))
        self.top_p = float(os.environ.get("TOP_P", "0.9"))
        self.top_k = int(os.environ.get("TOP_K", "50"))
        self.repetition_penalty = float(os.environ.get("REPETITION_PENALTY", "1.1"))
        
        # Quantization settings
        self.use_4bit = os.environ.get("USE_4BIT", "true").lower() == "true"
        self.use_8bit = os.environ.get("USE_8BIT", "false").lower() == "true"
        
        # Batch settings
        self.batch_size = int(os.environ.get("BATCH_SIZE", "4"))
        self.max_batch_size = int(os.environ.get("MAX_BATCH_SIZE", "8"))
        
    def _get_max_memory_config(self) -> Dict[str, str]:
        """Get max memory configuration for GPU."""
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            max_memory = {}
            for i in range(gpu_count):
                gpu_memory = torch.cuda.get_device_properties(i).total_memory
                # Use 80% of available memory
                max_memory[i] = f"{int(gpu_memory * 0.8 / 1024**3)}GB"
            return max_memory
        return {}
    
    def get_quantization_config(self):
        """Get quantization configuration."""
        if self.use_4bit:
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        elif self.use_8bit:
            return BitsAndBytesConfig(load_in_8bit=True)
        return None

class LocalModelManager:
    """
    Manages local model loading, inference, and GPU optimization.
    
    Supports:
    - Multiple GPU setups (DGX Spark)
    - LoRA adapter loading
    - Dynamic batching
    - Memory optimization
    - Model hot-swapping
    """
    
    def __init__(self):
        self.config = LocalModelConfig()
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.current_adapter = None
        self.model_loaded = False
        self.loading_lock = threading.Lock()
        
        # Performance metrics
        self.generation_count = 0
        self.total_generation_time = 0.0
        self.last_load_time = None
        
        # Initialize training service for adapter management
        self.training_service = TrainingService()
    
    async def load_model(self, adapter_path: Optional[str] = None) -> bool:
        """
        Load the base model and optionally a LoRA adapter.
        
        Args:
            adapter_path: Path to LoRA adapter to load
            
        Returns:
            True if model loaded successfully
        """
        with self.loading_lock:
            try:
                logger.info(f"Loading model: {self.config.base_model_path}")
                
                # Load tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.config.base_model_path,
                    cache_dir=self.config.model_cache_dir,
                    trust_remote_code=True
                )
                
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                
                # Load model with optimizations
                model_kwargs = {
                    "torch_dtype": self.config.torch_dtype,
                    "device_map": self.config.device_map,
                    "cache_dir": self.config.model_cache_dir,
                    "trust_remote_code": True,
                }
                
                # Add memory configuration
                if self.config.max_memory:
                    model_kwargs["max_memory"] = self.config.max_memory
                
                # Add quantization if enabled
                quant_config = self.config.get_quantization_config()
                if quant_config:
                    model_kwargs["quantization_config"] = quant_config
                
                # Flash attention
                if self.config.use_flash_attention:
                    model_kwargs["attn_implementation"] = "flash_attention_2"
                
                # Load base model
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.config.base_model_path,
                    **model_kwargs
                )
                
                # Load LoRA adapter if specified
                if adapter_path and Path(adapter_path).exists():
                    logger.info(f"Loading LoRA adapter: {adapter_path}")
                    self.model = PeftModel.from_pretrained(self.model, adapter_path)
                    self.current_adapter = adapter_path
                elif self.config.lora_adapter_path and Path(self.config.lora_adapter_path).exists():
                    logger.info(f"Loading default LoRA adapter: {self.config.lora_adapter_path}")
                    self.model = PeftModel.from_pretrained(self.model, self.config.lora_adapter_path)
                    self.current_adapter = self.config.lora_adapter_path
                
                # Create generation pipeline
                self.pipeline = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    max_new_tokens=self.config.max_new_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    top_k=self.config.top_k,
                    repetition_penalty=self.config.repetition_penalty,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    return_full_text=False,
                    batch_size=self.config.batch_size
                )
                
                self.model_loaded = True
                self.last_load_time = datetime.utcnow()
                
                # Log model info
                gpu_memory = self._get_gpu_memory_info()
                logger.info(f"Model loaded successfully. GPU memory: {gpu_memory}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.model_loaded = False
                return False
    
    async def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate text using the local model.
        
        Args:
            prompt: Input prompt
            max_new_tokens: Override max tokens
            temperature: Override temperature
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        if not self.model_loaded:
            if not await self.load_model():
                raise RuntimeError("Failed to load model")
        
        start_time = time.time()
        
        try:
            # Prepare generation parameters
            gen_kwargs = {
                "max_new_tokens": max_new_tokens or self.config.max_new_tokens,
                "temperature": temperature or self.config.temperature,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
                "repetition_penalty": self.config.repetition_penalty,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id,
                "return_full_text": False,
                **kwargs
            }
            
            # Generate
            result = self.pipeline(prompt, **gen_kwargs)
            
            # Extract generated text
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0]["generated_text"]
            else:
                generated_text = str(result)
            
            # Update metrics
            generation_time = time.time() - start_time
            self.generation_count += 1
            self.total_generation_time += generation_time
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
    
    async def generate_batch(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[str]:
        """
        Generate text for multiple prompts in batch.
        
        Args:
            prompts: List of input prompts
            **kwargs: Generation parameters
            
        Returns:
            List of generated texts
        """
        if not self.model_loaded:
            if not await self.load_model():
                raise RuntimeError("Failed to load model")
        
        # Process in batches to avoid memory issues
        results = []
        batch_size = min(self.config.max_batch_size, len(prompts))
        
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i + batch_size]
            
            try:
                batch_results = self.pipeline(batch, **kwargs)
                
                for result in batch_results:
                    if isinstance(result, dict) and "generated_text" in result:
                        results.append(result["generated_text"].strip())
                    else:
                        results.append(str(result).strip())
                        
            except Exception as e:
                logger.error(f"Batch generation failed for batch {i//batch_size}: {e}")
                # Fallback to individual generation
                for prompt in batch:
                    try:
                        result = await self.generate(prompt, **kwargs)
                        results.append(result)
                    except Exception as e2:
                        logger.error(f"Individual generation failed: {e2}")
                        results.append(f"Error: {str(e2)}")
        
        return results
    
    async def switch_adapter(self, adapter_path: str) -> bool:
        """
        Switch to a different LoRA adapter.
        
        Args:
            adapter_path: Path to new adapter
            
        Returns:
            True if switch successful
        """
        if adapter_path == self.current_adapter:
            return True  # Already loaded
        
        try:
            # Unload current adapter if any
            if self.current_adapter and hasattr(self.model, 'unload'):
                self.model.unload()
            
            # Load new adapter
            if Path(adapter_path).exists():
                self.model = PeftModel.from_pretrained(self.model, adapter_path)
                self.current_adapter = adapter_path
                logger.info(f"Switched to adapter: {adapter_path}")
                return True
            else:
                logger.error(f"Adapter path not found: {adapter_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to switch adapter: {e}")
            return False
    
    async def get_active_adapter_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded adapter."""
        if not self.current_adapter:
            return {"adapter": None, "message": "No adapter loaded"}
        
        try:
            # Get adapter metadata from training service
            async with AsyncSessionLocal() as db:
                # This would need to be implemented in training service
                pass
        except:
            pass
        
        return {
            "adapter_path": self.current_adapter,
            "base_model": self.config.base_model_path,
            "loaded_at": self.last_load_time.isoformat() if self.last_load_time else None
        }
    
    def _get_gpu_memory_info(self) -> Dict[str, str]:
        """Get GPU memory usage information."""
        if not torch.cuda.is_available():
            return {"message": "CUDA not available"}
        
        gpu_info = {}
        for i in range(torch.cuda.device_count()):
            memory_allocated = torch.cuda.memory_allocated(i) / 1024**3  # GB
            memory_reserved = torch.cuda.memory_reserved(i) / 1024**3   # GB
            total_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3  # GB
            
            gpu_info[f"gpu_{i}"] = {
                "allocated_gb": f"{memory_allocated:.2f}",
                "reserved_gb": f"{memory_reserved:.2f}",
                "total_gb": f"{total_memory:.2f}",
                "utilization": f"{(memory_allocated / total_memory) * 100:.1f}%"
            }
        
        return gpu_info
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        avg_time = self.total_generation_time / max(1, self.generation_count)
        
        return {
            "generations": self.generation_count,
            "total_time": self.total_generation_time,
            "avg_time_per_generation": avg_time,
            "generations_per_second": 1.0 / avg_time if avg_time > 0 else 0,
            "model_loaded": self.model_loaded,
            "current_adapter": self.current_adapter,
            "gpu_memory": self._get_gpu_memory_info()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the model service."""
        health = {
            "status": "healthy",
            "model_loaded": self.model_loaded,
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.model_loaded:
            try:
                # Test generation
                test_prompt = "Test prompt"
                start_time = time.time()
                result = await self.generate(test_prompt, max_new_tokens=10)
                generation_time = time.time() - start_time
                
                health["test_generation"] = {
                    "success": True,
                    "time_seconds": generation_time,
                    "result_length": len(result)
                }
            except Exception as e:
                health["test_generation"] = {
                    "success": False,
                    "error": str(e)
                }
                health["status"] = "degraded"
        
        return health

# Global instance
local_model_manager = LocalModelManager()
