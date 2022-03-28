#ifndef MEM_H_
#define MEM_H_

#include <stdlib.h>

void    init_mem(void);
void    reset_mem(void);
void    *mem_alloc(size_t size);
void    mem_dealloc(size_t size);

#ifdef DEBUG
extern size_t mem_max;
#endif

#endif // MEM_H_
