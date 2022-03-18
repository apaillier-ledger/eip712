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
# Input  = "uint8[2][][4]"          |   "bool"
# Output = ('uint8', [2, None, 4])  |   ('bool', [])
def get_array_levels(typename):
    array_lvls = list()
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
        array_lvls.insert(0, level_size)
    return (typename, array_lvls)


# From a string typename, extract the type and its size
# Input  = "uint64"         |   "string"
# Output = ('uint', 64)     |   ('string', None)
def get_typesize(typename):
    regex = re.compile("^(\w+?)(\d*)$")
    result = regex.search(typename)
    typename = result.group(1)
    typesize = result.group(2)
    if len(typesize) == 0:
        typesize = None
    else:
        typesize = int(typesize)
    return (typename, typesize)



def parse_int(typesize):
    return (Type.sol_int, int(typesize / 8))

def parse_uint(typesize):
    return (Type.sol_uint, int(typesize / 8))

def parse_address(typesize):
    return (Type.sol_string, None)

def parse_bool(typesize):
    return (Type.sol_bool, None)

def parse_string(typesize):
    return (Type.sol_string, None)

def parse_byte(typesize):
    return (Type.sol_byte, None)

def parse_bytes(typesize):
    if typesize != None:
        return (Type.sol_bytes_fix, typesize)
    return (Type.sol_bytes_dyn, None)

# set functions for each type
parsing_type_functions = {};
parsing_type_functions["int"] = parse_int
parsing_type_functions["uint"] = parse_uint
parsing_type_functions["address"] = parse_address
parsing_type_functions["bool"] = parse_bool
parsing_type_functions["string"] = parse_string
parsing_type_functions["byte"] = parse_byte
parsing_type_functions["bytes"] = parse_bytes



def send_struct_def_field(typename, keyname):
    type_enum = None

    (typename, array_lvls) = get_array_levels(typename)
    (typename, typesize) = get_typesize(typename)

    if typename in parsing_type_functions.keys():
        (type_enum, typesize) = parsing_type_functions[typename](typesize)
    else:
        type_enum = Type.custom
        typesize = None

    data = bytearray()
    data.append(((len(array_lvls) > 0) << 7) | ((typesize != None) << 6) | type_enum) # typedesc
    if type_enum == Type.custom:
        data.append(len(typename))
        for char in typename:
            data.append(ord(char))
    if typesize != None:
        data.append(typesize)
    if len(array_lvls) > 0:
        data.append(len(array_lvls))
        for lvl in array_lvls:
            if lvl == None:
                data.append(ArrayType.dynamic)
            else:
                data.append(ArrayType.fixed_size)
                data.append(lvl)
    data.append(len(keyname))
    for char in keyname:
        data.append(ord(char))

    send_apdu(INS_STRUCT_DEF, P1_FULL, P2_FIELD, data)
    return (typename, type_enum, typesize, array_lvls)



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
            for f in types[key]:
                (f["type"], f["enum"], f["typesize"], f["array_lvls"]) = \
                send_struct_def_field(f["type"], f["name"])

        # send domain implementation
        send_struct_impl_name("EIP712Domain")
        for key, val in data_json["domain"].items():
            send_struct_impl_field(types["EIP712Domain"],
                                   key,
                                   val)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        quit(0 if main(sys.argv[1]) else 1)
    else:
        print("Usage: %s JSON_FILE" % (sys.argv[0]), file=sys.stderr)
        quit(1)
