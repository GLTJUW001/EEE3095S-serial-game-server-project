#ifndef GAME_H
#define GAME_H

/* Tic-Tac-Toe rules. Pure C: no HAL or hardware includes, so it can be
 * unit-tested on a PC. The board is the single source of truth. */

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    G_OK = 0,
    G_OCCUPIED,   /* cell already taken            */
    G_RANGE,      /* index outside 0..8            */
    G_NOTURN,     /* mark does not match the turn  */
    G_OVER        /* game already finished         */
} move_result_t;

typedef enum { GS_PLAY = 0, GS_WIN, GS_DRAW } game_status_t;

void           game_reset(void);                    /* empty board, X to move */
move_result_t  game_move(char mark, int idx);       /* mark: 'X', 'O' or 0 = current player */
char           game_turn(void);                     /* 'X' or 'O' */
game_status_t  game_status(void);
char           game_winner(void);                   /* 'X', 'O' or '-' */
const char    *game_board(void);                    /* 9 chars + NUL, '.' = empty */

/* Move history: two chars per move, mark then cell, e.g. "X4O0X8". */
uint8_t        game_move_count(void);
const char    *game_history(void);

/* Computer opponent: picks a uniformly random EMPTY cell using rnd.
 * Returns -1 if the game is over or the board is full. The caller still
 * plays the cell through game_move(), so every rule is enforced as usual. */
int            game_ai_choose(uint32_t rnd);

#endif
