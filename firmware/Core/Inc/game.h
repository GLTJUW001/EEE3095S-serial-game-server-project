#ifndef GAME_H
#define GAME_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef enum
{
    GS_PLAY = 0,
    GS_WIN,
    GS_DRAW
} game_status_t;

typedef enum
{
    G_OK = 0,
    G_OVER,       /* game already finished */
    G_NOTURN,     /* mark does not match current turn */
    G_RANGE,      /* index out of 0..8 */
    G_OCCUPIED    /* target cell already taken */
} move_result_t;

/* Reset to an empty board, X to move, GS_PLAY. */
void game_reset(void);

/* Attempt a move. mark == 0 means "current turn". The board is only
 * modified if every validation check passes. */
move_result_t game_move(char mark, int idx);

/* Current player to move ('X' or 'O'). */
char game_turn(void);

/* Current game status. */
game_status_t game_status(void);

/* Winner mark if GS_WIN, otherwise '-'. */
char game_winner(void);

/* 9-character board string using '.', 'X', 'O' (NUL-terminated). */
const char *game_board(void);

#ifdef __cplusplus
}
#endif

#endif /* GAME_H */