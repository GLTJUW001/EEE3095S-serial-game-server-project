/* Host-side unit tests for Core/Src/game.c. Run with: make test */
#include "game.h"
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); ++failures; } } while (0)

/* Plays cell indices in order with no mark (current player moves). */
static void play(const char *digits)
{
    for (; *digits; ++digits) CHECK(game_move(0, *digits - '0') == G_OK);
}

int main(void)
{
    /* Fresh game */
    game_reset();
    CHECK(strcmp(game_board(), ".........") == 0);
    CHECK(game_turn() == 'X' && game_status() == GS_PLAY);

    /* Legal move and turn change */
    CHECK(game_move('X', 4) == G_OK);
    CHECK(strcmp(game_board(), "....X....") == 0 && game_turn() == 'O');

    /* Rejections leave the state unchanged */
    CHECK(game_move('X', 0) == G_NOTURN);
    CHECK(game_move('O', 4) == G_OCCUPIED);
    CHECK(game_move('O', 9) == G_RANGE);
    CHECK(game_move('O', -1) == G_RANGE);
    CHECK(game_move('O', 99999) == G_RANGE);
    CHECK(game_move('X', 99) == G_NOTURN);            /* turn is checked before range */
    CHECK(strcmp(game_board(), "....X....") == 0 && game_turn() == 'O');

    /* X wins on each of the 8 lines (X moves 1st, 3rd, 5th) */
    static const char *x_win[8] = {
        "03142",   /* 0,1,2 */   "30415",   /* 3,4,5 */
        "60718",   /* 6,7,8 */   "01326",   /* 0,3,6 */
        "10427",   /* 1,4,7 */   "20518",   /* 2,5,8 */
        "01428",   /* 0,4,8 */   "20416"    /* 2,4,6 */
    };
    for (int i = 0; i < 8; ++i)
    {
        game_reset();
        play(x_win[i]);
        CHECK(game_status() == GS_WIN);
        CHECK(game_winner() == 'X');
        CHECK(game_move(0, 8) == G_OVER);             /* no moves after the end */
    }

    /* O wins on the middle column: X0 O1 X3 O4 X8 O7 */
    game_reset();
    play("013487");
    CHECK(game_status() == GS_WIN && game_winner() == 'O');

    /* Draw: X0 O1 X2 O4 X3 O5 X7 O6 X8 */
    game_reset();
    play("01243576");
    CHECK(game_status() == GS_PLAY);
    play("8");
    CHECK(game_status() == GS_DRAW && game_winner() == '-');
    CHECK(strcmp(game_board(), "XOXXOOOXX") == 0);
    CHECK(game_move(0, 0) == G_OVER);

    /* History: mark + cell per move, rejected moves are not recorded */
    game_reset();
    CHECK(game_move_count() == 0 && strcmp(game_history(), "") == 0);
    CHECK(game_move(0, 4) == G_OK);
    CHECK(game_move(0, 4) == G_OCCUPIED);
    CHECK(game_move('X', 0) == G_NOTURN);
    CHECK(game_move(0, 0) == G_OK);
    CHECK(game_move(0, 8) == G_OK);
    CHECK(game_move_count() == 3 && strcmp(game_history(), "X4O0X8") == 0);
    game_reset();
    play("01243576");
    play("8");
    CHECK(game_move_count() == 9 && strcmp(game_history(), "X0O1X2O4X3O5X7O6X8") == 0);

    /* AI chooser: always an empty cell, covers every empty cell, none when over */
    game_reset();
    play("04");                                       /* X0 O4 */
    {
        int seen[9] = {0};
        for (uint32_t r = 0; r < 600; ++r)
        {
            int c = game_ai_choose(r * 2654435761u + 7u);
            CHECK(c >= 0 && c <= 8 && game_board()[c] == '.');
            if (c >= 0) seen[c]++;
        }
        CHECK(seen[0] == 0 && seen[4] == 0);
        for (int i = 1; i <= 8; ++i) if (i != 4) CHECK(seen[i] > 0);
    }
    game_reset();
    play("03142");                                    /* X wins */
    CHECK(game_ai_choose(1u) == -1);

    /* Reset clears everything */
    game_reset();
    CHECK(strcmp(game_board(), ".........") == 0 && game_status() == GS_PLAY && game_winner() == '-');

    if (failures == 0) printf("game_test: all passed\n");
    return failures != 0;
}
