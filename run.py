import subprocess
import sys
import os
import webbrowser

def main():
    print("Installation des dépendances...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    print("Lancement de l'application...")
    webbrowser.open("http://127.0.0.1:8000/login.html")

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()