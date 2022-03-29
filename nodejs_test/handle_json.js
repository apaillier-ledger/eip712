#!/usr/bin/env node

const assert = require('assert');
const fs = require('fs');
const keccak256 = require('keccak256');
const eip712 = require('eip-712');



const rawdata = fs.readFileSync('data.json');
const gData = JSON.parse(rawdata);

/*
function    get_node(node_depth)
{
    let node_key;
    let node_value = gData;

    for (let i = 0; i < node_depth; ++i)
    {
        node_key = Object.keys(node_value)[index_buffer[i]];
        node_value = node_value[node_key];
    }
    return {
        key: node_key,
        value: node_value
    };
}

function    get_current_node()
{
    return get_node(depth);
}

function    show_node(node)
{
    // Don't show content of objects and arrays (won't be feasable on the device anyway)
    if (typeof(node.value) === 'object')
    {
        if (Array.isArray(node.value))
        {
            node.value = '[Array]';
        }
        else
        {
            node.value = '{Object}';
        }
    }
    node.moves = {
        up: can_go_up(),
        left: can_go_left(),
        right: can_go_right(),
        down: can_go_down()
    };
    console.log(node);
}

function    show_current_node()
{
    show_node(get_current_node());
}

// Functions to check if movements are possible
function    can_go_right()
{
    const   parent_node = get_node(depth - 1);

    return (Object.keys(parent_node.value).length > (index_buffer[depth - 1] + 1));
}
function    can_go_left()
{
    return (index_buffer[depth - 1] > 0);
}
function    can_go_up()
{
    return (depth > 1);
}
function    can_go_down()
{
    const node = get_current_node();

    return (typeof(node.value) === 'object');
}
//

// Functions to move in the JSON tree
function    go_right()
{
    if (can_go_right())
    {
        index_buffer[depth - 1] += 1;
        return true;
    }
    return false;
}
function    go_left()
{
    if (can_go_left())
    {
        index_buffer[depth - 1] -= 1;
        return true;
    }
    return false;
}
function    go_up()
{
    if (can_go_up())
    {
        depth -= 1;
        return true;
    }
    return false;
}
function    go_down()
{
    if (can_go_down())
    {
        depth += 1;
        index_buffer[depth - 1] = 0;
        return true;
    }
    return false;
}


let index_buffer = [ 0 ];
let depth = 1;

function    interactive_version()
{
    // Keyboard key -> function
    // qwerty
    const fncts = {
        'w' : go_up,
        'a' : go_left,
        's' : go_down,
        'd' : go_right,
        'q' : process.exit
    };

    show_current_node();

    process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on('data', function (keydata) {
        const input = String.fromCharCode(keydata[0]);
        let valid = false;

        if (Object.keys(fncts).includes(input))
        {
            valid = fncts[input]();
        }
        if (valid) show_current_node();
    });
}


//

const NODE_OBJECT = 0;
const NODE_ARRAY = 1;
const NODE_PRIMITIVE = 2;

function    get_node_type(node)
{
    if (typeof(node) === 'object')
    {
        if (Array.isArray(node))
        {
            return NODE_ARRAY;
        }
        return NODE_OBJECT;
    }
    return NODE_PRIMITIVE;
}

function    add_to_path(path, key, parent_node_type)
{
    switch (parent_node_type)
    {
        case NODE_OBJECT:
        {
            path += ("." + key);
            break;
        }
        case NODE_ARRAY:
        {
            path += ("[" + key + "]");
            break;
        }
    }
    return path;
}

function    handle_depth(json_depth, node_type, path = "$")
{
    const keys = Object.keys(json_depth);

    for (let i = 0; i < keys.length; ++i)
    {
        const key = keys[i];
        const value = json_depth[key];

        if (typeof(value) === 'object')
        {
            handle_depth(value,
                         get_node_type(value),
                         add_to_path(path, key, node_type));
        }
        else
        {
            console.log("Key path = \"" + add_to_path(path, key, node_type) + "\"");
            console.log("Value = \"" + value + "\"");
        }
    }
}

function    depth_first_version()
{
    handle_depth(gData, get_node_type(gData));
}
*/


/////////////////////////////////////////////////////////////////////

// Detect type
const   TYPE_INVALID    = 0;
const   TYPE_INTEGER    = 1;
const   TYPE_BOOL       = 2;
const   TYPE_STRING     = 3;
const   TYPE_ADDRESS    = 4;
const   TYPE_BYTES      = 5;
const   TYPE_CUSTOM     = 6;
function    get_type_enum(structs, typename)
{
    if ((res = /u?int(\d+)/.exec(typename)))
    {
        // check that it's a native integer type
        const calc = res[1] / 8;
        if ((calc >= 1) && (calc <= 32) && ((res[1] % 8) === 0))
        {
            return TYPE_INTEGER;
        }
        else
        {
            return TYPE_CUSTOM;
        }
    }
    else if (typename === "address") // not else if on purpose
    {
        return TYPE_ADDRESS;
    }
    else if (typename === "bool")
    {
        return TYPE_BOOL;
    }
    else if (typename === "string")
    {
        return TYPE_STRING;
    }
    else if (typename === "bytes")
    {
        return TYPE_BYTES;
    }
    else if (Object.keys(structs).includes(typename))
    {
        return TYPE_CUSTOM;
    }

    return TYPE_INVALID;
}

function    get_typestr_native(types, name)
{
    return name;
}

function    get_typestr_custom(types, name)
{
    return get_type_string(types, name);
}

function    get_type_string(types, name)
{
    let type_str = "";
    let custom_type_deps = [];

    if (name in types)
    {
        type_str += (name + "(");
        for (let i = 0; i < types[name].length; ++i)
        {
            const elem = types[name][i];
            const [typename, isarray] = get_type(elem.type);
            const type_enum = get_type_enum(types, typename);

            if (i > 0) type_str += ",";

            assert(type_enum !== TYPE_INVALID);

            if (type_enum === TYPE_CUSTOM)
            {
                if (!custom_type_deps.includes(typename))
                {
                    custom_type_deps.push(typename);
                }
            }

            type_str += typename;
            if (isarray) type_str += "[]";
            type_str += (" " + elem.name)
        }
        type_str += ")";
    }
    custom_type_deps.forEach(typename => {
        type_str += get_type_string(types, typename);
    });
    return type_str;
}

function    get_type_hash(types, name)
{
    return keccak256(get_type_string(types, name));
}

function    encode_address(structs, type, value)
{
    let buf;

    // skip the 0x
    buf = Buffer.from(value.substring(2), "hex");
    return Buffer.concat([Buffer.alloc(12, 0), buf]);
}

// Somehow JS treats numbers as 32 bit for binary shifts
function    lshift(number, bits)
{
    return (number * Math.pow(2, bits));
}
function    rshift(number, bits)
{
    return (number / Math.pow(2, bits));
}

function    encode_integer(structs, type, value)
{
    let buf;

    buf = Buffer.allocUnsafe(32);
    // Left zero padding
    for (let i = 32; i > 0; --i)
    {
        let mask = lshift(0xFF, 8 * (i - 1));
        buf.writeUInt8(rshift(value & mask, 8 * (i - 1)), 32 - i);
    }
    return buf
}

function    encode_boolean(structs, type, value)
{
    // encode as integer
    return encode_integer(value | 0);
}

function    encode_dynamic(data)
{
    return keccak256(data);
}

function    encode_bytes(structs, type, value)
{
    if (value.startsWith("0x"))
    {
        value = value.substring(2);
    }
    return encode_dynamic(Buffer.from(value, "hex"));
}

function    encode_string(structs, type, value)
{
    return encode_dynamic(Buffer.from(value));
}

function    encode_struct(structs, type, value)
{
    return get_hash_struct(structs, type, value);
}

function    encode_property(structs, key, value, type)
{
    const encode_funcs = {
        [TYPE_ADDRESS]: encode_address,
        [TYPE_INTEGER]: encode_integer,
        [TYPE_BOOL]: encode_boolean,
        [TYPE_STRING]: encode_string,
        [TYPE_BYTES]: encode_bytes,
        [TYPE_CUSTOM]: encode_struct
    };
    const type_enum = get_type_enum(structs, type);

    assert(type_enum !== TYPE_INVALID);
    return encode_funcs[type_enum](structs, type, value);
}

function    encode_array(types, key, value, array_type)
{
    let buf = [];

    value.forEach(elem => {
        buf.push(encode_property(types, key, elem, array_type));
    });
    return keccak256(Buffer.concat(buf));
}

function    get_type(raw_type)
{
    let array = false;
    let typename = raw_type;

    if (raw_type.endsWith("[]"))
    {
        array = true;
        typename = raw_type.substring(0, raw_type.length - 2);
    }
    return [
        typename,
        array
    ];
}

function    get_hash_struct(types, struct_typename, data, verbose = false)
{
    let values = [];
    let buf;

    values.push(get_type_hash(types, struct_typename));
    if (verbose)
    {
        console.log("get_hash_struct(" + types + ", " + struct_typename + ", " + data + ")");
        console.log("-> " + struct_typename + " TypeHash");
        console.log("0x" + values[0].toString('hex'));
    }
    types[struct_typename].forEach(elem => {
        const [typename, isarray] = get_type(elem.type);
        let key = elem.name;
        let value = data[elem.name];

        if (isarray)
        {
            buf = encode_array(types, key, value, typename, verbose);
            if (verbose) console.log(buf);
        }
        else
        {
            buf = encode_property(types, key, value, typename, verbose);
        }
        values.push(buf);
    });
    return keccak256(Buffer.concat(values));
}

function    test_hash()
{
    let domain_hash;
    let message_hash;

    console.log("=== Domain ===");
    //domain_hash = get_hash_struct(gData.types, "EIP712Domain", gData.domain);
    //console.log("Domain hash: 0x" + domain_hash.toString("hex"));
    console.log("encodeType: " + eip712.encodeType(gData, "EIP712Domain"));
    console.log("typeHash: 0x" + Buffer.from(eip712.getTypeHash(gData, "EIP712Domain")).toString("hex"));

    console.log("=== Message ===");
    //message_hash = get_hash_struct(gData.types, gData.primaryType, gData.message);//, true);
    //console.log("Message hash: 0x" + message_hash.toString("hex"));
    console.log("encodeType: " + eip712.encodeType(gData, gData.primaryType));
    console.log("typeHash: 0x" + Buffer.from(eip712.getTypeHash(gData, gData.primaryType)).toString("hex"));
}

//interactive_version();
//depth_first_version();
test_hash();
