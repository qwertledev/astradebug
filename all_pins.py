# RGB keyboard stand - blink the strip without knowing which pin it is on
#
# This is the "is anything connected at all" test. Instead of trying pins one at
# a time, it drives EVERY GPIO with the same LED data, over and over. Whichever
# pin your strip's DIN is soldered to receives valid data, so the strip blinks -
# and you learn that without having to identify the pin first.
#
# Copy onto CIRCUITPY renamed to `code.py` and watch for about ten seconds.
#
#   Strip blinks on/off once a second
#       -> Power, ground, data line and solder joints are all good, and the pin
#          is somewhere in the scanned set. Run find_pin.py to name it.
#
#   Strip stays completely dark
#       -> Nothing is reaching it. The problem is physical: the data wire is not
#          landing on a GPIO, DIN and DOUT are reversed (the strip is
#          directional - the arrows must point AWAY from the microcontroller),
#          or the strip has no 5 V / ground.
#
# One caveat: this briefly drives every general-purpose pin as an output. That is
# fine for a pin wired to an LED strip or left unconnected, but if some other
# component on the board drives a pin as an output too, the two fight each other.
# It is a short diagnostic rather than something to leave running.

import time

import board
import digitalio
import microcontroller
import neopixel_write

# ----------------------------------------------------------------- config ----

NUM_PIXELS = 30
LEVEL = 40             # 0-255 per channel. ~310 mA on 30 LEDs - safe on USB.
PERIOD = 1.0           # seconds on, seconds off

# Internal-function pins on a Raspberry Pi Pico (SMPS mode, VBUS sense, LED).
SKIP = ("GP23", "GP24", "GP25")

# --------------------------------------------------------------- internals ----

# Every channel on, so this shows up whatever the colour order and whether the
# strip is RGB or RGBW. The extra byte on a 4-byte strip is covered because we
# send enough data for the wider format too.
ON = bytearray([LEVEL] * (NUM_PIXELS * 4))
OFF = bytearray(NUM_PIXELS * 4)


def claim_pins():
    """Grab every GPn pin as an output. Returns [(name, DigitalInOut)]."""
    held = []
    entries = []
    for name in dir(board):
        if not name.startswith("GP") or name in SKIP:
            continue
        if not isinstance(getattr(board, name, None), microcontroller.Pin):
            continue
        try:
            entries.append((int(name[2:]), name))
        except ValueError:
            continue

    for _, name in sorted(entries):
        try:
            pin_out = digitalio.DigitalInOut(getattr(board, name))
            pin_out.direction = digitalio.Direction.OUTPUT
            held.append((name, pin_out))
        except Exception as exc:  # noqa: BLE001 - already in use, skip it
            print("  {:<6} unavailable ({})".format(name, exc))
    return held


def blast(held, buf):
    for _, pin_out in held:
        try:
            neopixel_write.neopixel_write(pin_out, buf)
        except Exception:  # noqa: BLE001 - never let one pin stop the sweep
            pass


def main():
    held = claim_pins()
    if not held:
        raise RuntimeError(
            "No GPn pins available. Check you flashed a Raspberry Pi Pico "
            "CircuitPython build."
        )

    print("\n" + "=" * 58)
    print("all-pins blink test - {} pixels, {} pins".format(
        NUM_PIXELS, len(held)))
    print("=" * 58)
    print("driving: " + ", ".join(name for name, _ in held))
    print("\nWatch the strip for ~10 seconds.")
    print("  blinking once a second -> data path is GOOD, run find_pin.py next")
    print("  completely dark        -> nothing is reaching the strip (wiring)")
    print()

    try:
        count = 0
        while True:
            blast(held, ON)
            time.sleep(PERIOD)
            blast(held, OFF)
            time.sleep(PERIOD)
            count += 1
            print("  blink {}".format(count))
    finally:
        blast(held, OFF)
        for _, pin_out in held:
            pin_out.deinit()


try:
    main()
except Exception as err:  # noqa: BLE001
    print("\n--- all_pins.py failed ---")
    try:
        import traceback
        traceback.print_exception(err)
    except Exception:  # noqa: BLE001
        print("{}: {}".format(type(err).__name__, err))
    raise
