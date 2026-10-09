"""
SafeBox: Server Launcher
Run via: python run.py
"""
import uvicorn
import sys

if __name__ == "__main__":
    print("=================================================================")
    print("Starting SafeBox Engine on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("Prometheus Metrics: http://localhost:8000/api/v1/metrics")
    print("Web Console: http://localhost:8000/")
    print("=================================================================")
    uvicorn.run("safebox.app.main:app", host="0.0.0.0", port=8000, reload=False)
