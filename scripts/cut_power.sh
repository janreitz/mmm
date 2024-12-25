#!/bin/bash

case "$1" in
    poweroff)
        # Set GPIO4 to LOW using gpioset
        # Replace "gpiochip0" with your actual chip name if different
        /usr/bin/gpioset gpiochip0 4=0
        sleep 0.5
        ;;
esac