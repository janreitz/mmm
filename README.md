# Marta Musik Maschine
Before doing anything, checkout the associated blog post series at [martamusikmaschine.com](https://martamusikmaschine.com).

Marta Musik Maschine is a DIY, RFID enabled, multi-purpose, audio and light device for kids. It's open source and you can build one yourself. It's not hard at all, I promise.

This repository contains all the code needed on the Raspberry Pi, a KiCad project that enables you to etch/order a PCB and a few stl models that you can print on a 3D printer.

# Updates

# Additions

## DAC

The phatdac installer script and manual no longer work in newer PiOS versions. Adding the following lines to `/boot/firmware/config.txt` enables it.

```sh
# Device tree overlay for the hifiberry DAC is compatible
dtoverlay=hifiberry-dac
dtparam=i2s=on
```

To actually get sound output from the DAC, the `XSMT` pin must be connected to logical HIGH (3.3V) indicating unmute and the `FMT` pin to logical LOW (GND) indicating I2S communication. This can be done cleanly by bridging the solder pads on the bottom of the PCB (3->H/4->L).

## SDM63000

In addition to setting the baud rate for the serial input, I had to disable buffering (`stty -F /dev/serial0 raw`) to be able to read serial input with standard tools like `cat`.

## Buttons

The rpi-gpio package no longer works starting PiOS bookworm, because the gpio interface was changed. The rpi-lgpio package provides a compatibility shim. Installation via the package manager, as described on the lgpio docs site, did not work for me (`sudo apt install python3-rpi-lgpio`). I needed to install a few dependencies via `apt` before I successfully getting and building rpi-lgpio via pip.
- `sudo apt install swig liblgpio-dev`
- (In a venv) `pip3 install rpi-lgpio`

## Serial interface

