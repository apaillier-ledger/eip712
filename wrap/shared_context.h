#ifndef SHARED_CONTEXT_H_
#define SHARED_CONTEXT_H_

#include <stdio.h>

#include "libcxng.h"

#define ADDRESS_LENGTH 20

#define PRINTF(fmt, ...) printf(fmt, ##__VA_ARGS__)

extern cx_sha3_t    global_sha3;

#endif // SHARED_CONTEXT_H_
