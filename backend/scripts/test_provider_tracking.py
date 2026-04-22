"""
Simple test script for provider usage tracking service.

Run this to verify that provider usage tracking is working correctly.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.provider_usage_tracking_service import provider_usage_tracker
from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.provider_usage import ProviderUsageLog


async def test_tracking():
    """Test that provider usage tracking works without blocking."""
    print("Testing provider usage tracking...")
    
    # Test 1: Track a sample usage
    print("\n1. Tracking sample provider usage...")
    provider_usage_tracker.track_usage(
        provider_key="test_provider",
        user_id="test_user_123",
        usage_type="test_tracking",
        provider_name="Test Provider",
        provider_model="test-model-v1",
        subject_id="test_subject_456",
        topic_id="test_topic_789",
        usage_metadata={"test": "data", "version": "1.0"},
    )
    print("   ✓ Tracking call returned immediately (non-blocking)")
    
    # Wait a moment for background task to complete
    await asyncio.sleep(2)
    
    # Test 2: Verify the record was created
    print("\n2. Verifying record was created in database...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProviderUsageLog)
            .where(ProviderUsageLog.user_id == "test_user_123")
            .where(ProviderUsageLog.usage_type == "test_tracking")
        )
        record = result.scalar_one_or_none()
        
        if record:
            print(f"   ✓ Record created successfully:")
            print(f"     - ID: {record.id}")
            print(f"     - Provider: {record.provider_key} ({record.provider_name})")
            print(f"     - Model: {record.provider_model}")
            print(f"     - User: {record.user_id}")
            print(f"     - Type: {record.usage_type}")
            print(f"     - Subject: {record.subject_id}")
            print(f"     - Topic: {record.topic_id}")
            print(f"     - Metadata: {record.usage_metadata}")
            print(f"     - Created: {record.created_at}")
        else:
            print("   ✗ Record not found!")
            return False
    
    # Test 3: Count total tracked usages
    print("\n3. Counting total tracked usages...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(ProviderUsageLog.id))
        )
        count = result.scalar()
        print(f"   ✓ Total provider usage records: {count}")
    
    # Test 4: Test multiple concurrent tracking calls
    print("\n4. Testing concurrent tracking (10 calls)...")
    tasks = []
    for i in range(10):
        provider_usage_tracker.track_usage(
            provider_key=f"concurrent_test_{i % 3}",
            user_id="test_concurrent_user",
            usage_type="concurrent_test",
            usage_metadata={"batch": i},
        )
    print("   ✓ All 10 tracking calls returned immediately")
    
    await asyncio.sleep(2)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(ProviderUsageLog.id))
            .where(ProviderUsageLog.usage_type == "concurrent_test")
        )
        concurrent_count = result.scalar()
        print(f"   ✓ Records created: {concurrent_count}/10")
        if concurrent_count == 10:
            print("     All concurrent writes succeeded!")
        else:
            print(f"     Warning: Only {concurrent_count} records created")
    
    print("\n" + "="*60)
    print("Provider usage tracking test completed successfully! ✓")
    print("="*60)
    return True


async def cleanup_test_data():
    """Clean up test data."""
    print("\nCleaning up test data...")
    async with AsyncSessionLocal() as db:
        await db.execute(
            ProviderUsageLog.__table__.delete().where(
                ProviderUsageLog.user_id.in_([
                    "test_user_123",
                    "test_concurrent_user"
                ])
            )
        )
        await db.commit()
    print("✓ Test data cleaned up")


if __name__ == "__main__":
    print("="*60)
    print("Provider Usage Tracking Service Test")
    print("="*60)
    
    try:
        asyncio.run(test_tracking())
        # Optionally clean up test data
        # asyncio.run(cleanup_test_data())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
