#!/usr/bin/env python3
"""Wake word arbitration (tests/arbecho.py), the noise cap (main.c claim, noisecap.c, setting arbitration_noise_cap):
the kitchen Echo learned a quiet level of 10000 (state/arbitration "ambient" lines) and its stand-in front end
(HASSMIC_FAKE_AFE) reports 6x that, a cooker hood beside it.  Capped at 3x its score is 1523 and beats the living
room's 1300; uncapped (0 = off) it is 1222 and the living room answers."""
import asyncio, os
from arbecho import Echo, HA, check, until, start, run

key = os.urandom(32)
a, b = Echo("Echo Kitchen", 16961, 500, net=(2, key)), Echo("Echo Living Room", 16962, 1300, net=(2, key))
a.env["HASSMIC_FAKE_AFE"] = "50:1000000:60000"      # 1000 * log10(1000001 / 60001) = 1222; / 30001 = 1523
for e in (a, b): e.env["HASSMIC_ARB_RIVALS"] = "0"  # every round waits for the other's claim
with open(os.path.join(a.state, "arbitration"), "a") as f: f.write("ambient 10000\n" * 12)


async def main():
    ha = HA([a, b])
    await start((a, b), ha)
    check(await until(lambda: a.st("arbitration_peers") == 1 and b.st("arbitration_peers") == 1, 10), "both in one network")
    await asyncio.sleep(1)

    na, nb = len(a.starts), len(b.starts)
    a.wake(); b.wake(); await until(lambda: len(a.starts) > na or len(b.starts) > nb, 3); await asyncio.sleep(0.5)
    check(len(a.starts) == na + 1 and len(b.starts) == nb
          and "noise cap: ambient 60000 counted as 30000 (quiet 10000, x 3)" in a.text(),
          f"cap 3: the kitchen's own noise counts 3x its quiet level, it answers ({len(a.starts) - na} / {len(b.starts) - nb})")
    a.end_pipeline(); await asyncio.sleep(0.5)

    a.page.set(arbitration_noise_cap="0"); await asyncio.sleep(0.5)
    na, nb, at = len(a.starts), len(b.starts), len(a.text())
    a.wake(); b.wake(); await until(lambda: len(a.starts) > na or len(b.starts) > nb, 3); await asyncio.sleep(0.5)
    t = a.text()[at:]
    check(len(a.starts) == na and len(b.starts) == nb + 1 and "noise cap:" not in t and "score 1222" in t,
          f"cap off: the kitchen claims 1222, the living room answers ({len(a.starts) - na} / {len(b.starts) - nb})")
    b.end_pipeline(); await asyncio.sleep(0.5)


run(main, (a, b))
