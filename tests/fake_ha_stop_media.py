#!/usr/bin/env python3
""""<wake word>, stop" while a player of the room plays (main.c stop_keeps_listening, setting stop_media_listens, on by
default), with stop_ends_listening on: the run goes on, so Home Assistant hears "stop the music" and pauses it.  With
nothing playing, or the setting off, the stop ends listening as before (fake_ha_stop_word.py)."""
import asyncio, os
from arbecho import Echo, HA, check, until, start, run

SONOS = "media_player.kitchen_sonos"
a = Echo("Echo Kitchen", 16991, 500)
a.env.update(HASSMIC_MEDIA_HOLD_MS="1500", HASSMIC_MEDIA_MISSING_MS="1000")


async def main():
    ha = HA([a]); ha.media.update({SONOS: "idle"})
    await start((a,), ha)
    a.page.set(stop_ends_listening="on", arbitration_media_players=SONOS); await asyncio.sleep(0.8)
    check(a.page.state() is not None and next(x["value"] for x in a.page.state()["settings"] if x["name"] == "stop_media_listens") == 1,
          "stop_media_listens: on by default")

    async def stop_after_wake():
        n, s = len(a.starts), len(a.stops)
        a.wake(); check(await until(lambda: len(a.starts) == n + 1, 3), "  the wake word starts a run")
        await asyncio.sleep(0.3); a.stop(); await asyncio.sleep(0.8)
        return a.stops[s:]

    stops = await stop_after_wake()
    check(stops and stops[0][1] and "stop: listening ended" in a.text(), f"nothing plays: the stop ends listening ({stops})")
    a.end_pipeline(); await asyncio.sleep(0.5)

    ha.set_media(SONOS, "playing"); await asyncio.sleep(0.5)
    at = len(a.text()); stops = await stop_after_wake()
    check(stops == [] and "listening goes on" in a.text()[at:], f"the Sonos plays: listening goes on, Home Assistant hears the rest ({stops})")
    a.end_pipeline(); await asyncio.sleep(0.5)

    a.page.set(stop_media_listens="off"); await asyncio.sleep(0.5)
    stops = await stop_after_wake()
    check(stops and stops[0][1], f"setting off: the stop ends listening even with the Sonos playing ({stops})")
    a.end_pipeline(); await asyncio.sleep(0.3)


run(main, (a,))
