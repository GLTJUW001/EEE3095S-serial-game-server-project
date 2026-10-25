#ifndef SERVER_H
#define SERVER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

typedef enum
{
    SRV_IDLE = 0,   /* waiting for CONNECT */
    SRV_PLAY,       /* game in progress */
    SRV_OVER        /* game finished (win / draw / resign) */
} srv_state_t;

/* Reset game and go to IDLE. */
void server_init(void);

/* Current server state. */
srv_state_t server_state(void);

/* SW0 pressed: reset game, go to IDLE, emit EVT:RESET. */
void server_button_reset(void);

/* Handle one complete, validated command line (checksum already stripped). */
void server_handle(const char *cmd);

#ifdef __cplusplus
}
#endif

#endif /* SERVER_H */