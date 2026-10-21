/* The noise cap of wake word arbitration (main.c wake_heard): how much of the front end's ambientEnergy an Echo's score
 * counts.  Pure arithmetic, no locks, no files: arb.c keeps the one instance (state/arbitration), main.c calls it. */
#ifndef NOISECAP_H
#define NOISECAP_H
#include <stddef.h>

#define NOISECAP_KEEP 64                /* the quiet level: the median of the last 64 rounds without media in the room */
#define NOISECAP_LEARN 10               /* no cap until 10 of them are in */

struct noisecap { double v[NOISECAP_KEEP]; unsigned n; };     /* a ring, n ever taken */

/* The learned quiet level: the median of the samples kept, 0 while fewer than NOISECAP_LEARN */
double noisecap_quiet(const struct noisecap *c);
/* One round: the ambient to count, min(ambient, factor x quiet) (factor 0: off, or nothing learned yet: ambient as it
 * is), from the quiet level learned before this round; then, if no media plays in the room, this round's ambient is
 * learned.  quiet: the level used (0: none yet).  Returns whether the samples changed (to be saved). */
int    noisecap_round(struct noisecap *c, int factor, double ambient, int media, double *counted, double *quiet);
/* state/arbitration: the samples kept as "ambient <v>" lines, oldest first; noisecap_line takes one such line (0: it
 * was not one) */
size_t noisecap_format(const struct noisecap *c, char *out, size_t cap);
int    noisecap_line(struct noisecap *c, const char *line);
#endif
