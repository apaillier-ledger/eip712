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
P2_FIELD        = 0xFF

class Type(IntEnum):
    custom = 0
    # native types
    solidity_int = auto()
    solidity_uint = auto()
    solidity_address = auto()
    solidity_bool = auto()
    solidity_string = auto()
    solidity_byte = auto()
    solidity_bytes_fix = auto()
    solidity_bytes_dyn = auto()


# Write an APDU with given parameters, computes LC automatically from the data
def send_apdu(ins, p1, p2, data):
    sys.stdout.buffer.write(bytes([CLA, ins, p1, p2, len(data)]))
    sys.stdout.buffer.write(data)

def send_struct_def_name(name):
    data = bytearray()
    for char in name:
        data.append(ord(char))
    send_apdu(INS_STRUCT_DEF, P1_FULL, P2_NAME, data)

def send_struct_def_field(typename, keyname):
    field_type = None
    field_typesize = 0
    field_is_array = False

    # check if array type
    if typename.endswith("[]"):
        typename = typename[:-2]
        field_is_array = True

    # extract type size with regex
    int_regex = re.compile("^(u?int)([0-9]*)$")
    bytes_f_regex = re.compile("^(bytes)([0-9]+)$")
    int_result = int_regex.search(typename)
    bytes_f_result = bytes_f_regex.search(typename)

    if int_result:
        if int_result.group(1) == "int":
            field_type = Type.solidity_int
        else:
            field_type = Type.solidity_uint
        field_typesize = int(int(int_result.group(2)) / 8) # bits -> bytes
    elif bytes_f_result:
        field_type = Type.solidity_bytes_fix
        field_typesize = int(bytes_f_result.group(2))
    elif typename == "address":
        field_type = Type.solidity_address
    elif typename == "bool":
        field_type == Type.solidity_bool
    elif typename == "string":
        field_type = Type.solidity_string
    elif typename == "byte":
        field_type = Type.solidity_byte
    elif typename == "bytes":
        field_type = Type.solidity_bytes_dyn
    else:
        field_type = Type.custom

    data = bytearray()
    data.append((field_is_array << 7) | ((field_typesize > 0) << 6) | field_type) # typedesc
    if field_type == Type.custom:
        data.append(len(typename))
        for char in typename:
            data.append(ord(char))
    if field_typesize > 0:
        data.append(field_typesize)
    data.append(len(keyname))
    for char in keyname:
        data.append(ord(char))

    send_apdu(INS_STRUCT_DEF, P1_FULL, P2_FIELD, data)


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

        # send types definition
        types = data_json["types"]
        for key in types.keys():
            send_struct_def_name(key)
            for field in types[key]:
                send_struct_def_field(field["type"], field["name"])

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
        main("data.json")
