#!/usr/bin/env python3
"""
Setup utility for cross-platform deployment
Detects platform and installs appropriate dependencies
"""
import subprocess
import sys
import platform
import os

IS_RASPBERRY_PI = 'arm' in platform.machine().lower() or os.path.exists('/proc/device-tree/model')
IS_WINDOWS = sys.platform.startswith('win')

def run_command(cmd, shell=False):
    """Run shell command and return success status"""
    try:
        subprocess.check_call(cmd, shell=shell)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("\n" + "="*60)
    print("Face Recognition System - Setup Utility")
    print("="*60)
    
    # Detect platform
    if IS_RASPBERRY_PI:
        print("\n[DETECTED] Raspberry Pi System")
        print("Installing optimized dependencies for Raspberry Pi...")
        
        # Update system
        print("\n[STEP 1] Updating system packages...")
        if run_command("sudo apt-get update && sudo apt-get upgrade -y", shell=True):
            print("✓ System updated")
        else:
            print("⚠ Could not update system (might require sudo)")
        
        # Install Python dev
        print("\n[STEP 2] Installing Python development headers...")
        if run_command("sudo apt-get install -y python3-dev python3-pip", shell=True):
            print("✓ Python dev installed")
        
        # Install OpenCV dependencies
        print("\n[STEP 3] Installing OpenCV dependencies...")
        if run_command("sudo apt-get install -y libjasper-dev libtiff5 libjasper1 libtiff5", shell=True):
            print("✓ OpenCV dependencies installed")
        
        # Create venv
        print("\n[STEP 4] Creating virtual environment...")
        if run_command("python3 -m venv venv", shell=True):
            print("✓ Virtual environment created")
        else:
            print("✗ Failed to create virtual environment")
            print("  Try: python3 -m venv venv")
            return
        
        # Install requirements
        print("\n[STEP 5] Installing Python dependencies (this may take a while)...")
        cmd = "source venv/bin/activate && pip install -r requirements-pi.txt"
        
        if run_command(cmd, shell=True):
            print("✓ Dependencies installed")
        else:
            print("⚠ Some dependencies may have failed to install")
            print("  Try: source venv/bin/activate && pip install -r requirements-pi.txt")
        
    elif IS_WINDOWS:
        print("\n[DETECTED] Windows System")
        print("Installing full dependencies for Windows...")
        
        # Create venv
        print("\n[STEP 1] Creating virtual environment...")
        if run_command("python -m venv venv", shell=True):
            print("✓ Virtual environment created")
        else:
            print("✗ Failed to create virtual environment")
            print("  Try: python -m venv venv")
            return
        
        # Install requirements
        print("\n[STEP 2] Installing Python dependencies...")
        cmd = "venv\\Scripts\\pip install -r requirements-windows.txt"
        if run_command(cmd, shell=True):
            print("✓ Dependencies installed")
        else:
            print("⚠ Some dependencies may have failed to install")
            print("  Try: venv\\Scripts\\pip install -r requirements-windows.txt")
    else:
        print("\n[DETECTED] Linux System (Generic)")
        print("Installing dependencies for Linux...")
        
        # Create venv
        print("\n[STEP 1] Creating virtual environment...")
        if run_command("python3 -m venv venv", shell=True):
            print("✓ Virtual environment created")
        else:
            print("✗ Failed to create virtual environment")
            print("  Try: python3 -m venv venv")
            return
        
        # Install requirements
        print("\n[STEP 2] Installing Python dependencies...")
        cmd = "source venv/bin/activate && pip install -r requirements-pi.txt"
        if run_command(cmd, shell=True):
            print("✓ Dependencies installed")
        else:
            print("⚠ Some dependencies may have failed to install")
            print("  Try: source venv/bin/activate && pip install -r requirements-pi.txt")
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    
    if IS_WINDOWS:
        print("\nTo start the application:")
        print("  1. venv\\Scripts\\activate")
        print("  2. python app.py")
    else:
        print("\nTo start the application:")
        print("  1. source venv/bin/activate")
        print("  2. python3 app.py")
    
    print("\nAccess the dashboard at: http://localhost:5000")
    print("\nFor more information, see SETUP_GUIDE.md")

if __name__ == "__main__":
    main()
