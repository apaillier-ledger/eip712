#!/usr/bin/env python3

import json
import sys
import re
from enum import IntEnum, auto

# defines
CLA             = 0xe0
INS_STRUCT_DEF  = 0x18
INS_STRUCT_IMPL = 0x1a
P1_FULL         = 0x00
P1_PARTIAL      = 0xFF
P2_NAME         = 0x00
P2_ARRAY        = 0x0F
P2_FIELD        = 0xFF

class ArrayType(IntEnum):
    dynamic = 0
    fixed_size = auto()

class Type(IntEnum):
    custom = 0
    # native types
    sol_int = auto()
    sol_uint = auto()
    sol_address = auto()
    sol_bool = auto()
    sol_string = auto()
    sol_byte = auto()
    sol_bytes_fix = auto()
    sol_bytes_dyn = auto()


# Write an APDU with given parameters, computes LC automatically from the data
def send_apdu(ins, p1, p2, data):
    sys.stdout.buffer.write(bytes([CLA, ins, p1, p2, len(data)]))
    sys.stdout.buffer.write(data)


def send_struct_def_name(name):
    data = bytearray()
    for char in name:
        data.append(ord(char))
    send_apdu(INS_STRUCT_DEF, P1_FULL, P2_NAME, data)


# From a string typename, extract the type and all the array depth
# Input  = "uint8[2][][4]"
# Output = ('uint8', [2, None, 4])
def get_array_levels(typename):
    array_levels = list()
    regex = re.compile("(.*)\[([0-9]*)\]$")

    while True:
        result = regex.search(typename)
        if not result:
            break
        typename = result.group(1)

        level_size = result.group(2)
        if len(level_size) == 0:
            level_size = None
        else:
            level_size = int(level_size)
        array_levels.insert(0, level_size)
    return (typename, array_levels)


def send_struct_def_field(typename, keyname):
    type_enum = None
    typesize = 0

    (typename, array_levels) = get_array_levels(typename)

    # extract type size with regex
    int_regex = re.compile("^(u?int)([0-9]*)$")
    bytes_f_regex = re.compile("^(bytes)([0-9]+)$")
    int_result = int_regex.search(typename)
    bytes_f_result = bytes_f_regex.search(typename)

    if int_result:
        if int_result.group(1) == "int":
            type_enum = Type.sol_int
        else:
            type_enum = Type.sol_uint
        typesize = int(int(int_result.group(2)) / 8) # bits -> bytes
    elif bytes_f_result:
        type_enum = Type.sol_bytes_fix
        typesize = int(bytes_f_result.group(2))
    elif typename == "address":
        type_enum = Type.sol_address
    elif typename == "bool":
        type_enum == Type.sol_bool
    elif typename == "string":
        type_enum = Type.sol_string
    elif typename == "byte":
        type_enum = Type.sol_byte
    elif typename == "bytes":
        type_enum = Type.sol_bytes_dyn
    else:
        type_enum = Type.custom

    data = bytearray()
    data.append(((len(array_levels) > 0) << 7) | ((typesize > 0) << 6) | type_enum) # typedesc
    if type_enum == Type.custom:
        data.append(len(typename))
        for char in typename:
            data.append(ord(char))
    if typesize > 0:
        data.append(typesize)
    if len(array_levels) > 0:
        data.append(len(array_levels))
        for lvl in array_levels:
            if lvl == None:
                data.append(ArrayType.dynamic)
            else:
                data.append(ArrayType.fixed_size)
                data.append(lvl)
    data.append(len(keyname))
    for char in keyname:
        data.append(ord(char))

    send_apdu(INS_STRUCT_DEF, P1_FULL, P2_FIELD, data)
    return (type_enum, array_levels)


def send_struct_impl_name(structname):
    data = bytearray()
    for char in structname:
        data.append(ord(char))
    send_apdu(INS_STRUCT_IMPL, P1_FULL, P2_NAME, data)


def send_struct_impl_field(struct_def, key, value):
    return




def main(input_file):
    with open(input_file, "r") as data:
        data_json = json.load(data)
        domain_typename = "EIP712Domain"
        message_typename = data_json["primaryType"]
        types = data_json["types"]
        domain = data_json["domain"]
        message = data_json["message"]

        # send types definition
        for key in types.keys():
            send_struct_def_name(key)
            for field in types[key]:
                ret = send_struct_def_field(field["type"], field["name"])
                (field["enum"], field["array_levels"]) = ret

        # send domain implementation
        send_struct_impl_name("EIP712Domain")
        for key, val in data_json["domain"].items():
            send_struct_impl_field(types["EIP712Domain"],
                                   key,
                                   val)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: %s JSON_FILE" % (sys.argv[0]))
        quit(1)
