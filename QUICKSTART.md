# Quickstart

Follow these in order. Each step says what you should see when it worked.

Your board currently has **no software on it**. That is why the LEDs only flicker and why
files vanish from the drive. Steps 1–2 fix that; steps 3–5 turn the lights on.

---

## Step 1 — Download three files

Go to **github.com/qwertledev/astradebug**

Download these, using the download button (⤓) on each file's page:

- `code.py`
- `find_pin.py`
- `diagnostic.py` *(optional, only for troubleshooting later)*

> **Careful:** some browsers rename `.py` files to `.txt`. After downloading, check the names
> are still exactly `code.py` and `find_pin.py`. Rename them back if not — the board ignores
> anything not ending in `.py`.

---

## Step 2 — Put CircuitPython on the board

Right now your board shows a drive called **`RPI-RP2`**. That is the chip's built-in
emergency bootloader. It only accepts firmware files, which is why your `code.py` kept
disappearing.

1. Go to **https://circuitpython.org/board/raspberry_pi_pico/**
2. Click the big download button for the latest version. You get a file ending in **`.uf2`**.
3. Plug in the stand. The **`RPI-RP2`** drive appears.
4. **Drag the `.uf2` file onto the `RPI-RP2` drive.**
5. Wait a few seconds. The board restarts by itself.

**✅ Worked if:** `RPI-RP2` disappears and a new drive called **`CIRCUITPY`** appears instead.

**❌ If `RPI-RP2` is still there:** the file didn't take. Try dragging the `.uf2` again.

From now on, files you copy to `CIRCUITPY` will stay there.

---

## Step 3 — Find out which pin the LEDs are on

The software needs to know which pin on the chip your LED data wire is soldered to. This step
finds it for you. **You do not need any special tools — just watch the lights.**

1. Copy **`find_pin.py`** onto the `CIRCUITPY` drive.
2. **Rename it to `code.py`** (the board only ever runs a file with that exact name).
3. Watch the LED strip.

It tries each pin one at a time. Most do nothing — the strip stays dark. That's normal, and
a full pass takes about two minutes.

**When the strip lights up GREEN, keep watching.** It then blinks its own pin number:

| What you see | What it means |
| --- | --- |
| Solid **green** for a second | Found it — the number follows |
| **Long blue** flashes | Count these = the *tens* digit |
| **Short white** flashes | Count these = the *ones* digit |

**Examples:**

- green → 1 long blue → 6 short white = **GP16**
- green → 3 short white = **GP3**
- green → nothing at all = **GP0**

It repeats forever, so if you miss it, just wait for the next pass and count again.

**Write down that number.**

---

## Step 4 — Tell the lighting which pin to use

1. Open **`code.py`** (the real one from Step 1) in any text editor — Notepad is fine.
2. Near the top, find this line:

   ```python
   DATA_PIN_NAME = None   # None = auto-detect, or force e.g. "GP0" / "NEOPIXEL"
   ```

3. Change it to the pin you counted, **in quotes**:

   ```python
   DATA_PIN_NAME = "GP16"
   ```

4. Save the file.

---

## Step 5 — Turn the lights on

Copy your edited **`code.py`** onto the `CIRCUITPY` drive, replacing the `find_pin.py` copy
you renamed in Step 3.

**✅ Worked if:** the strip lights up within about a second and starts a slow rainbow. After
20 seconds it changes to a breathing fade, then a chasing comet, then loops.

**That's it — you're done.**

---

## Adjusting it

Edit `code.py` **directly on the `CIRCUITPY` drive** — it restarts and applies your change
the moment you save. No copying back and forth.

| You want | Change this |
| --- | --- |
| Brighter or dimmer | `BRIGHTNESS = 0.5` → anything from `0.0` to `1.0` |
| Red and green look swapped | `COLOR_ORDER = "GRB"` → `"RGB"` |
| Only one effect | `EFFECTS = ("rainbow",)` — keep the comma |
| Effects to change faster | `EFFECT_SECONDS = 20` → a smaller number |
| Never change effect | `EFFECT_SECONDS = None` |

Anything up to `BRIGHTNESS = 1.0` is safe on USB — see the power section in `README.md`.

---

## If something goes wrong

| Problem | What to do |
| --- | --- |
| Files still vanish from the drive | You're still on `RPI-RP2`. Step 2 didn't finish — drag the `.uf2` again. |
| Step 3 never lights the strip on any pin | Stop and say so. That's the first real sign of a wiring fault, and it points at the data line or the DIN/DOUT direction. |
| Strip lights but colours look wrong | `COLOR_ORDER = "RGB"` in `code.py`. |
| Nothing happens after Step 5 | Check the file on the drive is named exactly `code.py`, not `code.py.txt`. |
| Two faint red flashes, repeating | Now that CircuitPython is installed, this means an error in `code.py`. See §3 of `README.md` for reading the message. |
