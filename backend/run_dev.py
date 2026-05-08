import subprocess
import os
import sys

def run_dev():
    """
    Optimized developer runner for the CELTM Backend.
    Limits uvicorn file-watching to the 'app' directory,
    preventing lag caused by scanning huge folders like '.next' or 'node_modules'.
    """
    print(">>> Starting Optimized CELTM Backend Runner...")
    print(">>> Watching directory: 'app'")
    print(">>> Ignoring: '.venv', 'node_modules', '.next', 'artifacts'")
    
    # Construct uvicorn command
    # - --reload: enables auto-reload
    # - --reload-dir app: ONLY watch the 'app' directory
    # - --reload-exclude '*': (Note: Uvicorn doesn't support glob exclude well alongside reload-dir, 
    #   but reload-dir 'app' is sufficient to ignore outside folders)
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "app.main:app", 
        "--host", "127.0.0.1", 
        "--port", "8000", 
        "--reload",
        "--reload-dir", "app"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n>>> Backend runner stopped by user.")
    except Exception as e:
        print(f"\n>>> Local runner error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_dev()
