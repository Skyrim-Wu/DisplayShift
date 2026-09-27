#ifndef DISPLAYSHIFT_REPLY_H
#define DISPLAYSHIFT_REPLY_H

#include <stddef.h>
#include <stdint.h>

enum { DS_REPLY_OK, DS_REPLY_NULL, DS_REPLY_INVALID, DS_REPLY_UNSUPPORTED };

/* LG GSM/0x5bcb on this Mac repeats 0x51 in the length field, but retains
 * the checksum for the canonical 0x88 header. Only accept this exact quirk
 * for that device, with all other fields and the canonical checksum intact.
 * Keep the raw buffer unchanged for diagnostics. */
static int ds_validate_reply(const uint8_t *reply, size_t size,
                             uint8_t feature, int lg_length_quirk) {
    if (size < 11) return DS_REPLY_INVALID;
    if (reply[0] == 0x6e && reply[1] == 0x80) return DS_REPLY_NULL;
    uint8_t length = reply[1];
    if (lg_length_quirk && length == 0x51) length = 0x88;
    if (reply[0] != 0x6e || length != 0x88 || reply[2] != 0x02
            || reply[4] != feature) return DS_REPLY_INVALID;
    uint8_t checksum = 0x50;
    for (size_t i = 0; i < 11; i++) checksum ^= i == 1 ? length : reply[i];
    if (checksum != 0) return DS_REPLY_INVALID;
    if (reply[3] != 0) return DS_REPLY_UNSUPPORTED;
    return DS_REPLY_OK;
}

#endif
