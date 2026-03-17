#!/usr/bin/env python
"""
Training Worker for DGX Spark

Background worker that processes training jobs, model evaluation,
and adaptive learning tasks. Designed to run on GPU nodes.
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.database import AsyncSessionLocal
from app.core.logging import setup_logging
from app.services.training_service import TrainingService
from app.services.adaptive_learning_service import adaptive_learning_service
from app.services.local_model_service import local_model_manager
from app.services.queue_service import QueueService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class TrainingWorker:
    """
    Background worker for training tasks on DGX Spark.
    
    Handles:
    - SFT/DPO training jobs
    - Model evaluation
    - Adaptive learning updates
    - Model hot-swapping
    """
    
    def __init__(self):
        self.training_service = TrainingService()
        self.queue_service = QueueService()
        self.running = True
        self.worker_id = os.environ.get("WORKER_ID", "training-worker-1")
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def run(self):
        """Main worker loop."""
        logger.info(f"Training worker {self.worker_id} starting...")
        
        # Initialize local model
        await local_model_manager.load_model()
        
        # Main processing loop
        while self.running:
            try:
                # Process training jobs
                await self._process_training_jobs()
                
                # Process adaptive learning updates
                await self._process_adaptive_learning()
                
                # Process model evaluations
                await self._process_evaluations()
                
                # Health check and maintenance
                await self._maintenance_tasks()
                
                # Brief pause to prevent busy-waiting
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(10)
        
        logger.info("Training worker shutting down...")
    
    async def _process_training_jobs(self):
        """Process pending training jobs."""
        try:
            async with AsyncSessionLocal() as db:
                # Get next pending job
                job = await self.queue_service.dequeue_job("training")
                if not job:
                    return
                
                logger.info(f"Processing training job: {job.id}")
                
                # Run the training job
                result = await self.training_service.run_training_job(
                    job_id=job.payload["job_id"],
                    db=db
                )
                
                logger.info(f"Training job completed: {result}")
                
                # Update queue
                await self.queue_service.complete_job(job.id, result)
                
        except Exception as e:
            logger.error(f"Failed to process training job: {e}")
    
    async def _process_adaptive_learning(self):
        """Process adaptive learning updates."""
        try:
            # Check if we need to update learning profiles
            # This could be triggered by new vetting data or time-based updates
            
            async with AsyncSessionLocal() as db:
                # Update learning profiles from recent vetting
                await adaptive_learning_service._load_profiles()
                
                logger.debug("Adaptive learning profiles updated")
                
        except Exception as e:
            logger.error(f"Failed to update adaptive learning: {e}")
    
    async def _process_evaluations(self):
        """Process model evaluation jobs."""
        try:
            async with AsyncSessionLocal() as db:
                # Get next evaluation job
                job = await self.queue_service.dequeue_job("evaluation")
                if not job:
                    return
                
                logger.info(f"Processing evaluation job: {job.id}")
                
                # Run evaluation
                result = await self.training_service.process_evaluation_job(
                    evaluation_id=job.payload["evaluation_id"],
                    db=db
                )
                
                logger.info(f"Evaluation job completed: {result}")
                
                # Update queue
                await self.queue_service.complete_job(job.id, result)
                
        except Exception as e:
            logger.error(f"Failed to process evaluation job: {e}")
    
    async def _maintenance_tasks(self):
        """Perform maintenance tasks."""
        try:
            # Check model health
            health = await local_model_manager.health_check()
            if health["status"] != "healthy":
                logger.warning(f"Model health issue: {health}")
            
            # Log performance metrics
            metrics = local_model_manager.get_performance_metrics()
            logger.debug(f"Model metrics: {metrics}")
            
            # Cleanup old training data if needed
            # This could be implemented based on storage constraints
            
        except Exception as e:
            logger.error(f"Maintenance task failed: {e}")

async def main():
    """Main entry point."""
    worker = TrainingWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
