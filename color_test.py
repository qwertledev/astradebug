# RGB keyboard stand - work out the colour order
#
# Run this once find_pin.py has told you which pin the strip is on. It answers two
# questions that the pin finder deliberately avoids:
#
#   * which byte position drives which colour (the COLOR_ORDER setting), and
#   * whether the strip is plain RGB or actually RGBW.
#
# Set DATA_PIN below, copy this onto CIRCUITPY renamed to `code.py`, and watch.
#
# It does NOT assume a colour order. It lights one byte position at a time and
# tells you (on serial, if you have it) which position is lit. All you have to do
# is note the colour you actually see for each of the three, in order.
#
# Report them back as: slot 1 = ?, slot 2 = ?, slot 3 = ?
#
#   slot 1 red,   slot 2 green, slot 3 blue  -> COLOR_ORDER = "RGB"
#   slot 1 green, slot 2 red,   slot 3 blue  -> COLOR_ORDER = "GRB"  (usual WS2812B)
#
# If all three slots look white-ish, or the strip only partly lights, the strip is
# probably RGBW - the final stage checks for that.

import time

import board
import digitalio
import neopixel_write

# ----------------------------------------------------------------- config ----

DATA_PIN = "GP9"       # <-- the pin find_pin.py identified
NUM_PIXELS = 30
LEVEL = 70             # 0-255
HOLD = 2.5             # seconds to show each state
DARK = 1.0             # dark gap between states, so the states are countable

# --------------------------------------------------------------- internals ----


def send(pin_out, buf):
    neopixel_write.neopixel_write(pin_out, buf)


def slot_frame(slot, bytes_per_pixel):
    """Light exactly one byte position in every pixel."""
    buf = bytearray(NUM_PIXELS * bytes_per_pixel)
    for i in range(NUM_PIXELS):
        buf[i * bytes_per_pixel + slot] = LEVEL
    return buf


def blank(bytes_per_pixel):
    return bytearray(NUM_PIXELS * bytes_per_pixel)


def stage(pin_out, label, buf, bytes_per_pixel):
    print("  {}".format(label))
    send(pin_out, buf)
    time.sleep(HOLD)
    send(pin_out, blank(bytes_per_pixel))
    time.sleep(DARK)


def main():
    pin = getattr(board, DATA_PIN, None)
    if pin is None:
        raise RuntimeError(
            "board.{} does not exist. Set DATA_PIN to the pin find_pin.py "
            "reported, e.g. \"GP0\".".format(DATA_PIN)
        )

    pin_out = digitalio.DigitalInOut(pin)
    pin_out.direction = digitalio.Direction.OUTPUT

    print("\n" + "=" * 58)
    print("colour test on board.{} - {} pixels".format(DATA_PIN, NUM_PIXELS))
    print("=" * 58)
    print("Note the colour you see at each stage. Order matters.\n")

    try:
        while True:
            print("--- 3-byte RGB mode ---")
            for slot in range(3):
                stage(pin_out,
                      "slot {} of 3".format(slot + 1),
                      slot_frame(slot, 3), 3)

            print("--- all three together (should be WHITE) ---")
            full = bytearray(NUM_PIXELS * 3)
            for i in range(len(full)):
                full[i] = LEVEL
            stage(pin_out, "all slots", full, 3)

            print("--- 4-byte RGBW mode ---")
            print("    If the strip looked wrong above but these look clean,")
            print("    it is an RGBW strip and BYTES_PER_PIXEL should be 4.")
            for slot in range(4):
                stage(pin_out,
                      "rgbw slot {} of 4".format(slot + 1),
                      slot_frame(slot, 4), 4)

            print("\n  --- end of pass, starting over ---\n")
            time.sleep(2.0)
    finally:
        send(pin_out, blank(4))
        pin_out.deinit()


try:
    main()
except Exception as err:  # noqa: BLE001
    print("\n--- color_test.py failed ---")
    try:
        import traceback
        traceback.print_exception(err)
    except Exception:  # noqa: BLE001
        print("{}: {}".format(type(err).__name__, err))
    raise
