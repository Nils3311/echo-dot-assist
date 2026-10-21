/* noisecap.c, the noise cap of wake word arbitration: it learns the quiet level only from rounds without media in the
 * room, caps nothing until it has 10 of them, caps at factor x quiet from there, factor 0 is off, the median keeps a
 * minority of loud rounds out of it, and the samples go through state/arbitration's lines and back unchanged. */
#include "noisecap.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static int fails;
static void check(int ok, const char *what) { printf("%s %s\n", ok ? "ok  " : "FAIL", what); if (!ok) fails++; }

int main(void)
{
    struct noisecap c; double counted, quiet; int changed;
    memset(&c, 0, sizeof c);

    /* nothing learned: no cap, whatever the factor */
    changed = noisecap_round(&c, 3, 200000, 0, &counted, &quiet);
    check(changed && counted == 200000 && quiet == 0, "first round: no quiet level yet, ambient as it is, learned");
    memset(&c, 0, sizeof c);

    /* media in the room: never learned */
    for (int i = 0; i < 20; i++) noisecap_round(&c, 3, 90000, 1, &counted, &quiet);
    check(c.n == 0 && noisecap_quiet(&c) == 0 && counted == 90000, "media here: 20 rounds, none learned, no cap");

    /* 9 rounds: still learning */
    for (int i = 0; i < 9; i++) noisecap_round(&c, 3, 17000 + 100 * i, 0, &counted, &quiet);
    noisecap_round(&c, 3, 200000, 1, &counted, &quiet);
    check(c.n == 9 && quiet == 0 && counted == 200000, "9 quiet rounds: no cap yet");
    changed = noisecap_round(&c, 3, 17900, 0, &counted, &quiet);        /* the 10th, capped against what came before */
    check(changed && quiet == 0 && c.n == 10, "the 10th round learns, but is not capped by itself");
    check(fabs(noisecap_quiet(&c) - 17450) < 1e-9, "10 learned: the median (17450)");

    /* the cap: at factor x quiet, not below */
    noisecap_round(&c, 3, 52000, 1, &counted, &quiet);
    check(counted == 52000 && fabs(quiet - 17450) < 1e-9, "under 3x quiet: counted as it is");
    noisecap_round(&c, 3, 103000, 1, &counted, &quiet);
    check(fabs(counted - 3 * 17450) < 1e-9, "a cooker hood, 103000: counted as 3x quiet (52350)");
    noisecap_round(&c, 2, 103000, 1, &counted, &quiet);
    check(fabs(counted - 2 * 17450) < 1e-9, "factor 2: 2x quiet");
    noisecap_round(&c, 0, 103000, 1, &counted, &quiet);
    check(counted == 103000, "factor 0: off");
    check(c.n == 10, "rounds with media: still none learned");

    /* loud rounds without media are learned too (the cooker hood has no media state), the median stays */
    for (int i = 0; i < 9; i++) noisecap_round(&c, 3, 150000, 0, &counted, &quiet);
    check(c.n == 19 && fabs(noisecap_quiet(&c) - 17900) < 1e-9, "9 loud rounds of 19 learned too: the median still the quiet room's");
    for (int i = 0; i < 64; i++) noisecap_round(&c, 3, 30000 + i, 0, &counted, &quiet);
    check(fabs(noisecap_quiet(&c) - 30031.5) < 1e-9 && c.n == 83, "only the last 64 count");

    /* state/arbitration: oldest first, back unchanged; other lines left alone */
    char text[NOISECAP_KEEP * 24]; struct noisecap d; size_t n = noisecap_format(&c, text, sizeof text);
    memset(&d, 0, sizeof d);
    int lines = 0;
    for (char *l = strtok(text, "\n"); l; l = strtok(NULL, "\n")) lines += noisecap_line(&d, l);
    check(n > 0 && lines == 64 && d.n == 64 && noisecap_quiet(&d) == noisecap_quiet(&c), "64 lines saved and loaded, the same quiet level");
    noisecap_round(&d, 3, 30064, 0, &counted, &quiet); noisecap_round(&c, 3, 30064, 0, &counted, &quiet);
    check(noisecap_quiet(&d) == noisecap_quiet(&c), "loaded: the oldest sample goes first, as before");
    check(!noisecap_line(&d, "delay 0011223344556677 120\n") && !noisecap_line(&d, "ambient x\n") && !noisecap_line(&d, "ambient -5\n")
          && d.n == 65, "other lines and bad values: not taken");
    char small[30]; n = noisecap_format(&c, small, sizeof small);
    check(n == strlen(small) && n > 0 && small[n - 1] == '\n', "a short buffer: whole lines only");

    printf("noisecap: %s\n", fails ? "FAILED" : "all passed");
    return fails ? 1 : 0;
}
