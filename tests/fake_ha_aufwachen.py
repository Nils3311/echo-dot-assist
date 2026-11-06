#!/usr/bin/env python3
"""The settings of the waking up, all off by default (main.c): reply_end_wait (a follow-up only after the reply's real end,
by its bytes, as MixerDrain returns at once; a barge-in still cuts it), stop_min_score (a weak "stop" ignored, none of it
while off) and wake_clips (each wake word's audio in state/wakeclips)."""
import asyncio, glob, os, signal, wave
from aioesphomeapi import VoiceAssistantEventType as Ev
from esphome_common import check, until, sync, home_assistant, run

PORTS = (16981, 16982, 16983, 16984, 16985)


async def main(e):
    ha = await home_assistant(e); cli, va = ha.cli, ha.va
    url = f"http://127.0.0.1:{e.HTTP_PORT}"
    for n in ("reply_end_wait", "stop_min_score", "wake_clips"): check(e.pv(n) == 0, f"{n}: off by default")
    clips = lambda: sorted(glob.glob(os.path.join(e.state, "wakeclips", "*.wav")))

    async def woke():
        va.started.clear(); e.wake(); await asyncio.wait_for(va.started.wait(), 5)

    async def ask(reply):                           # a run that answers with a question: the Echo listens again after it
        await woke(); va.started.clear()
        cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_STT_END, {"text": "which light"})
        cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_INTENT_END, {"conversation_id": "x", "continue_conversation": "1"})
        cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_TTS_END, {"url": url + reply})
        cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_RUN_END, None)
        return asyncio.get_running_loop().time()

    async def done():
        cli.send_voice_assistant_event(Ev.VOICE_ASSISTANT_ERROR, {"code": "x", "message": "end of test pipeline"})
        await sync(cli); await asyncio.sleep(0.3)

    # off: the follow-up as soon as the player took the data, the 3 s reply's end not waited for
    t0 = await ask("/long.wav?s=3"); await asyncio.wait_for(va.started.wait(), 5)
    off = asyncio.get_running_loop().time() - t0
    check(off < 1.5 and "for its real end" not in e.log(), f"off: the follow-up after {off:.2f} s, nothing waited for")
    await done(); check(clips() == [], "off: no wake word's audio kept")

    # on: it starts after the bytes' time and the tail, "speaking" until then
    e.page.set(reply_end_wait="on"); await sync(cli)
    t0 = await ask("/long.wav?s=3"); await asyncio.wait_for(va.started.wait(), 8)
    on = asyncio.get_running_loop().time() - t0
    check(3.0 <= on < 4.5 and "for its real end" in e.log(), f"on: the follow-up after the 3 s reply's real end: {on:.2f} s")
    await done()

    # on, and "Alexa" while it talks: at once, not after the 3 s
    before = os.path.getsize(e.play)
    await ask("/long.wav?s=3"); await until(lambda: os.path.getsize(e.play) > before)
    await asyncio.sleep(0.2); t0 = asyncio.get_running_loop().time(); await woke()
    cut = asyncio.get_running_loop().time() - t0
    check(cut < 1.0, f"on: a wake word still cuts the reply: new run after {cut:.2f} s")
    await done(); e.page.set(reply_end_wait="off"); await sync(cli)

    # stop_min_score: HASSMIC_TEST_STOP_SCORE plays a "stop" of 0.41, the one that ended a request live was 0.4008
    e.page.set(stop_ends_listening="on"); await sync(cli)
    await woke(); n = len(va.stopped); e.proc.send_signal(signal.SIGHUP); await until(lambda: len(va.stopped) > n, 2)
    check(len(va.stopped) > n and "ignored" not in e.log(), "stop_min_score off: the weak stop ends listening")
    await done()
    e.page.set(stop_min_score=45); await sync(cli)
    await woke(); n = len(va.stopped); e.proc.send_signal(signal.SIGHUP); await asyncio.sleep(0.6)
    check(len(va.stopped) == n and "wake: STOP at 0.410, under 45 %, ignored" in e.log(), "stop_min_score 45: the same stop is ignored, it goes on listening")
    await done()
    e.page.set(stop_min_score=40); await sync(cli)
    await woke(); n = len(va.stopped); e.proc.send_signal(signal.SIGHUP); await until(lambda: len(va.stopped) > n, 2)
    check(len(va.stopped) > n, "stop_min_score 40: a stop above it ends listening")
    await done(); e.page.set(stop_min_score=0, stop_ends_listening="off"); await sync(cli)

    # wake_clips: the file after the word's end, a proper WAV, readable by its owner only
    e.page.set(wake_clips="on"); await sync(cli)
    await woke(); await until(lambda: clips(), 3)
    await done()
    check(len(clips()) == 1, f"wake_clips on: one wake word, one file: {clips()}")
    if clips():
        with wave.open(clips()[0]) as w:
            check((w.getnchannels(), w.getframerate(), w.getsampwidth()) == (1, 16000, 2) and 0.3 < w.getnframes() / 16000 <= 4,
                  f"16 kHz mono, {w.getnframes() / 16000:.2f} s")
        check(os.stat(clips()[0]).st_mode & 0o077 == 0, "the file is its owner's only")
        check(os.path.basename(clips()[0]) in e.log(), "the log names it")
    e.page.set(wake_clips="off"); await sync(cli)
    n = len(clips()); await woke(); await asyncio.sleep(1); await done()
    check(len(clips()) == n, "wake_clips off again: nothing more, what is there stays")
    await cli.disconnect()


run(main, PORTS, {"HASSMIC_TEST_STOP_SCORE": "0.41", "HASSMIC_PLAY_TAKEN_AT_ONCE": "1"}, log=True)
