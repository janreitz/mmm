#!/usr/bin/env python3
"""
Smart power button daemon that coordinates with Marta
"""
from gpiozero import Button
import subprocess
import signal
import sys
import time
import os
import psutil

# Configure GPIO17 as input with pull-up
button = Button(17, pull_up=True)

def signal_handler(signum, frame):
    print("Received signal to terminate")
    sys.exit(0)

def is_marta_running():
    """Check if Marta.py is currently running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'Marta.py' in cmdline:
                    return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def graceful_marta_shutdown():
    """Send SIGINT to Marta to trigger graceful shutdown"""
    marta_pid = is_marta_running()
    if marta_pid:
        print(f"Found Marta running (PID: {marta_pid}), sending graceful shutdown signal...")
        try:
            os.kill(marta_pid, signal.SIGINT)
            
            # Wait up to 10 seconds for Marta to shut down gracefully
            for i in range(10):
                time.sleep(1)
                if not is_marta_running():
                    print("Marta shut down gracefully")
                    return True
                print(f"Waiting for Marta to shut down... ({i+1}/10)")
            
            print("Marta didn't shut down gracefully, proceeding with system shutdown")
            return False
        except ProcessLookupError:
            print("Marta process no longer exists")
            return True
        except PermissionError:
            print("Permission denied sending signal to Marta")
            return False
    else:
        print("Marta is not running")
        return True

def shutdown():
    """Handle shutdown sequence"""
    print("Button press detected - initiating shutdown sequence")
    
    # Try graceful Marta shutdown first
    if graceful_marta_shutdown():
        print("Proceeding with system shutdown")
    else:
        print("Forced system shutdown due to Marta not responding")
    
    # Give a moment for any final cleanup
    time.sleep(1)
    
    # Shutdown the system
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])

def main():
    # Register signal handlers for graceful termination
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Smart power management daemon started")
    print("Will coordinate with Marta for graceful shutdowns")
    
    # Wait for button press
    button.when_held = shutdown
    button.hold_time = 2.0  # Requires 2 second hold to trigger
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Daemon interrupted")
        sys.exit(0)

if __name__ == "__main__":
    main()