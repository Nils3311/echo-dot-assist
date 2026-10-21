/* The noise cap (noisecap.h).  The front end's score is voiceEnergy over ambientEnergy, a signal to noise: an Echo next
 * to its own loud noise loses even when the talker stands at it.  2026-10-21 15:44:26, the cooker hood on beside the
 * kitchen Echo and the talker in the kitchen: kitchen ambient 103 k (6x its quiet level), living room 44.5 k, and the
 * living room won by 2.3 dB.  ambientEnergy says how loud the Echo's room is, not where the talker stands (48 rounds
 * of a measuring run: it pointed at the right Echo in 34, voiceEnergy alone in 45).  So above factor x the Echo's own
 * quiet level it counts no more: min(ambient, 3 x quiet) left that run's 48 rounds as they were (45 right, the same
 * three wrong) and turned 15:44:26 (+0.6 dB); 2x already lost one of the run's rounds.  Quiet levels measured: kitchen
 * 17 336, living room 16 102 (medians of 11 days of rounds without media in the room); music hardly moved ambient
 * (0.5-1.6x), the cooker hood up to 4.7x in the kitchen and 2.7x through the wall.  Each Echo learns its own: the
 * median of its last 64 such rounds, robust against the cooking in a quarter of them. */
#include "noisecap.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int cmp_dbl(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); }

double noisecap_quiet(const struct noisecap *c)
{
    unsigned k = c->n < NOISECAP_KEEP ? c->n : NOISECAP_KEEP;
    double s[NOISECAP_KEEP];
    if (k < NOISECAP_LEARN) return 0;
    memcpy(s, c->v, k * sizeof s[0]);              /* the ring's order does not matter to a median */
    qsort(s, k, sizeof s[0], cmp_dbl);
    return k % 2 ? s[k / 2] : (s[k / 2 - 1] + s[k / 2]) / 2;
}

int noisecap_round(struct noisecap *c, int factor, double ambient, int media, double *counted, double *quiet)
{
    double q = noisecap_quiet(c);
    *quiet = q;
    *counted = factor > 0 && q > 0 && ambient > factor * q ? factor * q : ambient;
    /* Media in the room raise ambient by what plays: a level to cap, not the room's own */
    if (media || ambient <= 0) return 0;
    c->v[c->n++ % NOISECAP_KEEP] = ambient;
    return 1;
}

size_t noisecap_format(const struct noisecap *c, char *out, size_t cap)
{
    size_t n = 0;
    if (cap) out[0] = 0;
    for (unsigned i = c->n > NOISECAP_KEEP ? c->n - NOISECAP_KEEP : 0; i < c->n && n < cap; i++) {
        int w = snprintf(out + n, cap - n, "ambient %.0f\n", c->v[i % NOISECAP_KEEP]);
        if (w < 0 || (size_t)w >= cap - n) { out[n] = 0; break; }      /* whole lines only */
        n += (size_t)w;
    }
    return n;
}

int noisecap_line(struct noisecap *c, const char *line)
{
    double v;
    if (sscanf(line, "ambient %lf", &v) != 1 || !(v > 0 && v < 1e12)) return 0;
    c->v[c->n++ % NOISECAP_KEEP] = v;
    return 1;
}
