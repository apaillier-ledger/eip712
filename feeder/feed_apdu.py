#!/usr/bin/env python3

import json
import sys
import re
from enum import IntEnum, auto

# defines
CLA             = 0xe0
INS_STRUCT_DEF  = 0x18
INS_STRUCT_IMPL = 0x1a
INS_SIGN        = 0x0c
P1_COMPLETE     = 0x00
P1_PARTIAL      = 0xff
P2_NAME         = 0x00
P2_ARRAY        = 0x0f
P2_FIELD        = 0xff
P2_VERS_LEGACY  = 0x00
P2_VERS_NEW     = 0x01

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
    send_apdu(INS_STRUCT_DEF, P1_COMPLETE, P2_NAME, data)


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
    return (Type.sol_address, None)

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

    send_apdu(INS_STRUCT_DEF, P1_COMPLETE, P2_FIELD, data)
    return (typename, type_enum, typesize, array_lvls)



def send_struct_impl_name(structname):
    data = bytearray()
    for char in structname:
        data.append(ord(char))
    send_apdu(INS_STRUCT_IMPL, P1_COMPLETE, P2_NAME, data)



def send_struct_impl_array(size):
    data = bytearray()
    data.append(size)
    send_apdu(INS_STRUCT_IMPL, P1_COMPLETE, P2_ARRAY, data)



def encode_integer(value, typesize):
    data = bytearray()

    # Some are already represented as integers in the JSON, but most as strings
    if isinstance(value, str):
        base = 10
        if value.startswith("0x"):
            base = 16
        value = int(value, base)

    if value == 0:
        data.append(0)
    else:
        while value > 0:
            data.append(value & 0xff)
            value >>= 8
        data.reverse()
    return data

def encode_int(value, typesize):
    return encode_integer(value, typesize)

def encode_uint(value, typesize):
    return encode_integer(value, typesize)

def encode_hex_string(value, size):
    data = bytearray()
    value = value[2:] # skip 0x
    byte_idx = 0
    while byte_idx < size:
        data.append(int(value[(byte_idx * 2):(byte_idx * 2 + 2)], 16))
        byte_idx += 1
    return data

def encode_address(value, typesize):
    return encode_hex_string(value, 20)

def encode_bool(value, typesize):
    return encode_integer(value, typesize)

def encode_string(value, typesize):
    data = bytearray()
    for char in value:
        data.append(ord(char))
    return data

def encode_byte(value, typesize):
    return bytearray()

def encode_bytes_fix(value, typesize):
    return encode_hex_string(value, typesize)

def encode_bytes_dyn(value, typesize):
    # length of the value string
    # - the length of 0x (2)
    # / by the length of one byte in a hex string (2)
    return encode_hex_string(value, int((len(value) - 2) / 2))

# set functions for each type
encoding_functions = {}
encoding_functions[Type.sol_int] = encode_int
encoding_functions[Type.sol_uint] = encode_uint
encoding_functions[Type.sol_address] = encode_address
encoding_functions[Type.sol_bool] = encode_bool
encoding_functions[Type.sol_string] = encode_string
encoding_functions[Type.sol_bytes_fix] = encode_bytes_fix
encoding_functions[Type.sol_bytes_dyn] = encode_bytes_dyn



def send_struct_impl_field(value, field):
    data_w_length = bytearray()

    # Something wrong happened if this triggers
    if isinstance(value, list) or (field["enum"] == Type.custom):
        breakpoint()

    data = encoding_functions[field["enum"]](value, field["typesize"])

    # Add a 16-bit integer with the value's byte length (network byte order)
    data_w_length.append((len(data) & 0xff00) >> 8)
    data_w_length.append(len(data) & 0xff)

    data_w_length += data
    while len(data_w_length) > 0xff:
        send_apdu(INS_STRUCT_IMPL, P1_PARTIAL, P2_FIELD, data_w_length[:0xff])
        data_w_length = data_w_length[0xff:]
    send_apdu(INS_STRUCT_IMPL, P1_COMPLETE, P2_FIELD, data_w_length)



def evaluate_field(structs, data, field, lvls_left):
    array_lvls = field["array_lvls"]

    if len(array_lvls) > 0 and lvls_left > 0:
        send_struct_impl_array(len(data))
        idx = 0
        for subdata in data:
            if not evaluate_field(structs, subdata, field, lvls_left - 1):
                return False
            idx += 1
        if array_lvls[lvls_left - 1] != None:
            if array_lvls[lvls_left - 1] != idx:
                print("Mismatch in array size! Got %d, expected %d\n" %
                      (idx, array_lvls[lvls_left - 1]),
                      file=sys.stderr)
                return False
    else:
        if field["enum"] == Type.custom:
            if not send_struct_impl(structs, data, field["type"]):
                return False
        else:
            send_struct_impl_field(data, field)
    return True



def send_struct_impl(structs, data, structname):
    # Check if it is a struct we don't known
    if structname not in structs.keys():
        return False

    struct = structs[structname]
    for f in struct:
        if not evaluate_field(structs, data[f["name"]], f, len(f["array_lvls"])):
            return False
    return True


def send_sign():
    send_apdu(INS_SIGN, 0x00, P2_VERS_NEW, bytearray())


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
        send_struct_impl_name(domain_typename)
        if not send_struct_impl(types, domain, domain_typename):
            return False

        # send message implementation
        send_struct_impl_name(message_typename)
        if not send_struct_impl(types, message, message_typename):
            return False

        # sign
        send_sign()
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        quit(0 if main(sys.argv[1]) else 1)
    else:
        print("Usage: %s JSON_FILE" % (sys.argv[0]), file=sys.stderr)
        quit(1)
