# RGB keyboard stand - find the LED data pin
#
# Run this when you don't know which GPIO the strip's DIN is soldered to. That is
# the normal situation after flashing stock Raspberry Pi Pico CircuitPython, which
# has no `board.NEOPIXEL` because it knows nothing about this board.
#
# Copy onto the CIRCUITPY drive renamed to `code.py`, then just watch the strip.
# No serial console needed: when the correct pin is reached the strip lights, and
# it then blinks its own number at you.
#
#   1. solid GREEN for a second  -> "this is the pin"
#   2. long BLUE blinks          -> the tens digit
#   3. short WHITE blinks        -> the units digit
#
# So GREEN, then one long blue, then six short white = GP16.
# GREEN with no blinks at all    = GP0.
#
# Every other pin leaves the strip dark, so most of a pass is just waiting.
# It loops forever - you get as many passes as you need to count it.
#
# The same information is printed to the serial console if you have one open.

import time

import board
import digitalio
import microcontroller
import neopixel_write

# ----------------------------------------------------------------- config ----

NUM_PIXELS = 30        # WS2812B count on the stand
LEVEL = 60             # 0-255 per channel; bright to spot, low current
COLOR_ORDER = "GRB"

MARKER_SECONDS = 1.0   # length of the solid green "found it" marker
LONG_BLINK = 0.5       # tens digit
SHORT_BLINK = 0.18     # units digit
GAP = 0.18             # gap between blinks

# Pins to leave alone. On a Raspberry Pi Pico these three are wired to internal
# functions (SMPS mode, VBUS sense, onboard LED) rather than brought out, so
# testing them is pointless. Harmless to clear this if your board differs.
SKIP = ("GP23", "GP24", "GP25")

# --------------------------------------------------------------- internals ----

_ORDER = tuple("RGB".index(c) for c in COLOR_ORDER)


def frame(rgb):
    buf = bytearray(NUM_PIXELS * 3)
    for i in range(NUM_PIXELS):
        base = i * 3
        for slot, source in enumerate(_ORDER):
            buf[base + slot] = rgb[source]
    return buf


OFF = frame((0, 0, 0))
GREEN = frame((0, LEVEL, 0))
BLUE = frame((0, 0, LEVEL))
WHITE = frame((LEVEL, LEVEL, LEVEL))


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
    return sorted(found)


def pulse(pin_out, colour, seconds):
    neopixel_write.neopixel_write(pin_out, colour)
    time.sleep(seconds)
    neopixel_write.neopixel_write(pin_out, OFF)


def signal(pin_out, number):
    """Light the strip, then blink the pin number on it."""
    pulse(pin_out, GREEN, MARKER_SECONDS)
    time.sleep(0.4)

    tens, units = divmod(number, 10)
    for _ in range(tens):
        pulse(pin_out, BLUE, LONG_BLINK)
        time.sleep(GAP)
    if tens:
        time.sleep(0.3)
    for _ in range(units):
        pulse(pin_out, WHITE, SHORT_BLINK)
        time.sleep(GAP)


def test(number, name):
    """Drive one pin. Returns False if the pin is unusable."""
    try:
        pin_out = digitalio.DigitalInOut(getattr(board, name))
        pin_out.direction = digitalio.Direction.OUTPUT
    except Exception as exc:  # noqa: BLE001 - in use by USB, flash, etc.
        print("  {:<6} skipped ({})".format(name, exc))
        return False

    try:
        signal(pin_out, number)
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
    print("Watch the strip. Most pins leave it dark - that is expected.")
    print("When it lights GREEN, keep watching and count the blinks:")
    print("  long BLUE = tens, short WHITE = units.")
    print("  e.g. green, 1 long, 6 short = GP16.  green, nothing = GP0.")
    print("\nTesting {} pins, looping until you stop it.\n".format(len(pins)))

    while True:
        for number, name in pins:
            print("  {:<6} <- watch now".format(name))
            test(number, name)
            time.sleep(0.8)
        print("\n  --- end of pass, starting over ---\n")
        time.sleep(2.0)


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
