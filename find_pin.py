# RGB keyboard stand - find the LED data pin
#
# Run this when you don't know which GPIO the strip's DIN is soldered to. That is
# the normal situation after flashing stock Raspberry Pi Pico CircuitPython, which
# has no `board.NEOPIXEL` because it knows nothing about this board.
#
# Copy onto the CIRCUITPY drive renamed to `code.py`, then just watch the strip.
# No serial console needed: when the correct pin is reached the strip lights, and
# it then flashes its own number at you.
#
# The number is encoded in flash LENGTH, not colour, so it stays readable even if
# the colour order is wrong or the strip turns out not to be plain RGB:
#
#   1. three rapid blips     -> "found it, start counting"
#   2. LONG flashes          -> the tens digit
#   3. SHORT flashes         -> the units digit
#
# So blip-blip-blip, one long, six short = GP16.
# Blip-blip-blip and nothing after       = GP0.
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

BLIP = 0.09            # the three rapid "found it" blips
LONG_BLINK = 0.75      # tens digit - deliberately much longer than SHORT
SHORT_BLINK = 0.15     # units digit
GAP = 0.28             # gap between flashes

# Pins to leave alone. On a Raspberry Pi Pico these three are wired to internal
# functions (SMPS mode, VBUS sense, onboard LED) rather than brought out, so
# testing them is pointless. Harmless to clear this if your board differs.
SKIP = ("GP23", "GP24", "GP25")

# --------------------------------------------------------------- internals ----


# Every channel of every pixel on, sent at RGBW width. This lights the strip
# whatever its colour order is and whether it is RGB or RGBW: on a 3-byte strip
# the surplus simply cascades off the end. The point is that the code below
# carries no colour or alignment meaning - only flash length matters.
ON = bytearray([LEVEL] * (NUM_PIXELS * 4))
OFF = bytearray(NUM_PIXELS * 4)


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
    """Three blips to get attention, then the pin number in long/short flashes."""
    for _ in range(3):
        pulse(pin_out, ON, BLIP)
        time.sleep(BLIP)
    time.sleep(1.0)

    tens, units = divmod(number, 10)
    for _ in range(tens):
        pulse(pin_out, ON, LONG_BLINK)
        time.sleep(GAP)
    if tens:
        time.sleep(0.6)        # clear separation between the two digits
    for _ in range(units):
        pulse(pin_out, ON, SHORT_BLINK)
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
    print("When you see three rapid blips, keep watching and count:")
    print("  LONG flashes = tens, SHORT flashes = units.")
    print("  e.g. blips, 1 long, 6 short = GP16.  blips, nothing after = GP0.")
    print("Colour does not matter here - only how long each flash lasts.")
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
