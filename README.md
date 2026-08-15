# RGB keyboard stand — lighting + LED debug

Symptom reported: **on USB plug-in the LEDs give one faint, brief red burst, then go dark.**
The board is recognised by the PC and files can be copied to it.

That combination rules out the hardware. A board that enumerates and mounts `CIRCUITPY` is
not browning out and is not shorting VBUS, and LEDs that visibly light have working solder
joints, a working data line and a working ground return. What you were seeing is
CircuitPython's built-in status-LED error code — it means `code.py` raised an exception (or
there was no `code.py` to run). The firmware was lighting the strip *on purpose*, to tell
you so.

## Make it glow

**Nothing needs to be added to the hardware.** Copy `code.py` to the root of the `CIRCUITPY`
drive and the stand lights up — it starts as soon as the file finishes copying.

Open `code.py` and set one value:

```python
NUM_PIXELS = 16        # <-- your real LED count
```

That is normally the only edit. It cycles rainbow → breathe → comet, and needs **no
libraries** — it drives the LEDs through the built-in `neopixel_write` module rather than
the `neopixel` library, so there is no bundle to download and no version mismatch to get
wrong (a mismatched bundle is the most common cause of the red-blink you saw).

Other knobs at the top of the file:

| Setting | Purpose |
| --- | --- |
| `BRIGHTNESS` | `0.0`–`1.0`, default `0.25`. See the power note below. |
| `COLOR_ORDER` | `"GRB"` for WS2812B. Switch to `"RGB"` if red and green come out swapped. |
| `EFFECTS` | Which effects cycle, and in what order. Use a single entry to pin one. |
| `EFFECT_SECONDS` | Seconds per effect; set to `None` to never switch. |
| `DATA_PIN_NAME` | Only needed if the pin is not auto-detected — the error message tells you. |

If you would rather use the `neopixel` library (for its `auto_write`/slicing API), install it
from the [CircuitPython bundle](https://circuitpython.org/libraries) into `CIRCUITPY/lib/` —
and match the bundle to the firmware major version. This build reports `9.0.0-alpha.1`, so
use the **9.x** bundle; an 8.x `.mpy` will fail to import and put you right back at the two
red blinks.

### Power

`BRIGHTNESS = 0.25` is chosen to stay comfortably inside a USB 2.0 port's 500 mA, and none of
the effects light every LED at full white at once. Before turning it up:

```
python3 tools/power_budget.py 16
```

16 WS2812Bs at full white is ~976 mA — already double what a USB 2.0 port supplies. If the
strip browns out or the board resets when you raise `BRIGHTNESS`, that is the port's current
limit rather than a bug: feed the strip from its own 5 V supply with the grounds tied
together.

Optional, only if you get flicker or the first LED misbehaves later on — a 300–500 Ω resistor
in series with the data line and a ~1000 µF capacitor across 5 V/GND near the strip. Yours is
evidently working without them, so don't add them pre-emptively.

---

## Reference: what the red burst meant

Kept because the blink codes are worth knowing — they tell you what went wrong without a
serial console.

## 1. Why the symptom points at software, not solder

The firmware being run here is [Snipeye/circuitpython](https://github.com/Snipeye/circuitpython),
which is upstream CircuitPython `9.0.0-alpha.1` (Oct 2023) plus exactly one custom commit
(`6bba718`, an RP2040 `pulseio.PulseIn` fix for IR decoding). So all the supervisor
behaviour below is stock CircuitPython, and it is worth reading literally.

When `code.py` stops running, the supervisor blinks the status LED in a colour that encodes
*why* it stopped. From `supervisor/shared/rgb_led_colors.h`:

```c
#define INTENSITY (0x30)              // 48/255 ≈ 19% — this is why it looks "faint"
#define RED     COLOR(INTENSITY, 0, 0)

#define ALL_DONE     GREEN
#define EXCEPTION    RED
#define SAFE_MODE    YELLOW
#define REPL_RUNNING WHITE

#define ALL_DONE_BLINKS  1
#define EXCEPTION_BLINKS 2
#define SAFE_MODE_BLINKS 3

#define OFF_ON_RATIO 3
#define BLINK_TIME_MS 100u
#define LED_SLEEP_TIME_MS 5000u
```

Three details line up with what you're seeing:

| What you saw | What the firmware does |
| --- | --- |
| **faint** | `INTENSITY` is `0x30` — 19% of full scale, then scaled again by `rgb_status_brightness` (50–63/255 on most boards). Dim is by design. |
| **red** | `EXCEPTION = RED`. Red specifically means *an exception escaped `code.py`*. |
| **short burst, then off** | `EXCEPTION_BLINKS = 2` at `BLINK_TIME_MS = 100` with `OFF_ON_RATIO = 3` → two 100 ms pulses inside 800 ms, then dark. |

And the whole strip flashing at once (rather than a single indicator LED) is expected if the
board definition sets `MICROPY_HW_NEOPIXEL_COUNT` — `supervisor/shared/status_leds.c` writes
the same colour to every pixel it knows about:

```c
for (size_t i = 0; i < MICROPY_HW_NEOPIXEL_COUNT; i++) { ... }
common_hal_neopixel_write(&status_neopixel, status_neopixel_color, 3 * MICROPY_HW_NEOPIXEL_COUNT);
```

## 2. The test that confirms it in 10 seconds

This is the useful part. The blink pattern **repeats**. In `main.c`:

```c
} else if (tick_diff > total_time) {
    pattern_start = supervisor_ticks_ms32();   // restart the pattern
}
```

with `total_time = blink_time + LED_SLEEP_TIME_MS` = 800 ms + 5000 ms.

> **Plug it in and watch the strip for a full 15 seconds without touching anything.**
>
> If the faint red double-blink comes back roughly **every 6 seconds**, the diagnosis is
> confirmed: your hardware is fine and `code.py` is throwing.

Count the blinks and note the colour — that alone tells you the failure class:

| Pattern (repeats ≈ every 5–6 s) | Meaning | Where to look |
| --- | --- | --- |
| **2 × faint red** | Exception escaped `code.py` | Read the traceback (§3) |
| 3 × faint yellow | **Safe mode** — `code.py` never ran | `supervisor.runtime.safe_mode_reason`; commonly `BROWNOUT` |
| 1 × faint green | `code.py` ran to completion and exited | Missing `while True:` loop |
| steady faint white | Sitting in the REPL | No `code.py`, or you're connected to the console |
| nothing at all | Not enumerating / no power / genuinely dark | §5 hardware checks |

A brownout (real power problem) shows up as **3 yellow**, not 2 red. That is what makes this
worth distinguishing before you reach for the soldering iron.

## 3. Get the traceback — this is the actual fix

Red-2 means there is a Python traceback waiting for you on the USB serial console. It names
the file, the line and the exception. Everything else here is guesswork until you read it.

- **Linux:** `screen /dev/ttyACM0 115200` (or `tio /dev/ttyACM0`)
- **macOS:** `screen /dev/tty.usbmodem* 115200`
- **Windows:** PuTTY / Tera Term on the board's COM port, 115200 8N1
- **Any OS, easiest:** the [Mu editor](https://codewith.mu/) — click *Serial*

Press <kbd>Ctrl</kbd>+<kbd>D</kbd> in the console to soft-reboot and watch the run from the
top. The traceback prints immediately before the red blinks start.

Common causes for this specific build, roughly in order:

1. **`ImportError: no module named 'neopixel'`** — the `neopixel` library is not in
   `CIRCUITPY/lib/`. It is *not* built into the firmware; it ships in the
   [Adafruit CircuitPython bundle](https://circuitpython.org/libraries). Match the bundle to
   the firmware major version (this build reports `9.0.0-alpha.1`, so use the 9.x bundle —
   an 8.x bundle `.mpy` will fail to import).
2. **`AttributeError: 'module' object has no attribute 'NEOPIXEL'`** — `board.NEOPIXEL`
   doesn't exist on this board definition; the data pin has another name.
3. **`ValueError: <pin> in use`** — something else already claimed the data pin. On RP2040
   this includes a `pulseio.PulseIn` left running from a previous soft-reload.
4. **`RuntimeError: All state machines in use`** — see §4, this one is specific to your build.
5. **`MemoryError`** — allocating a large pixel buffer plus a bundle import on an RP2040.

## 4. One trap specific to this fork (IR + NeoPixel on RP2040)

The single custom commit in this fork is a `pulseio.PulseIn` fix, so this stand very likely
decodes IR alongside driving the LEDs. On RP2040 **both** of those are PIO peripherals, and
they compete:

- `PulseIn` claims a PIO state machine *for as long as the object is alive*
  (`ports/raspberrypi/common-hal/pulseio/PulseIn.c`).
- `neopixel_write` builds a **new** state machine on *every single write*
  (`ports/raspberrypi/common-hal/neopixel_write/__init__.c`).

If the allocation fails, look closely at what that code does:

```c
if (!ok) {
    // Do nothing. Maybe bitbang?
    return;
}
```

It **silently returns** — no exception, no error, the LEDs just never update. So if you ever
see the LEDs freeze on one colour (rather than the red blink), with IR still working, that's
this path, not a wiring fault. Constructing the `PulseIn` *after* the pixels, or keeping one
long-lived `neopixel.NeoPixel` object rather than recreating it, avoids the squeeze.

## 5. If the blinks *don't* repeat every ~6 seconds

Then it isn't the exception indicator, and hardware is back on the table. In priority order:

1. **Does the board enumerate?** Does a `CIRCUITPY` drive appear, and a serial port? If the
   flash happens and then the device vanishes from USB entirely, you have a **short pulling
   down VBUS** and the host port's over-current protection is cutting power. Unplug
   immediately and check for solder bridges between 5 V and GND, and for a backwards
   capacitor. Do not keep re-plugging it.
2. **Power budget.** WS2812B LEDs draw up to ~60 mA each at full white. USB 2.0 gives you
   500 mA. Run `python3 tools/power_budget.py <led_count>` for the numbers. If you're over
   budget the strip must have its own 5 V supply, with **grounds tied together**.
3. **Common ground.** If the strip is externally powered, its GND *must* be bonded to the
   microcontroller GND or the data line has no reference and behaves randomly.
4. **Data direction.** WS2812 strips are directional. The MCU must drive the **DIN** end
   (arrows on the PCB point *away* from it). Wired to DOUT, the strip only ever shows
   power-on garbage.
5. **LED power gate.** Some board definitions gate LED power behind a pin
   (`NEOPIXEL_POWER` / `CIRCUITPY_STATUS_LED_POWER`) that your code must drive. The
   diagnostic detects and enables this automatically, as does `code.py`.

## 6. Using the diagnostic

Only needed if the lights misbehave. Copy `diagnostic.py` **over** `code.py` on the
`CIRCUITPY` drive (keep your own `code.py` somewhere first), then open the serial console.
Restore `code.py` when you're done.

It deliberately uses the **built-in `neopixel_write` module**, not the `neopixel` library, so
it runs even when a missing/mismatched bundle is the root cause. It:

- prints board ID, firmware version, reset reason and safe-mode reason;
- auto-detects the data pin and any LED power-gate pin;
- lights **one LED at a time at ~9% brightness**, so it draws a few mA and cannot brown out
  a marginal supply — this separates a *data* problem from a *power* problem;
- only then ramps the whole strip up in stages, printing an estimated current draw at each
  step, so you can watch for the exact point it collapses;
- catches and prints every exception rather than dying silently.

Set `NUM_PIXELS` at the top to your real LED count before running.

Read the output top to bottom:

- **Nothing lights, no errors** → data never reaches the strip. Check DIN vs DOUT, the data
  pin choice, and common ground.
- **The single-LED walk works but the full-brightness stage dies or resets** → power. You are
  over USB's budget; add an external 5 V supply.
- **An exception is printed** → that's the bug, and its traceback is the answer.

---

### Files

| File | Runs on | Purpose |
| --- | --- | --- |
| `code.py` | the board | **The lighting.** Copy to `CIRCUITPY` and it glows. No libraries needed. |
| `diagnostic.py` | the board | Staged, low-current LED diagnostic. Only if something misbehaves. |
| `tools/power_budget.py` | your PC | Current-draw estimate vs USB budget |
