#!/usr/bin/env python3
"""
Fix auth database permissions and ensure it's writable.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings

def fix_auth_db():
    """Check and fix auth database permissions."""
    
    # Extract the file path from the database URL
    # sqlite+aiosqlite:///./auth.db -> ./auth.db
    db_path = settings.AUTH_DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    db_path = Path(db_path).resolve()
    
    print(f"🔍 Checking auth database at: {db_path}")
    
    # Check if database exists
    if not db_path.exists():
        print(f"📝 Creating auth database at: {db_path}")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty database file
        db_path.touch()
        print(f"✅ Created auth database file")
    else:
        print(f"✅ Auth database exists")
    
    # Check permissions
    if os.access(db_path, os.R_OK | os.W_OK):
        print(f"✅ Auth database is readable and writable")
    else:
        print(f"❌ Auth database is NOT readable/writable")
        print(f"🔧 Attempting to fix permissions...")
        
        try:
            # Try to make it writable
            os.chmod(db_path, 0o644)
            print(f"✅ Fixed permissions")
        except PermissionError as e:
            print(f"❌ Cannot fix permissions: {e}")
            print(f"💡 Try running with: sudo chmod 644 {db_path}")
            return False
    
    # Check directory permissions
    if os.access(db_path.parent, os.R_OK | os.W_OK | os.X_OK):
        print(f"✅ Directory is accessible")
    else:
        print(f"❌ Directory is NOT accessible")
        print(f"💡 Try running with: sudo chmod 755 {db_path.parent}")
        return False
    
    # Test write access
    try:
        with open(db_path, 'a') as f:
            f.write("")
        print(f"✅ Write test successful")
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        return False
    
    print(f"\n✅ Auth database is ready!")
    return True

if __name__ == "__main__":
    success = fix_auth_db()
    sys.exit(0 if success else 1)
