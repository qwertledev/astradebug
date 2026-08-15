#!/usr/bin/env python3
"""Estimate whether a WS2812-style LED run can be powered over USB.

    python3 tools/power_budget.py 16
    python3 tools/power_budget.py 60 --rgbw --supply 2000

Numbers are the usual datasheet figures: ~20 mA per colour channel per LED at
full on, plus ~1 mA quiescent. Real strips vary; treat this as a sanity check,
not a specification.
"""

import argparse

MA_PER_CHANNEL = 20.0
MA_QUIESCENT = 1.0
VOLTS = 5.0

SUPPLIES = {
    "USB 2.0 port": 500.0,
    "USB 3.0 port": 900.0,
    "USB-C (5 V/1.5 A)": 1500.0,
    "USB-C (5 V/3 A)": 3000.0,
}


def draw_ma(count, channels, duty):
    """Worst-case draw for `count` LEDs at `duty` fraction of full brightness."""
    return count * (MA_QUIESCENT + channels * MA_PER_CHANNEL * duty)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("count", type=int, help="number of LEDs in the run")
    ap.add_argument("--rgbw", action="store_true",
                    help="SK6812 RGBW (4 channels) instead of 3")
    ap.add_argument("--supply", type=float, default=None,
                    help="available current in mA (default: compare against all)")
    args = ap.parse_args()

    if args.count <= 0:
        ap.error("count must be positive")

    channels = 4 if args.rgbw else 3
    kind = "RGBW" if args.rgbw else "RGB"

    print("{} x {} LEDs at {:.0f} V".format(args.count, kind, VOLTS))
    print("=" * 52)

    print("\nWorst-case draw by brightness (all LEDs, all channels):")
    for pct in (5, 10, 25, 50, 100):
        ma = draw_ma(args.count, channels, pct / 100)
        print("  {:>3}% -> {:>7.0f} mA  ({:>5.2f} A, {:>5.1f} W)".format(
            pct, ma, ma / 1000, ma / 1000 * VOLTS))

    full = draw_ma(args.count, channels, 1.0)

    if args.supply is not None:
        budget = {"your supply": args.supply}
    else:
        budget = SUPPLIES

    print("\nHeadroom at full white:")
    for name, limit in budget.items():
        if full <= limit:
            note = "OK"
        else:
            note = "OVER by {:.0f} mA".format(full - limit)
        print("  {:<20} {:>6.0f} mA  {}".format(name, limit, note))

    print("\nMax brightness that fits:")
    for name, limit in budget.items():
        usable = limit - args.count * MA_QUIESCENT
        if usable <= 0:
            pct = 0.0
        else:
            pct = min(100.0, usable / (args.count * channels * MA_PER_CHANNEL) * 100)
        print("  {:<20} {:>5.0f}%   (neopixel brightness ~{:.2f})".format(
            name, pct, pct / 100))

    print("\nNotes:")
    print("  * Leave ~20% headroom - the microcontroller and USB hub need some too.")
    print("  * Over budget means an external 5 V supply, with grounds tied together.")
    print("  * A host port cutting out under load looks exactly like a firmware bug.")


if __name__ == "__main__":
    main()
