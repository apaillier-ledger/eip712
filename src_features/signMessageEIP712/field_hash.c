#include <stdlib.h>
#include "field_hash.h"
#include "encode_field.h"
#include "path.h"
#include "mem.h"
#include "eip712.h"
#include "shared_context.h"

static s_field_hashing *fh = NULL;

bool field_hash_init(void)
{
    if (fh == NULL)
    {
        if ((fh = mem_alloc(sizeof(*fh))) == NULL)
        {
            return false;
        }
        fh->state = FHS_IDLE;
    }
    return true;
}

const uint8_t *field_hash(const uint8_t *data,
                          uint8_t data_length,
                          bool partial)
{
    const void *field_ptr;
    e_type field_type;
    uint8_t *value = NULL;
#ifdef DEBUG
    const char *type;
    uint8_t typelen;
    const char *key;
    uint8_t keylen;
#endif


    (void)data;
    if (fh == NULL)
    {
        return NULL;
    }
    // get field by path
    if ((field_ptr = path_get_field()) == NULL)
    {
        return NULL;
    }
    field_type = struct_field_type(field_ptr);
    if (fh->state == FHS_IDLE) // first packet for this frame
    {
        fh->remaining_size = (data[0] << 8) | data[1]; // network byte order
        data += sizeof(uint16_t);
        data_length -= sizeof(uint16_t);
        fh->state = FHS_WAITING_FOR_MORE;
        if (IS_DYN(field_type))
        {
            cx_keccak_init((cx_hash_t*)&global_sha3, 256); // init hash
        }
    }
    fh->remaining_size -= data_length;
    // if a dynamic type -> continue progressive hash
    if (IS_DYN(field_type))
    {
        cx_hash((cx_hash_t*)&global_sha3,
                0,
                data,
                data_length,
                NULL,
                0);
    }
    if (fh->remaining_size == 0)
    {
        if (partial) // only makes sense if marked as complete
        {
            return NULL;
        }
#ifdef DEBUG
        PRINTF("=> ");
        type = get_struct_field_typename(field_ptr, &typelen);
        fwrite(type, sizeof(char), typelen, stdout);
        PRINTF(" ");
        key = get_struct_field_keyname(field_ptr, &keylen);
        fwrite(key, sizeof(char), keylen, stdout);
        PRINTF("\n");
#endif

        if (!IS_DYN(field_type))
        {
            switch (field_type)
            {
                case TYPE_SOL_INT:
                case TYPE_SOL_UINT:
                    value = encode_integer(data, data_length);
                    break;
                case TYPE_SOL_BYTES_FIX:
                    value = encode_bytes(data, data_length);
                    break;
                case TYPE_SOL_ADDRESS:
                    value = encode_address(data, data_length);
                    break;
                case TYPE_SOL_BOOL:
                    value = encode_boolean((bool*)data, data_length);
                    break;
                case TYPE_CUSTOM:
                default:
                    PRINTF("Unknown solidity type!\n");
                    return NULL;
            }

            if (value == NULL)
            {
                return NULL;
            }
        }
        else
        {
            if ((value = mem_alloc(KECCAK256_HASH_BYTESIZE)) == NULL)
            {
                return NULL;
            }
            // copy hash into memory
            cx_hash((cx_hash_t*)&global_sha3,
                    CX_LAST,
                    NULL,
                    0,
                    value,
                    KECCAK256_HASH_BYTESIZE);
        }

        // TODO: Move elsewhere
        uint8_t len = IS_DYN(field_type) ?
                      KECCAK256_HASH_BYTESIZE :
                      EIP_712_ENCODED_FIELD_LENGTH;
        // last thing in mem is the hash of the previous field
        // and just before it is the current hash context
        cx_sha3_t *hash_ctx = (cx_sha3_t*)(value - sizeof(cx_sha3_t));
        // start the progressive hash on it
        cx_hash((cx_hash_t*)hash_ctx,
                0,
                value,
                len,
                NULL,
                0);
        // deallocate it
        mem_dealloc(len);

        path_advance();
        fh->state = FHS_IDLE;
    }
    else
    {
        if (!partial || !IS_DYN(field_type)) // only makes sense if marked as partial
        {
            return NULL;
        }
    }

    return value;
}
