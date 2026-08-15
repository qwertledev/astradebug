# RGB keyboard stand - lighting
#
# Drop this on the root of the CIRCUITPY drive as `code.py` and the stand glows.
#
# No libraries needed. This drives the LEDs through the built-in `neopixel_write`
# module rather than the `neopixel` library, so there is no bundle to download and
# no version mismatch to get wrong. Nothing to add to the hardware either.
#
# Set NUM_PIXELS below to your real LED count. That is usually the only edit.

import time

import board
import digitalio
import neopixel_write

# ----------------------------------------------------------------- config ----

NUM_PIXELS = 16        # <-- set this to your real LED count
BRIGHTNESS = 0.25      # 0.0-1.0. See the power note at the bottom of this file.
COLOR_ORDER = "GRB"    # WS2812B is GRB. Use "RGB" if red and green come out swapped.
DATA_PIN_NAME = None   # None = auto-detect, or force e.g. "GP0" / "NEOPIXEL"

EFFECTS = ("rainbow", "breathe", "comet")   # cycled in this order
EFFECT_SECONDS = 20    # how long each effect runs; None = never switch
FPS = 50

# Perceptual correction. LEDs are linear, eyes are not; without this, fades look
# like they snap to full near the top of the range and crush to black at the bottom.
GAMMA = bytes(int(pow(i / 255, 2.6) * 255 + 0.5) for i in range(256))

_ORDER = tuple("RGB".index(c) for c in COLOR_ORDER)

# ---------------------------------------------------------------- helpers ----


def wheel(pos):
    """0-255 around the colour wheel -> (r, g, b) at full saturation."""
    pos &= 255
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def scale(rgb, level):
    return (int(rgb[0] * level), int(rgb[1] * level), int(rgb[2] * level))


def render(pin_out, pattern):
    """Gamma-correct, apply brightness, reorder to the wire format, and send."""
    buf = bytearray(NUM_PIXELS * 3)
    for i, rgb in enumerate(pattern):
        base = i * 3
        for slot, source in enumerate(_ORDER):
            buf[base + slot] = int(GAMMA[rgb[source] & 255] * BRIGHTNESS)
    neopixel_write.neopixel_write(pin_out, buf)


# ---------------------------------------------------------------- effects ----


def rainbow(t):
    """Full spectrum wrapped around the strip, rotating."""
    offset = int(t * 60)
    return [wheel(offset + i * 255 // NUM_PIXELS) for i in range(NUM_PIXELS)]


def breathe(t):
    """Whole strip one slowly drifting hue, swelling and fading."""
    phase = (t / 5.0) % 1.0
    level = 1.0 - abs(phase * 2.0 - 1.0)       # triangle wave, 0 -> 1 -> 0
    level = 0.05 + 0.95 * level                # never fully dark
    return [scale(wheel(int(t * 8)), level)] * NUM_PIXELS


def comet(t):
    """A bright head chasing a fading tail around the strip."""
    tail = max(3, NUM_PIXELS // 3)
    head = (t * 12.0) % NUM_PIXELS
    colour = wheel(int(t * 20))
    out = []
    for i in range(NUM_PIXELS):
        distance = (head - i) % NUM_PIXELS
        level = 1.0 - distance / tail
        out.append(scale(colour, level) if level > 0 else (0, 0, 0))
    return out


RENDERERS = {"rainbow": rainbow, "breathe": breathe, "comet": comet}

# ------------------------------------------------------------------ setup ----


def is_pin(obj):
    import microcontroller
    return isinstance(obj, microcontroller.Pin)


def find_data_pin():
    if DATA_PIN_NAME:
        return DATA_PIN_NAME
    candidates = [
        n for n in dir(board)
        if "NEOPIXEL" in n.upper()
        and "POWER" not in n.upper()
        and is_pin(getattr(board, n, None))
    ]
    return candidates[0] if candidates else None


def is_led_power(name):
    """A power-gate pin for the LEDs specifically - not some unrelated rail."""
    upper = name.upper()
    return "POWER" in upper and ("NEOPIXEL" in upper or "LED" in upper)


def enable_power():
    """Some boards gate LED power behind a pin that has to be driven high."""
    held = []
    for name in dir(board):
        if is_led_power(name) and is_pin(getattr(board, name, None)):
            try:
                gate = digitalio.DigitalInOut(getattr(board, name))
                gate.direction = digitalio.Direction.OUTPUT
                gate.value = True
                held.append(gate)
                print("enabled board.{}".format(name))
            except Exception as exc:  # noqa: BLE001
                print("could not drive board.{}: {}".format(name, exc))
    return held


def main():
    pin_name = find_data_pin()
    if pin_name is None:
        raise RuntimeError(
            "No NEOPIXEL pin found on this board. Set DATA_PIN_NAME at the top "
            "of code.py to the pin your strip's DIN is soldered to, e.g. \"GP0\"."
        )

    print("stand lighting: {} pixels on board.{}, brightness {}".format(
        NUM_PIXELS, pin_name, BRIGHTNESS))

    enable_power()

    pin_out = digitalio.DigitalInOut(getattr(board, pin_name))
    pin_out.direction = digitalio.Direction.OUTPUT

    frame_time = 1.0 / FPS
    index = 0
    started = time.monotonic()

    while True:
        now = time.monotonic()

        if EFFECT_SECONDS and now - started >= EFFECT_SECONDS:
            index = (index + 1) % len(EFFECTS)
            started = now
            print("effect: {}".format(EFFECTS[index]))

        render(pin_out, RENDERERS[EFFECTS[index]](now))
        time.sleep(frame_time)


try:
    main()
except Exception as err:  # noqa: BLE001 - surface it instead of a bare red blink
    # Without this you get CircuitPython's two faint red status blinks and no
    # explanation. Print the real traceback to the serial console instead.
    print("\n--- code.py failed ---")
    try:
        import traceback
        traceback.print_exception(err)
    except Exception:  # noqa: BLE001 - traceback signatures vary by version
        print("{}: {}".format(type(err).__name__, err))
    raise


# Power note
# ----------
# WS2812B LEDs draw up to ~60 mA each at full white; a USB 2.0 port gives 500 mA.
# BRIGHTNESS caps that, and none of the effects above light every LED at full
# white simultaneously, so 0.25 is comfortable for a typical stand. Before turning
# it up, check the headroom:
#
#     python3 tools/power_budget.py <your led count>
#
# If the strip browns out or the board resets when you raise BRIGHTNESS, that is
# the USB port's current limit, not a bug - feed the strip from its own 5 V supply
# with the grounds tied together.
