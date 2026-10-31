#!/usr/bin/env python3
"""Wake word arbitration (tests/arbecho.py), the takeover (main.c trigger, setting arbitration_takeover): an Echo that
only listens (or thinks) after a wake word of its own gives way to a new wake word another Echo heard better, once its
run is 2 s old; a follow-up of a conversation and a ringing timer keep it; a wake word it did not hear leaves it alone.
"<wake word>, stop" (SIGHUP here) is stop_ends_listening's (fake_ha_stop_word.py), not the takeover's: checked here only
alongside it."""
import asyncio, os, time
from aioesphomeapi import VoiceAssistantEventType as Ev, VoiceAssistantTimerEventType as Tm
from arbecho import Echo, HA, check, until, start, run

key = os.urandom(32)
a, b = Echo("Echo Kitchen", 16961, 500, net=(2, key)), Echo("Echo Living Room", 16962, 900, net=(2, key))


async def main():
    ha = HA([a, b])
    await start((a, b), ha)
    check(await until(lambda: a.st("arbitration_peers") == 1 and b.st("arbitration_peers") == 1, 10), "both in one network")

    # Takeover (main.c trigger, arbitration_takeover): a run the Echo's own wake word opened has no priority once it
    # has listened for 2 s, and ends quietly (start=false, no new run) when another Echo takes a wake word it heard too
    async def listening(e, secs=2.8):               # a wrong wake-up: the run listens on
        n = len(e.starts); e.wake(); await until(lambda: len(e.starts) == n + 1, 3); await asyncio.sleep(secs)
    def took(e): return e.text().count("takeover: ")
    # (1) both hear the new wake word, the other one better
    await listening(a); na, nb, sa, ta = len(a.starts), len(b.starts), len(a.stops), took(a)
    a.wake(); b.wake(); await until(lambda: len(b.starts) == nb + 1 and len(a.stops) > sa, 3); await asyncio.sleep(0.5)
    check(len(b.starts) == nb + 1 and len(a.starts) == na and [x for _, x in a.stops[sa:]] == [True]
          and "takeover: another Echo heard the wake word better" in a.text() and took(a) == ta + 1,
          "takeover: both heard it, the better one answers, the listening one ends its run quietly (start=false)")
    b.end_pipeline(); await asyncio.sleep(0.5)
    # (2) only the other one hears it: its "answers" leaves this run alone (an "Alexa" upstairs must not end a real
    # command downstairs)
    await listening(a); na, nb, sa, ta = len(a.starts), len(b.starts), len(a.stops), took(a)
    b.wake(); await until(lambda: len(b.starts) == nb + 1, 3); await asyncio.sleep(0.5)
    check(len(b.starts) == nb + 1 and len(a.stops) == sa and took(a) == ta,
          "takeover: only the other Echo heard it; this one listens on")
    a.end_pipeline(); b.end_pipeline(); await asyncio.sleep(0.5)
    # ...and a run younger than 2 s keeps the wake word (Home Assistant would refuse a new run: one start per wake
    # word in 2 s)
    await listening(a, 0.8); na, nb, sa, ta = len(a.starts), len(b.starts), len(a.stops), took(a)
    a.wake(); b.wake(); await asyncio.sleep(1.5)
    check(len(a.starts) == na and len(b.starts) == nb and len(a.stops) == sa and took(a) == ta,
          "takeover: a run younger than 2 s keeps the wake word and listens on")
    a.end_pipeline(); await asyncio.sleep(0.5)
    # the listening Echo hears the new wake word alone: it listens anew from it
    await listening(a); na, sa = len(a.starts), len(a.stops)
    a.wake(); await until(lambda: len(a.starts) == na + 1, 3); await asyncio.sleep(0.3)
    check(len(a.starts) == na + 1 and [x for _, x in a.stops[sa:]] == [True] and "wake word: pipeline cancelled" in a.text(),
          "takeover: its own wake word again after 2 s: the run is cancelled and a new one listens")
    a.end_pipeline(); await asyncio.sleep(0.5)
    # (1b) THINKING counts as listening: a wake that heard nothing thinks after a second or two, just when its talker
    # calls from the next room (2026-10-19 21:06:09)
    n = len(a.starts); a.wake(); await until(lambda: len(a.starts) == n + 1, 3)
    a.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_STT_VAD_END, None); await asyncio.sleep(2.3)
    na, nb, sa, ta = len(a.starts), len(b.starts), len(a.stops), took(a)
    a.wake(); b.wake(); await until(lambda: len(b.starts) == nb + 1 and len(a.stops) > sa, 3); await asyncio.sleep(0.5)
    check(len(b.starts) == nb + 1 and len(a.starts) == na and [x for _, x in a.stops[sa:]] == [True] and took(a) == ta + 1,
          "takeover: a run that thinks after a wake word of its own gives way too")
    b.end_pipeline(); await asyncio.sleep(0.5)
    # (3) a follow-up of a conversation (continue_conversation, started by the Echo itself) keeps its priority
    n = len(a.starts); a.wake(); await until(lambda: len(a.starts) == n + 1, 3)
    a.cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_INTENT_END, {"conversation_id": "x", "continue_conversation": "1"})
    a.end_pipeline(); await until(lambda: len(a.starts) == n + 2, 3); await asyncio.sleep(2.8)
    na, nb, sa = len(a.starts), len(b.starts), len(a.stops)
    a.wake(); b.wake(); await asyncio.sleep(1.5)
    check(len(a.starts) == na and len(b.starts) == nb and len(a.stops) == sa and "with priority: busy or ringing" in b.text(),
          "a follow-up of a conversation keeps the next wake word against a better score")
    a.end_pipeline(); await asyncio.sleep(0.5)
    # (4) a ringing timer too
    a.cli.send_voice_assistant_timer_event(Tm.VOICE_ASSISTANT_TIMER_FINISHED, "t1", "tea", 60, 0, False); await asyncio.sleep(0.5)
    na, nb = len(a.starts), len(b.starts)
    a.wake(); b.wake(); await until(lambda: len(a.starts) == na + 1, 3); await asyncio.sleep(0.5)
    check(len(a.starts) == na + 1 and len(b.starts) == nb, "a ringing timer keeps the next wake word against a better score")
    sa = len(a.stops); a.stop(); await until(lambda: len(a.stops) > sa, 2)
    check("alarm: off (stop)" in a.text() and True in [x for _, x in a.stops[sa:]], "\"<wake word>, stop\": the ring and the run it opened end")
    await asyncio.sleep(0.5)
    # (5) off: as before, the listening Echo keeps the wake word
    for e in (a, b): e.page.set(arbitration_takeover="off")
    await listening(a); na, nb, sa, ta = len(a.starts), len(b.starts), len(a.stops), took(a)
    a.wake(); b.wake(); await asyncio.sleep(1.5)
    check(len(a.starts) == na and len(b.starts) == nb and len(a.stops) == sa and took(a) == ta,
          "takeover off: the listening Echo keeps the wake word")
    a.end_pipeline(); await asyncio.sleep(0.5)
    for e in (a, b): e.page.set(arbitration_takeover="on")

    # "<wake word>, stop" is not the takeover's: with stop_ends_listening off (its default) it goes to Home Assistant
    nb, sb = len(b.starts), len(b.stops); b.wake(); await until(lambda: len(b.starts) == nb + 1, 3); b.stop(); await asyncio.sleep(0.5)
    check(len(b.stops) == sb, "takeover on, stop_ends_listening off: \"<wake word>, stop\" out of silence is a command for Home Assistant")
    b.end_pipeline(); await asyncio.sleep(0.5)
    # both on: a run that only listens, then "<wake word>, stop": the wake word takes over, its "stop" ends that run,
    # and nothing listens anew
    a.page.set(stop_ends_listening="on")
    await listening(a); na, sa = len(a.starts), len(a.stops)
    a.wake(); await asyncio.sleep(0.05); a.stop(); await asyncio.sleep(1.5)
    check(len(a.starts) - na == len(a.stops) - sa - 1 and a.stops[-1][1] is True,
          f"takeover and stop_ends_listening: listening, then \"<wake word>, stop\": no run left ({len(a.starts) - na} started)")
    a.page.set(stop_ends_listening="off"); await asyncio.sleep(0.5)

run(main, (a, b))
