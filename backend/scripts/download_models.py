#!/usr/bin/env python
"""
Pre-download ML models for offline/cached usage.
Runs during Docker build to populate the image with models.
Models persist in the Docker volume at runtime.
"""

import sys
from pathlib import Path
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def download_only_if_missing():
    """Download reranker model from Hugging Face (skips if import works)."""
    try:
        # Try importing - if this works, model is already available
        from sentence_transformers import CrossEncoder
        
        # Try to instantiate without downloading (will use cached if available)
        # Set cache_folder to ensure we're using the right location
        import os
        os.environ["HF_HOME"] = "/root/.cache"
        
        print(f"📥 Loading reranker model: {settings.RERANKER_MODEL}...")
        model = CrossEncoder(settings.RERANKER_MODEL, cache_folder="/root/.cache/huggingface")
        
        # Force the model to actually load (not just initialize)
        _ = model.predict([("test", "test")])
        
        print(f"✅ Reranker model ready: {settings.RERANKER_MODEL}")
        print(f"   Cache location: /root/.cache")
        return True
    except Exception as e:
        print(f"⚠️ Model loading failed: {e}")
        print(f"   (This is normal on first build - will cache for next time)")
        return False


def main():
    """Download all required ML models."""
    import os
    
    # Ensure cache directory exists and is writable
    cache_dir = Path("/root/.cache/huggingface")
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Initializing ML models (cache: {cache_dir})...")
    
    os.environ["HF_HOME"] = "/root/.cache"
    
    success = download_only_if_missing()
    
    if success:
        print("✅ All models cached successfully")
        sys.exit(0)
    else:
        print("⚠️ Model pre-download deferred to first request (will cache then)")
        sys.exit(0)  # Non-fatal


if __name__ == "__main__":
    main()
