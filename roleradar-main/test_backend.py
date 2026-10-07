#!/usr/bin/env python3
"""
Test script to check backend imports and functionality
"""

import sys
import os
sys.path.insert(0, '.')

def test_imports():
    """Test if all imports work correctly"""
    print("🔍 Testing Backend Imports...")
    
    try:
        print("1. Testing config import...")
        from config import config
        print("✅ Config imported successfully")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        print("2. Testing ai_modules import...")
        from ai_modules.interview_practice import InterviewPracticeSystem
        print("✅ AI modules imported successfully")
    except Exception as e:
        print(f"❌ AI modules import failed: {e}")
        return False
    
    try:
        print("3. Testing backend.main import...")
        from backend.main import app
        print(f"✅ Backend main imported successfully")
        print(f"   App title: {app.title}")
        print(f"   App version: {app.version}")
    except Exception as e:
        print(f"❌ Backend main import failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_interview_system():
    """Test the interview practice system"""
    print("\n🎤 Testing Interview System...")
    
    try:
        from ai_modules.interview_practice import InterviewPracticeSystem
        
        system = InterviewPracticeSystem()
        print("✅ Interview system initialized")
        
        # Test role-specific questions
        job_requirements = {
            'title': 'Software Engineer',
            'skills_required': [{'name': 'Python'}, {'name': 'JavaScript'}],
            'specific_job': False
        }
        
        import asyncio
        async def test_session():
            session = await system.start_interview_session(
                job_requirements,
                role='software_engineer',
                specific_job=False
            )
            return session
        
        session = asyncio.run(test_session())
        print(f"✅ Interview session created: {session['session_id']}")
        print(f"   Questions generated: {len(session['questions'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Interview system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Tech Jobs Crawler - Backend Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed!")
        sys.exit(1)
    
    # Test interview system
    if not test_interview_system():
        print("\n❌ Interview system test failed!")
        sys.exit(1)
    
    print("\n🎉 All tests passed! Backend is ready.")
    print("🌐 To start the server, run:")
    print("   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload")