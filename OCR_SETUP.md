# OCR Setup Guide

## Overview

The OCR implementation is fully integrated into the document processing pipeline. When scanned/image-heavy PDFs are detected, the system automatically attempts OCR extraction using Tesseract.

## Architecture

### Backend Flow
1. **Native Extraction** → PyMuPDF extracts text from PDF
2. **Scanned Detection** → Analyzes text density across pages
   - If <30% of pages have ≥50 characters → considered scanned
3. **OCR Fallback** → Renders pages as images and runs Tesseract
4. **Retry Logic** → Up to 2 retries per page with exponential backoff
5. **Progress Tracking** → Real-time updates sent to frontend

### Frontend Display
- Orange progress bar and "OCR" badge when Tesseract is processing
- Extraction method stored: `"native"` or `"ocr"`
- `used_ocr` boolean flag in document metadata

## Configuration

**Backend settings** (`app/core/config.py`):
```python
OCR_ENABLED: bool = True              # Master toggle
OCR_MIN_TEXT_PER_PAGE: int = 50       # Min chars to consider page has text
OCR_SPARSE_THRESHOLD: float = 0.3     # <30% pages with text = scanned
OCR_LANGUAGE: str = "eng"             # Tesseract language
OCR_MAX_RETRIES: int = 2              # Retries per page
OCR_DPI: int = 300                    # Image resolution for OCR
```

## Installation

### Local Development (macOS/Linux)

#### 1. Install Tesseract

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Fedora/RHEL:**
```bash
sudo dnf install tesseract
```

#### 2. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

The requirements already include:
- `pytesseract` (Python Tesseract interface)
- `Pillow` (image processing for OCR)
- PyMuPDF and other extraction libraries

#### 3. Run Backend Locally
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

Due to repository mirror issues, the Docker image doesn't include Tesseract by default.

**Option A: Run Backend Locally, Use Docker for Services Only**
```bash
# Start PostgreSQL, Redis, etc. via Docker
docker compose up -d db redis

# Install Tesseract locally
brew install tesseract

# Run app locally
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Option B: Custom Docker Image with Tesseract**

Create a custom Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Build tools and Tesseract OCR
RUN apt-get update && \
    apt-get install -y tesseract-ocr libpq-dev build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -f Dockerfile.ocr -t qgen_rag-api:ocr .
docker run -d \
  --name qgen_api \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  qgen_rag-api:ocr
```

**Option C: Multi-Stage Build**
- Base image with Tesseract + dependencies
- Second stage installs Python packages
- This reduces final image size

## Graceful Degradation

If Tesseract is **not** installed:
1. Native extraction still works normally
2. OCR detection runs but logs a warning
3. Processing continues with available native text
4. Frontend shows no OCR badge (no `used_ocr: true`)
5. Document still processes successfully with whatever text was extracted

All OCR code includes try/except blocks to prevent crashes:
```python
try:
    import pytesseract
    pytesseract.get_tesseract_version()
except ImportError:
    logger.warning("Tesseract not available - OCR disabled")
    return None  # Falls back to native extraction
```

## Testing OCR

### 1. Test with a Scanned PDF
Upload a scanned textbook or document:
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@scanned_book.pdf" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Monitor Logs
```bash
# Backend logs show OCR progress
# [2026-03-05 08:39:35.635] [ocr] 10% - Running OCR on 270 pages...
# [2026-03-05 08:39:40.123] [ocr] 50% - OCR processing page 135/270...
```

### 3. Check Document Status
```bash
curl http://localhost:8000/documents/{doc_id}/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response includes:
```json
{
  "extraction_method": "ocr",
  "used_ocr": true,
  "processing_detail": "Processing complete (OCR). 47 chunks, 6134 tokens."
}
```

## Performance Notes

- **Native extraction:** ~100ms for 270-page PDF
- **OCR processing:** ~5-10 seconds per 100 pages (depends on hardware)
- **DPI setting:** 300 DPI balances quality vs. speed
  - Lower (150-200): Faster, may lose detail
  - Higher (400+): Better quality, slower

## Troubleshooting

### "Tesseract binary not found"
```bash
# Check Tesseract is installed
which tesseract

# If missing, install it
brew install tesseract
```

### OCR is very slow
- Reduce `OCR_DPI` in config (e.g., 200 instead of 300)
- Increase `OCR_MAX_RETRIES` to skip retries on first failure (set to 0)
- Process documents in batches during off-peak hours

### OCR quality is poor
- Increase `OCR_DPI` (e.g., 400)
- Check if PDF is actually scanned (look at extracted text)
- For very old scans, may need preprocessing (contrast enhancement)

### Document marked as scanned incorrectly
- Adjust `OCR_MIN_TEXT_PER_PAGE` (amount of text required per page)
- Adjust `OCR_SPARSE_THRESHOLD` (percentage of pages needing text)

## Future Improvements

- [ ] Google Cloud Vision API fallback (for very complex scans)
- [ ] PDF preprocessing (automatic contrast/deskew)
- [ ] Caching of OCR results by file hash
- [ ] Async OCR processing with progress webhooks
- [ ] Language auto-detection
- [ ] Multi-language support
