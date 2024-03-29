#!/usr/bin/env python3

import argparse
import json
import sys
import re
from enum import IntEnum, auto
from ledgercomm import Transport
import hashlib
from ecdsa import SigningKey
from ecdsa.util import sigencode_der
import pdb
import time

# defines
CLA             = 0xe0
INS_SIGN        = 0x0c
INS_STRUCT_DEF  = 0x1a
INS_STRUCT_IMPL = 0x1c
INS_FILTERING   = 0x1e
P1_COMPLETE     = 0x00
P1_PARTIAL      = 0xff
P2_NAME         = 0x00
P2_ARRAY        = 0x0f
P2_FIELD        = 0xff
P2_VERS_LEGACY  = 0x00
P2_VERS_NEW     = 0x01
P2_FILT_ACTIVATE        = 0x00
P2_FILT_CONTRACT_NAME   = 0x0f
P2_FILT_FIELD_NAME      = 0xff

# global variables
parser = None
trans = None
filtering_paths = None
current_path = list()
sig_ctx = {}


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
    if args.speculos or args.device:
        print("> %.02x %.02x %.02x %.02x ... " % (CLA, ins, p1, p2), end="", flush=True)
        trans.send(cla=CLA, ins=ins, p1=p1, p2=p2, cdata=data)
        sw, response = trans.recv()
        # To simulate really bad transport latency
        #if ins == INS_STRUCT_IMPL:
        #    time.sleep(2)
        print(hex(sw))
        #print("Done!")
    else:
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
        if value < 0: # negative number, send it as unsigned
            mask = 0
            for i in range(typesize): # make a mask as big as the typesize
                mask = (mask << 8) | 0xff
            value &= mask
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

    if args.filtering:
        path = ".".join(current_path)
        if path in filtering_paths.keys():
            send_filtering_field_name(filtering_paths[path])

    send_apdu(INS_STRUCT_IMPL, P1_COMPLETE, P2_FIELD, data_w_length)



def evaluate_field(structs, data, field, lvls_left, new_level = True):
    array_lvls = field["array_lvls"]

    if new_level:
        current_path.append(field["name"])
    if len(array_lvls) > 0 and lvls_left > 0:
        send_struct_impl_array(len(data))
        idx = 0
        for subdata in data:
            current_path.append("[]")
            if not evaluate_field(structs, subdata, field, lvls_left - 1, False):
                return False
            current_path.pop()
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
    if new_level:
        current_path.pop()
    return True



def send_struct_impl(structs, data, structname):
    # Check if it is a struct we don't known
    if structname not in structs.keys():
        return False

    struct = structs[structname]
    for f in struct:
        if not evaluate_field(structs, data[f["name"]], f, len(f["array_lvls"])):
            return False
        #send_struct_def_name("EEaahh!") # To force crash
    return True

def send_sign():
    bip32path = bytearray.fromhex("8000002c8000003c800000000000000000000000")
    path_len = bytearray()
    path_len.append(int(len(bip32path) / 4))
    send_apdu(INS_SIGN, 0x00, P2_VERS_NEW, path_len + bip32path)

def send_filtering_activate():
    send_apdu(INS_FILTERING, P1_COMPLETE, P2_FILT_ACTIVATE, bytearray())

def send_filtering_info(p2, display_name, filters_count, sig):
    payload = bytearray()
    payload.append(len(display_name))
    for char in display_name:
        payload.append(ord(char))
    if p2 == P2_FILT_CONTRACT_NAME:
        payload.append(filters_count)
    payload.append(len(sig))
    payload += sig
    send_apdu(INS_FILTERING, P1_COMPLETE, p2, payload)

# ledgerjs doesn't actually sign anything, and instead uses already pre-computed signatures
def send_filtering_contract_name(display_name, filters_count: int):
    global sig_ctx

    #filters_count += 1 # force error in the app
    msg = bytearray()
    msg.append(183)
    msg += sig_ctx["chainid"]
    #print("chain id = %s" % (sig_ctx["chainid"].hex()))
    msg += sig_ctx["caddr"]
    #print("contract addr = %s" % (sig_ctx["caddr"].hex()))
    msg += sig_ctx["schema_hash"]
    #print("schema hash = %s" % (sig_ctx["schema_hash"].hex()))
    msg.append(filters_count)
    for char in display_name:
        msg.append(ord(char))

    sig = sig_ctx["key"].sign_deterministic(msg, sigencode=sigencode_der)
    send_filtering_info(P2_FILT_CONTRACT_NAME, display_name, filters_count, sig)

# ledgerjs doesn't actually sign anything, and instead uses already pre-computed signatures
def send_filtering_field_name(display_name):
    global sig_ctx

    path_str = ".".join(current_path)

    msg = bytearray()
    msg.append(72)
    msg += sig_ctx["chainid"]
    msg += sig_ctx["caddr"]
    msg += sig_ctx["schema_hash"]
    for char in path_str:
        msg.append(ord(char))
    for char in display_name:
        msg.append(ord(char))
    sig = sig_ctx["key"].sign_deterministic(msg, sigencode=sigencode_der)
    send_filtering_info(P2_FILT_FIELD_NAME, display_name, None, sig)

def read_filtering_file(domain, message):
    data_json = None
    with open("%s-filter.json" % (args.JSON_FILE)) as data:
        data_json = json.load(data)
    return data_json

def prepare_filtering(filtr_data, message):
    global filtering_paths

    if "fields" in filtr_data:
        filtering_paths = filtr_data["fields"]
    else:
        filtering_paths = {}

def handle_optional_domain_values(domain):
    if "chainId" not in domain.keys():
        domain["chainId"] = 0
    if "verifyingContract" not in domain.keys():
        domain["verifyingContract"] = "0x0000000000000000000000000000000000000000"

def init_signature_context(types, domain):
    global sig_ctx

    handle_optional_domain_values(domain)
    with open(args.keypath, "r") as priv_file:
        sig_ctx["key"] = SigningKey.from_pem(priv_file.read(), hashlib.sha256)
        caddr = domain["verifyingContract"]
        if caddr.startswith("0x"):
            caddr = caddr[2:]
        sig_ctx["caddr"] = bytearray.fromhex(caddr)
        chainid = domain["chainId"]
        sig_ctx["chainid"] = bytearray()
        for i in range(8):
            sig_ctx["chainid"].append(chainid & (0xff << (i * 8)))
        sig_ctx["chainid"].reverse()
        schema_str = json.dumps(types).replace(" ","")
        schema_hash = hashlib.sha224(schema_str.encode())
        sig_ctx["schema_hash"] = bytearray.fromhex(schema_hash.hexdigest())

        return True
    return False

def main():
    global sig_ctx

    with open(args.JSON_FILE, "r") as data:
        data_json = json.load(data)
        domain_typename = "EIP712Domain"
        message_typename = data_json["primaryType"]
        types = data_json["types"]
        domain = data_json["domain"]
        message = data_json["message"]

        if args.filtering:
            if not init_signature_context(types, domain):
                return False
            filtr = read_filtering_file(domain, message)

        # send types definition
        for key in types.keys():
            send_struct_def_name(key)
            for f in types[key]:
                (f["type"], f["enum"], f["typesize"], f["array_lvls"]) = \
                send_struct_def_field(f["type"], f["name"])

        if args.filtering:
            send_filtering_activate()
            prepare_filtering(filtr, message)

        # send domain implementation
        send_struct_impl_name(domain_typename)
        if not send_struct_impl(types, domain, domain_typename):
            return False

        if args.filtering:
            if filtr and "name" in filtr:
                send_filtering_contract_name(filtr["name"], len(filtering_paths))
            else:
                send_filtering_contract_name(sig_ctx["domain"]["name"], len(filtering_paths))

        # send message implementation
        send_struct_impl_name(message_typename)
        if not send_struct_impl(types, message, message_typename):
            return False

        # sign
        send_sign()
    if trans:
        trans.close()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("JSON_FILE")
    parser.add_argument("-s", "--speculos", action="store_true")
    parser.add_argument("-d", "--device", action="store_true")
    parser.add_argument("-f", "--filtering", action="store_true")
    parser.add_argument("-k", "--keypath", default="feeder/key/key.pem")
    args = parser.parse_args()
    if (args.speculos):
        trans = Transport(interface="tcp", server="127.0.0.1", port=9999, debug=True)
    elif (args.device):
        trans = Transport(interface="hid", debug=True)
    quit(0 if main() else 1)
