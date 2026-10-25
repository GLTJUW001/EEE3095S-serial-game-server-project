#include "game.h"

static char board[10];
static char turn;
static char winner;
static uint8_t moves;
static game_status_t status;

static const uint8_t lines[8][3] = {
    {0, 1, 2}, {3, 4, 5}, {6, 7, 8},
    {0, 3, 6}, {1, 4, 7}, {2, 5, 8},
    {0, 4, 8}, {2, 4, 6}
};

void game_reset(void)
{
    for (uint8_t i = 0; i < 9u; ++i) board[i] = '.';
    board[9] = '\0';
    turn = 'X';
    winner = '-';
    moves = 0;
    status = GS_PLAY;
}

/* Validation order is fixed by the protocol spec: turn, range, occupied.
 * The board is written ONLY after every check has passed, so a rejected
 * request cannot change any game state. */
move_result_t game_move(char mark, int idx)
{
    if (status != GS_PLAY)             return G_OVER;
    if (mark != 0 && mark != turn)     return G_NOTURN;
    if (idx < 0 || idx > 8)            return G_RANGE;
    if (board[idx] != '.')             return G_OCCUPIED;

    /* ---- commit point: state changes below this line only ---- */
    board[idx] = turn;
    ++moves;

    for (uint8_t l = 0; l < 8u; ++l)
    {
        if (board[lines[l][0]] == turn &&
            board[lines[l][1]] == turn &&
            board[lines[l][2]] == turn)
        {
            status = GS_WIN;
            winner = turn;
            return G_OK;
        }
    }
    if (moves == 9u)
    {
        status = GS_DRAW;
        return G_OK;
    }
    turn = (turn == 'X') ? 'O' : 'X';
    return G_OK;
}

char          game_turn(void)   { return turn; }
game_status_t game_status(void) { return status; }
char          game_winner(void) { return winner; }
const char   *game_board(void)  { return board; }
