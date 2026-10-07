@echo off
echo Starting Tech Jobs Crawler Backend Server...
echo.

cd /d "D:\7"

echo Backend starting on http://localhost:8000...
echo Open frontend in browser: file:///D:/7/frontend/index.html
echo.

:: Try to start the server
python -c "
import sys
import os
sys.path.append('.')

# Import and run the FastAPI app
try:
    from backend.main import app
    import uvicorn
    print('✅ Backend loaded successfully')
    print('🌐 Starting server on http://localhost:8000')
    uvicorn.run(app, host='0.0.0.0', port=8000)
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('💡 Make sure you have: pip install fastapi uvicorn')
except Exception as e:
    print(f'❌ Server error: {e}')
except KeyboardInterrupt:
    print('\n🛑 Server stopped by user')
"

pause