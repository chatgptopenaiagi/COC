#ifndef COC_NATIVE_H
#define COC_NATIVE_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Caller supplies valid memory. 0=valid, 1=invalid JSON/contract, 2=invalid bounds. */
int coc_validate_json(const unsigned char *data, size_t length);
#ifdef __cplusplus
}
#endif
#endif
