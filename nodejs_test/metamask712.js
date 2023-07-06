#!/usr/bin/env node

const fs = require("fs")
const eth_sig_util = require ("@metamask/eth-sig-util")

const TypedDataUtils = eth_sig_util.TypedDataUtils
const SignTypedDataVersion = eth_sig_util.SignTypedDataVersion



const g_rawdata = fs.readFileSync(process.argv[2]);
const g_json_data = JSON.parse(g_rawdata);

function get_info(display_name,
                  name,
                  json_data) {
    obj = null
    if (name == "EIP712Domain") {
        obj = json_data.domain
    } else if (name == json_data.primaryType) {
        obj = json_data.message
    }
    console.log("========== "+ display_name + " ==========")
    const encode_type = TypedDataUtils.encodeType(name, json_data.types)
    const hash_struct = TypedDataUtils.hashStruct(name,
                                                  obj,
                                                  json_data.types,
                                                  SignTypedDataVersion.V4)
    console.log("encodeType = " + encode_type)
    console.log("hashStruct = 0x" + hash_struct.toString("hex"))
    console.log("==============================")
}

function get_domain_info(json_data) {
    get_info("Domain", "EIP712Domain", json_data)
}
function get_message_info(json_data) {
    get_info("Message", json_data.primaryType, json_data)
}

get_domain_info(g_json_data)
get_message_info(g_json_data)
