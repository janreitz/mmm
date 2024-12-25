#!/usr/bin/env python3

from gpiozero import Button
import subprocess
import signal
import sys
import time

# Configure GPIO17 as input with pull-up
# When button is pressed, it will be pulled LOW
button = Button(17, pull_up=True)

def signal_handler(signum, frame):
    print("Received signal to terminate")
    sys.exit(0)

def shutdown():
    print("Button press detected - initiating shutdown")
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])

def main():
    # Register signal handlers for graceful termination
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print("Power management daemon started")
    
    # Wait for button press
    # hold_time ensures we don't trigger on accidental brief presses
    button.when_held = shutdown
    button.hold_time = 2.0  # Requires 2 second hold to trigger

    # Keep the script running
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()