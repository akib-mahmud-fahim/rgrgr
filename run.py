import uvicorn
import webbrowser
import threading
import time
import os

def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"\n[AutoClip Pro] Opening web application at: {url}\n")
    webbrowser.open(url)

if __name__ == "__main__":
    print("==================================================")
    print(" 🎬 AutoClip Pro - Automated Video Slicer & Manager")
    print(" Localhost Server Starting on http://127.0.0.1:8000")
    print("==================================================")
    
    # Auto open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn server
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
