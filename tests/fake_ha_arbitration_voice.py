#!/usr/bin/env python3
"""Wake word arbitration (tests/arbecho.py), the voice energy in the claim (main.c claim), both settings off by default:
the kitchen's stand-in front end reads a voice of 60 dB in a loud room, score 1222, and loses to the living room's 1300.
arbitration_voice_weight 50: 1222 + 3000 against 1300 + 2900 (no reading: the median, 58 dB), the closer Echo answers.
arbitration_voice_min 65: the kitchen's voice is under it, no claim and no run, whatever the score says."""
import asyncio, os
from arbecho import Echo, HA, check, until, start, run

key = os.urandom(32)
a, b = Echo("Echo Kitchen", 16986, 500, net=(2, key)), Echo("Echo Living Room", 16987, 1300, net=(2, key))
a.env["HASSMIC_FAKE_AFE"] = "50:1000000:60000"      # 1000 * log10(1000001 / 60001) = 1222
for e in (a, b): e.env["HASSMIC_ARB_RIVALS"] = "0"  # every round waits for the other's claim


async def main():
    ha = HA([a, b])
    await start((a, b), ha)
    check(await until(lambda: a.st("arbitration_peers") == 1 and b.st("arbitration_peers") == 1, 10), "both in one network")
    await asyncio.sleep(1)

    async def round_():
        na, nb, at = len(a.starts), len(b.starts), len(a.text())
        a.wake(); b.wake(); await until(lambda: len(a.starts) > na or len(b.starts) > nb, 3); await asyncio.sleep(0.5)
        return len(a.starts) - na, len(b.starts) - nb, a.text()[at:]

    x, y, t = await round_()
    check((x, y) == (0, 1) and "voice 6" not in t, f"off: the score alone, the living room answers ({x} / {y})")
    b.end_pipeline(); await asyncio.sleep(0.5)

    a.page.set(arbitration_voice_weight="50"); b.page.set(arbitration_voice_weight="50"); await asyncio.sleep(0.5)
    x, y, t = await round_()
    check((x, y) == (1, 0) and "voice 60.0 dB at 50 %: score 1222 -> 4222" in t, f"weight 50: the kitchen's voice counts, it answers ({x} / {y})")
    a.end_pipeline(); await asyncio.sleep(0.5)
    a.page.set(arbitration_voice_weight="0"); b.page.set(arbitration_voice_weight="0"); await asyncio.sleep(0.5)

    a.page.set(arbitration_voice_min="65"); await asyncio.sleep(0.5)
    na, at = len(a.starts), len(a.text())
    a.wake(); await asyncio.sleep(1.5)
    t = a.text()[at:]
    check(len(a.starts) == na and "voice 60.0 dB, under 65: no talker, no claim" in t, "voice_min 65: alone in the round it still neither claims nor answers")
    a.page.set(arbitration_voice_min="0"); await asyncio.sleep(0.5)
    na, at = len(a.starts), len(a.text())
    a.wake(); await until(lambda: len(a.starts) > na, 3)
    check(len(a.starts) == na + 1, "voice_min 0: it answers again")
    a.end_pipeline(); await asyncio.sleep(0.3)


run(main, (a, b))
