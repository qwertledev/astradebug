# RGB keyboard stand - staged LED diagnostic
#
# Only needed if the lights misbehave. To run it, copy this file over code.py
# on the CIRCUITPY drive (keep a copy of your own code.py first) and open the
# serial console.
#
# Uses the built-in `neopixel_write` module rather than the `neopixel` library, so
# it still runs when a missing or version-mismatched library bundle is the actual
# root cause. Current draw is kept tiny until the final stage, so a marginal 5 V
# rail cannot brown out mid-test and hide the result.

import sys
import time

import board
import digitalio
import microcontroller
import supervisor

try:
    import neopixel_write
except ImportError:
    neopixel_write = None

# ----------------------------------------------------------------- config ----

NUM_PIXELS = 16        # set this to your real LED count
BYTES_PER_PIXEL = 3    # 3 = WS2812/WS2812B/SK6812 RGB, 4 = SK6812 RGBW
COLOR_ORDER = "GRB"    # WS2812B is GRB. Try "RGB" if colours come out swapped.
DATA_PIN_NAME = None   # None = auto-detect, or force e.g. "GP0" / "NEOPIXEL"

WALK_LEVEL = 24        # 0-255 per channel for the one-at-a-time walk (~9%)
RAMP_LEVELS = (8, 24, 64, 128, 255)   # whole-strip stages
MA_PER_CHANNEL = 20.0  # full-on current per colour channel, per LED
MA_QUIESCENT = 1.0     # idle current per LED
USB_BUDGET_MA = 500.0  # USB 2.0 host port

# ---------------------------------------------------------------- helpers ----


def hr(title=""):
    print("\n" + "-" * 62)
    if title:
        print(title)
        print("-" * 62)


def show(obj, name):
    """Print an attribute without letting introspection crash the run."""
    try:
        print("  {:<22} {}".format(name, obj()))
    except Exception as exc:  # noqa: BLE001 - diagnostic, report everything
        print("  {:<22} <unavailable: {}>".format(name, exc))


def is_pin(obj):
    return isinstance(obj, microcontroller.Pin)


def encode(rgb, order):
    """Reorder an (r, g, b) tuple into the strip's wire order."""
    r, g, b = rgb
    channels = {"R": r, "G": g, "B": b}
    out = [channels[c] for c in order]
    if BYTES_PER_PIXEL == 4:
        out.append(0)  # W channel off - we are testing the RGB dies
    return out


def buffer_for(pattern):
    """pattern: list of (r, g, b), one per pixel."""
    buf = bytearray(NUM_PIXELS * BYTES_PER_PIXEL)
    for i, rgb in enumerate(pattern):
        buf[i * BYTES_PER_PIXEL:(i + 1) * BYTES_PER_PIXEL] = bytes(
            encode(rgb, COLOR_ORDER)
        )
    return buf


def estimate_ma(pattern):
    total = MA_QUIESCENT * len(pattern)
    for r, g, b in pattern:
        total += (r + g + b) / 255.0 * MA_PER_CHANNEL
    return total


def write(pin_out, pattern):
    neopixel_write.neopixel_write(pin_out, buffer_for(pattern))


def blank(pin_out):
    write(pin_out, [(0, 0, 0)] * NUM_PIXELS)


# ------------------------------------------------------------ 1. the board ----


def report_environment():
    hr("1. ENVIRONMENT")
    show(lambda: sys.implementation.name, "implementation")
    show(lambda: ".".join(str(v) for v in sys.implementation.version), "version")
    show(lambda: sys.platform, "platform")
    show(lambda: board.board_id, "board_id")
    show(lambda: microcontroller.cpu.reset_reason, "reset_reason")
    show(lambda: supervisor.runtime.safe_mode_reason, "safe_mode_reason")
    show(lambda: supervisor.runtime.usb_connected, "usb_connected")
    show(lambda: supervisor.runtime.serial_connected, "serial_connected")

    print("\n  Interpreting the two that matter:")
    print("    reset_reason == BROWNOUT      -> the 5 V rail is collapsing (power problem)")
    print("    safe_mode_reason != NONE      -> code.py was skipped entirely this boot")
    print("    both NONE/POWER_ON            -> clean boot; a red 2-blink is a code.py bug")


# ------------------------------------------------------------- 2. the pins ----


def find_pins():
    hr("2. PIN DISCOVERY")

    names = sorted(n for n in dir(board) if not n.startswith("_"))
    pins = [n for n in names if is_pin(getattr(board, n, None))]
    print("  {} pin objects exposed by `board`".format(len(pins)))
    print("  " + ", ".join(pins) if pins else "  (none)")

    power = [n for n in pins
             if "POWER" in n.upper()
             and ("NEOPIXEL" in n.upper() or "LED" in n.upper())]
    if power:
        print("\n  LED power-gate candidates: {}".format(", ".join(power)))

    if DATA_PIN_NAME:
        chosen = DATA_PIN_NAME
        print("\n  Data pin forced by config: {}".format(chosen))
    else:
        preferred = [n for n in pins if "NEOPIXEL" in n.upper() and "POWER" not in n.upper()]
        chosen = preferred[0] if preferred else None
        if chosen:
            print("\n  Auto-detected data pin: board.{}".format(chosen))
        else:
            print("\n  !! No NEOPIXEL pin exposed by this board definition.")
            print("     Set DATA_PIN_NAME at the top of this file to the pin you")
            print("     actually soldered the strip's DIN to, e.g. \"GP0\".")

    return chosen, power


def enable_power(power_names):
    """Drive any LED power-gate pin so the strip is actually fed."""
    held = []
    for name in power_names:
        try:
            gate = digitalio.DigitalInOut(getattr(board, name))
            gate.direction = digitalio.Direction.OUTPUT
            gate.value = True
            held.append(gate)
            print("  enabled board.{} (set high)".format(name))
        except Exception as exc:  # noqa: BLE001
            print("  could not drive board.{}: {}".format(name, exc))
    return held


# ------------------------------------------------------- 3. data-line test ----


def walk(pin_out):
    """One LED at a time, dim. Draws a few mA - tests DATA, not power."""
    hr("3. DATA TEST - one LED at a time, ~{}% brightness".format(
        round(WALK_LEVEL / 255 * 100)))
    print("  Each pixel should light white in turn, from the DIN end outward.")
    print("  Estimated peak draw: {:.0f} mA - safe on any USB port.\n".format(
        estimate_ma([(WALK_LEVEL,) * 3]) + MA_QUIESCENT * NUM_PIXELS))

    for i in range(NUM_PIXELS):
        pattern = [(0, 0, 0)] * NUM_PIXELS
        pattern[i] = (WALK_LEVEL, WALK_LEVEL, WALK_LEVEL)
        write(pin_out, pattern)
        print("    pixel {:>3} / {}".format(i + 1, NUM_PIXELS))
        time.sleep(0.15)

    blank(pin_out)
    print("\n  How many lit?")
    print("    all of them      -> data path is good, go to stage 4")
    print("    none             -> wrong data pin, DIN/DOUT reversed, or no common ground")
    print("    only the first N -> break in the chain after pixel N (check that joint)")


def colours(pin_out):
    hr("4. COLOUR ORDER - whole strip, still dim")
    for name, rgb in (("RED", (WALK_LEVEL, 0, 0)),
                      ("GREEN", (0, WALK_LEVEL, 0)),
                      ("BLUE", (0, 0, WALK_LEVEL))):
        write(pin_out, [rgb] * NUM_PIXELS)
        print("    showing {}".format(name))
        time.sleep(0.8)
    blank(pin_out)
    print("\n  If the names don't match what you saw, change COLOR_ORDER at the top")
    print("  (WS2812B = \"GRB\"; some clones are \"RGB\").")


# ------------------------------------------------------ 4. the power ramp ----


def ramp(pin_out):
    hr("5. POWER TEST - whole strip, increasing brightness")
    print("  Watch for the stage where it dims, flickers, glitches or resets.")
    print("  Each stage is printed BEFORE it is applied, so the last line you")
    print("  see in the console is the stage that killed it.\n")

    for level in RAMP_LEVELS:
        pattern = [(level, level, level)] * NUM_PIXELS
        ma = estimate_ma(pattern)
        verdict = "OK" if ma <= USB_BUDGET_MA else "OVER USB BUDGET"
        print("    level {:>3}/255  ~{:>6.0f} mA  [{}]".format(level, ma, verdict))
        time.sleep(0.3)
        write(pin_out, pattern)
        time.sleep(1.0)

    blank(pin_out)
    print("\n  Reached full brightness without a reset -> power delivery is fine.")


# ----------------------------------------------------------------- driver ----


def main():
    print("\n" + "=" * 62)
    print("RGB keyboard stand - LED diagnostic")
    print("{} pixels, {} bytes each, {} order".format(
        NUM_PIXELS, BYTES_PER_PIXEL, COLOR_ORDER))
    print("=" * 62)

    report_environment()

    if neopixel_write is None:
        hr("STOPPED")
        print("  This firmware has no `neopixel_write` module, so it cannot drive")
        print("  WS2812-style LEDs at all. That would be a firmware build problem.")
        return

    pin_name, power_names = find_pins()
    if pin_name is None:
        hr("STOPPED")
        print("  No data pin to test. Set DATA_PIN_NAME and re-run.")
        return

    held = enable_power(power_names)

    pin_out = digitalio.DigitalInOut(getattr(board, pin_name))
    pin_out.direction = digitalio.Direction.OUTPUT
    try:
        blank(pin_out)
        walk(pin_out)
        colours(pin_out)
        ramp(pin_out)
    finally:
        try:
            blank(pin_out)
        except Exception:  # noqa: BLE001
            pass
        pin_out.deinit()
        for gate in held:
            gate.deinit()

    hr("DONE")
    print("  Diagnostic finished cleanly and released the pin.")
    print()
    print("  Now watch the strip for 15 seconds. Because code.py exited without")
    print("  an exception you should see ONE faint GREEN blink every ~5 seconds")
    print("  instead of the two red ones.")
    print()
    print("  If red-2 became green-1, that proves the burst you were chasing was")
    print("  CircuitPython's exception indicator - the LEDs and wiring are fine,")
    print("  and the bug is an exception in your own code.py.")


try:
    main()
except Exception as err:  # noqa: BLE001 - the whole point is to surface this
    hr("DIAGNOSTIC ITSELF RAISED")
    try:
        import traceback
        traceback.print_exception(err)
    except Exception:  # noqa: BLE001 - older/newer traceback signatures
        print("  {}: {}".format(type(err).__name__, err))
    print("\n  Note the exception type above - see section 3 of README.md.")
