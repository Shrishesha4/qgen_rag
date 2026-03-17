# 🚀 DGX Spark Deployment Guide for QGen RAG System

## 📋 Overview

This guide walks you through deploying the QGen RAG system on NVIDIA DGX Spark for production-scale SLM/LLM training and inference. The system implements a dual-engine architecture with adaptive learning capabilities.

## 🏗️ System Architecture

### Core Components
- **PostgreSQL + pgvector**: Vector database for embeddings and training data
- **Redis**: Caching and session management
- **Backend API**: FastAPI with GPU-accelerated inference
- **Training Worker**: Background training jobs on GPU
- **Frontend**: SvelteKit web interface
- **Monitoring**: Prometheus + Grafana

### ML Pipeline
- **Local Model Inference**: DeepSeek-R1-Distill-Llama with LoRA adapters
- **Constitutional AI**: Automated quality filtering
- **Adaptive Learning**: Multi-subject difficulty adaptation
- **Training Pipeline**: SFT + DPO with continuous learning

## 🔧 Prerequisites

### Hardware Requirements
- **DGX Spark** or equivalent multi-GPU system
- **GPU Memory**: Minimum 32GB total (8GB+ per GPU)
- **System Memory**: 128GB+ RAM
- **Storage**: 1TB+ SSD fast storage
- **Network**: 10Gbps+ for model downloads

### Software Requirements
- **NVIDIA Driver**: 525.60+ 
- **CUDA**: 12.0+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.9+

## 📦 Installation

### 1. System Setup

```bash
# Clone the repository
git clone <repository-url>
cd qgen_rag

# Run the DGX Spark setup script
sudo ./scripts/setup_dgx_spark.sh
```

### 2. Environment Configuration

Edit the generated environment file:

```bash
nano /opt/qgen/.env
```

Set these critical variables:
```bash
# External APIs
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here

# Model Configuration
LOCAL_MODEL_PATH=deepseek-ai/DeepSeek-R1-Distill-Llama-8B

# Security
SECRET_KEY=your_secret_key_here
```

### 3. Start the System

```bash
cd /opt/qgen
docker-compose -f docker-compose.dgx.yml up -d
```

### 4. Verify Deployment

```bash
# Check service status
docker-compose -f docker-compose.dgx.yml ps

# Check GPU utilization
nvidia-smi

# Check logs
docker-compose -f docker-compose.dgx.yml logs -f backend
```

## 🎯 Data Collection & Training Workflow

### Phase 1: Initial Data Collection

1. **Access the Frontend**
   - URL: `http://your-dgx-ip:5173`
   - Create teacher and vetter accounts

2. **Upload Reference Materials**
   - Navigate to "Documents" section
   - Upload PDFs, textbooks, and reference materials
   - Wait for processing and embedding

3. **Generate Initial Questions**
   - Use "Generate Questions" feature
   - Start with easier topics to build baseline
   - Target 1000+ approved questions per subject

### Phase 2: Vetting & Feedback Collection

1. **Vetting Process**
   - Students/Experts review generated questions
   - Provide detailed feedback on:
     - Question clarity
     - Answer correctness
     - Difficulty appropriateness
     - Educational value

2. **Quality Metrics to Track**
   - Approval rate by subject/difficulty
   - Common rejection reasons
   - Edit patterns and improvements
   - Time spent per question

### Phase 3: Model Training

1. **Trigger Training**
   ```bash
   # Via API
   curl -X POST "http://your-dgx-ip:8000/api/v1/training/trigger" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"training_method": "sft+dpo"}'
   ```

2. **Monitor Training**
   - Grafana: `http://your-dgx-ip:3000`
   - Check loss curves and metrics
   - Monitor GPU utilization

3. **Model Evaluation**
   - Automatic evaluation on held-out data
   - Human evaluation on sample questions
   - Performance comparison across versions

### Phase 4: Adaptive Learning

1. **Difficulty Calibration**
   - System learns what constitutes "easy/medium/hard" per subject
   - Automatic difficulty prediction and validation
   - Continuous refinement based on vetting feedback

2. **Subject Specialization**
   - Model learns subject-specific patterns
   - Optimal question types per domain
   - Topic-difficulty mapping

## 📊 Monitoring & Optimization

### Key Metrics

1. **Generation Quality**
   - Approval rate by subject/difficulty
   - Rejection reason distribution
   - Edit frequency and patterns

2. **Training Performance**
   - Loss curves (SFT/DPO)
   - GPU utilization
   - Training time per epoch

3. **System Performance**
   - Inference latency
   - Queue depth
   - Memory usage

### Grafana Dashboards

Access Grafana at `http://your-dgx-ip:3000` (admin/admin)

Pre-configured dashboards:
- **System Overview**: Overall health and performance
- **Training Pipeline**: Training job status and metrics
- **Quality Analytics**: Question quality and approval rates
- **GPU Monitoring**: GPU utilization and memory

## 🔄 Continuous Improvement Loop

### Daily Operations

1. **Data Collection**
   - Target: 100+ new vetted questions per day
   - Diverse subjects and difficulty levels
   - Quality feedback from multiple vetters

2. **Model Updates**
   - Weekly SFT training on new approved questions
   - Monthly DPO training on preference pairs
   - Quarterly evaluation and model promotion

3. **Quality Assurance**
   - Monitor approval rates (target: 80%+)
   - Track rejection patterns
   - Adjust generation parameters

### Advanced Features

1. **Multi-Subject Learning**
   - System automatically adapts to different domains
   - Cross-subject knowledge transfer
   - Specialized adapters per subject

2. **Difficulty Adaptation**
   - Dynamic difficulty calibration
   - Personalized difficulty per user group
   - Automatic difficulty adjustment based on performance

3. **Constitutional AI**
   - Automated quality filtering
   - Reduced vetter workload
   - Consistent quality standards

## 🛠️ Troubleshooting

### Common Issues

1. **GPU Memory Issues**
   ```bash
   # Check GPU memory
   nvidia-smi
   
   # Reduce batch size in .env
   BATCH_SIZE=2
   MAX_BATCH_SIZE=4
   ```

2. **Training Failures**
   ```bash
   # Check training logs
   docker-compose logs training_worker
   
   # Common fixes:
   # - Reduce learning rate
   # - Increase gradient accumulation
   # - Use 4-bit quantization
   ```

3. **Slow Inference**
   ```bash
   # Check model loading
   curl http://your-dgx-ip:8000/api/v1/model/health
   
   # Optimize:
   # - Enable flash attention
   # - Use tensor parallelism
   # - Increase batch size
   ```

### Performance Tuning

1. **GPU Optimization**
   ```bash
   # Enable mixed precision
   USE_FLASH_ATTN=true
   
   # Optimize memory usage
   USE_4BIT=true
   MAX_MEMORY_GPU0=24GB
   ```

2. **Database Optimization**
   ```sql
   -- Vector index for similarity search
   CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops);
   
   -- Partition large tables
   CREATE TABLE questions_y2024m01 PARTITION OF questions;
   ```

3. **Caching Strategy**
   ```bash
   # Redis configuration
   REDIS_MAXMEMORY=16gb
   REDIS_POLICY=allkeys-lru
   ```

## 📈 Scaling Considerations

### Horizontal Scaling

1. **Multiple GPU Nodes**
   - Deploy training workers on separate nodes
   - Use distributed training (FSDP/DeepSpeed)
   - Load balance inference across nodes

2. **Database Scaling**
   - Read replicas for question serving
   - Partitioned tables for training data
   - Connection pooling

3. **Frontend Scaling**
   - CDN for static assets
   - Load balancer for multiple instances
   - Session affinity for user state

### Model Scaling

1. **Larger Base Models**
   - DeepSeek-R1-Distill-Llama-70B
   - Custom fine-tuned models
   - Model ensembles

2. **Specialized Adapters**
   - Per-subject LoRA adapters
   - Difficulty-specific adapters
   - Domain-specific adapters

## 🔐 Security & Compliance

### Data Security

1. **Encryption**
   - Database encryption at rest
   - Network encryption (TLS)
   - API authentication

2. **Access Control**
   - Role-based permissions
   - API rate limiting
   - Audit logging

### Model Security

1. **Model Protection**
   - Encrypted model storage
   - Access-controlled model downloads
   - Model versioning and rollback

2. **Output Filtering**
   - Content safety checks
   - PII detection and removal
   - Output validation

## 📚 API Reference

### Training Endpoints

```bash
# Trigger training
POST /api/v1/training/trigger
{
  "training_method": "sft+dpo",
  "base_model": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
  "hyperparameters": {
    "learning_rate": 2e-4,
    "num_epochs": 3
  }
}

# Get training status
GET /api/v1/training/status

# List model versions
GET /api/v1/training/versions

# Activate model version
POST /api/v1/training/versions/{id}/activate
```

### Generation Endpoints

```bash
# Generate questions
POST /api/v1/questions/generate
{
  "subject_id": "uuid",
  "count": 10,
  "difficulty": "medium",
  "types": ["mcq", "short_answer"]
}

# Get generation status
GET /api/v1/questions/status/{subject_id}
```

## 🎯 Success Metrics

### Quality Targets
- **Approval Rate**: 80%+ across all subjects
- **Difficulty Accuracy**: 85%+ correct difficulty labeling
- **Educational Value**: 90%+ pedagogically sound questions

### Performance Targets
- **Inference Latency**: <2 seconds per question
- **Training Time**: <4 hours for 10k samples
- **GPU Utilization**: 70%+ during training

### Scale Targets
- **Daily Generation**: 1000+ questions
- **Active Users**: 100+ concurrent
- **Model Updates**: Weekly improvements

## 🔄 Maintenance Schedule

### Daily
- Monitor system health
- Check training job status
- Review quality metrics

### Weekly
- Trigger model training
- Update adaptive learning profiles
- Performance optimization

### Monthly
- Model evaluation and promotion
- Database maintenance
- Security updates

### Quarterly
- Architecture review
- Capacity planning
- Feature roadmap updates

## 📞 Support

### Technical Support
- **Documentation**: `/docs` directory
- **Logs**: `/opt/qgen/logs`
- **Monitoring**: Grafana dashboards

### Community
- **Issues**: GitHub repository
- **Discussions**: Developer forum
- **Updates**: Newsletter and blog

---

**🎉 Congratulations!** You now have a production-ready SLM/LLM training system running on DGX Spark. The system will continuously improve through human feedback and adaptive learning, becoming better at generating educational content over time.
