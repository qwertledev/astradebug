# RGB keyboard stand - find the LED data pin
#
# Run this when you don't know which GPIO the strip's DIN is soldered to. That is
# the normal situation after flashing stock Raspberry Pi Pico CircuitPython, which
# has no `board.NEOPIXEL` because it knows nothing about this board.
#
# Copy over code.py on the CIRCUITPY drive, open the serial console, and watch the
# strip. It drives each GPIO in turn with a NeoPixel signal and prints the pin name
# as it goes. When the strip lights up, the pin printed at that moment is yours.
#
# Then put that name into DATA_PIN_NAME at the top of code.py, e.g.
#
#     DATA_PIN_NAME = "GP0"
#
# It loops forever, so you get as many passes as you need to catch it.

import time

import board
import digitalio
import microcontroller
import neopixel_write

# ----------------------------------------------------------------- config ----

NUM_PIXELS = 30        # WS2812B count on the stand
DWELL = 1.2            # seconds to hold each pin lit
LEVEL = 60             # 0-255 per channel; bright enough to spot, low current
COLOR_ORDER = "GRB"

# Pins to leave alone. On a Raspberry Pi Pico these three are wired to internal
# functions (SMPS mode, VBUS sense, onboard LED) rather than brought out, so
# testing them is pointless. Harmless to clear this if your board differs.
SKIP = ("GP23", "GP24", "GP25")

# --------------------------------------------------------------- internals ----

_ORDER = tuple("RGB".index(c) for c in COLOR_ORDER)


def gp_pins():
    """Every GPn pin the firmware exposes, in numeric order."""
    found = []
    for name in dir(board):
        if not name.startswith("GP") or name in SKIP:
            continue
        if not isinstance(getattr(board, name, None), microcontroller.Pin):
            continue
        try:
            number = int(name[2:])
        except ValueError:
            continue          # e.g. GPIO aliases that aren't plain GPn
        found.append((number, name))
    return [name for _, name in sorted(found)]


def frame(rgb):
    buf = bytearray(NUM_PIXELS * 3)
    for i in range(NUM_PIXELS):
        base = i * 3
        for slot, source in enumerate(_ORDER):
            buf[base + slot] = rgb[source]
    return buf


LIT = frame((LEVEL, LEVEL, LEVEL))
OFF = frame((0, 0, 0))


def test(name):
    """Drive one pin with a NeoPixel signal. Returns False if unusable."""
    try:
        pin_out = digitalio.DigitalInOut(getattr(board, name))
        pin_out.direction = digitalio.Direction.OUTPUT
    except Exception as exc:  # noqa: BLE001 - in use by USB, flash, etc.
        print("  {:<6} skipped ({})".format(name, exc))
        return False

    try:
        neopixel_write.neopixel_write(pin_out, LIT)
        time.sleep(DWELL)
        neopixel_write.neopixel_write(pin_out, OFF)
        time.sleep(0.2)
    finally:
        pin_out.deinit()
    return True


def main():
    pins = gp_pins()
    if not pins:
        raise RuntimeError(
            "This firmware exposes no GPn pins, which is unexpected on an RP2040. "
            "Check that you flashed a Raspberry Pi Pico CircuitPython build."
        )

    print("\n" + "=" * 56)
    print("LED data pin finder - {} pixels".format(NUM_PIXELS))
    print("=" * 56)
    print("Watch the strip. When it lights, note the pin printed at")
    print("that moment, then set DATA_PIN_NAME in code.py to it.")
    print("\nTesting {} pins, {}s each (~{:.0f}s per pass):\n".format(
        len(pins), DWELL, len(pins) * (DWELL + 0.2)))

    while True:
        for name in pins:
            print("  {:<6} <- watch now".format(name))
            test(name)
        print("\n  --- end of pass, starting over ---\n")
        time.sleep(1.0)


try:
    main()
except Exception as err:  # noqa: BLE001
    print("\n--- find_pin.py failed ---")
    try:
        import traceback
        traceback.print_exception(err)
    except Exception:  # noqa: BLE001
        print("{}: {}".format(type(err).__name__, err))
    raise
