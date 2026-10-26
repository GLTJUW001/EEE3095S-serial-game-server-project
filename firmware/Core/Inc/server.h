#ifndef SERVER_H
#define SERVER_H

#include <stdint.h>

typedef enum { SRV_IDLE = 0, SRV_PLAY, SRV_OVER } srv_state_t;

void        server_init(void);
void        server_handle(const char *cmd);   /* one validated, checksum-free command line */
void        server_set_time(uint32_t now_ms); /* entropy for the computer opponent */
void        server_button_reset(void);        /* local reset: IDLE + "EVT:RESET" */
srv_state_t server_state(void);

#endif
