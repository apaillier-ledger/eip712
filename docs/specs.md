## EIP712 meeting (10/02/22)

* Forward-only streaming
* Need all content to validate the hash
* Have for each key/value combo the option to skip it (for very long, multi-screen value ones)
* Have for each key/value the option to completely skip the rest of the json (the device will
  still receive the remaining but not display it)
* Maybe show the keys as JsonPath, to have a better understanding of where we are in the tree

* The whitelisting feature will come later, will be signed by the backend to ensure authenticity

## TODO

### Figure out how all the hashing works 
* Typehash => Done
* hashStructs => Done

Archi:
* Send types to the device
    * Device stores it all in RAM
* Send domain to the device field by field
    * Device checks everything against the predefined type in RAM and starts computing the hash
* Send message the same way as the domain

* Everything is sent as strings, the FW will parse it

## Specs

### APDUs

#### Send struct definition
INS 0x18

P1  0x00
P2  0x00, name (length infered from LC)
Byte values     | 'O' | 'r' | 'd' | 'e' | 'r' |
Byte meaning    |       Name (as string)      |

P1  0x00 (send complete) / 0xFF (partial, more to come)
P2  0xFF, field

P1's value can indicate a partial send, it means the data in the APDU is too long (> 256 bytes)
and has been split into multiple APDUs but still following the same scheme (length + data).

Byte values     |   0x41   |   0x01   |   0x03    | 'i' | 'd' | 'x' |
Byte meaning    | TypeDesc | TypeSize | KeyLength | Key (as string) |
=> int8 idx

Byte values     |   0xC2   |   0x08   |    0x02    |   0x00   |   0x01   |    0x02   |   0x03    | 'I' | 'D' | 's' |
Byte meaning    | TypeDesc | TypeSize | ArrayCount | DynArray | FixArray | ArraySize | KeyLength | Key (as string) |
=> uint64 matches[][2]

Byte values     |   0x00   |  0x06  | 'P' | 'e' | 'r' | 's' | 'o' | 'n' |    0x02   |    't' | 'o'    |
Byte meaning    | TypeDesc | Length |        TypeName (as string)       | KeyLength | Key (as string) |
=> Person to


##### TypeDesc

The upper 4 bits are used as binary flags for the given type:
* The 8th bit, when set to 1, indicates there will be a TypeArray
* The 7th bit, when set to 1, indicates there will be a TypeSize
* The 6th bit is unused for now
* The 5th bit is unused for now

The lower 4 bits indicate the type, when evaluated as a 4-bit value:
* 0 -> custom struct (defined by the contract)
* 1 -> int  (8 / 16 / 32 / 64 / 128 / 256)
* 2 -> uint (8 / 16 / 32 / 64 / 128 / 256)
* 3 -> address
* 4 -> bool
* 5 -> string
* 6 -> fixed-size bytes (1..32)
* 7 -> dynamic-size bytes

=> TypeSize can only be set if the type is not a custom struct.

##### TypeSize (optional)

=> Always the first byte after TypeDesc.

Component indicating the size in byte of native solidity types that require it, including:
* int
* uint
* fixed-size bytes


##### TypeName (optional)

=> Always starts one byte after TypeDesc.

##### TypeArray (optional)

=> Starts one byte after TypeSize or TypeName, if not present: one byte after TypeDesc.

Byte values     |   0x02     |   0x00    |   0x01    |   0x03    |
Byte meaning    | ArrayCount | ArrayType | ArrayType | ArraySize |

Array Count: Indicates how many array levels

Array Type:
* 0 -> Dynamic size
* 1 -> Fixed size (followed by a byte indicating how many elements in the array)

Array Size (optional): Indicates how big the fixed size array is

#### Send struct implementation (to display & hash)
INS 0x1A

P1  0x00
P2  0x00, name (length infered from LC)
Byte values     | 'E' | 'I' | 'P' | '7' | '1' | '2' | 'D' | 'o' | 'm' | 'a' | 'i' | 'n' |
Byte meaning    |                            Name (as string)                           |
=> Indicates the typename of the incoming structure implementation

P1  0x00
P2  0x0F, array
Byte values     |  0x07  |
Byte meaning    |  Size  |
=> Indicates the following $Size fields will all be in an array

P1  0x00 (send complete) / 0xFF (partial, more to come)
P2  0xFF, field
Byte values     | 0x00 | 0x03 | 0x01 | 0x33 | 0x37 |
Byte meaning    |    Length   |    Raw value       |
=> Gives a field value


The value in the APDU is represented into a format that's tied to its type.
Every value in JSON is a string, but an integer 128 is going to be sent as
as one byte         | 0x80 |
instead of three    | '1' | '2' | '8' |

#### sign EIP 712
INS 0x0C
P1  0x00
P2  0x00 (old version for backward compatibility) / 0x01 (new version)
LC  0x00 (no data)


### Flow

Given these structs:

primary struct outer {
    int     a
    inner   b
}

struct inner {
    int     a
    int     c
}

#### Receiving the struct definitions

INS | P1  | P2  | message
-----------------------------
0x18  0x00  0x00  "outer"
0x18  0x00  0xFF  "int" "a"
0x18  0x00  0XFF  "inner" "b"
0x18  0x00  0x00  "inner"
0x18  0x00  0xFF  "int" "a"
0x18  0x00  0xFF  "int" "c"


* len(structs)
    * len(name) "outer"
        * len(fields)
            * len(type) "int"   len(name) "a"
            * len(type) "inner" len(name) "b"
    * len(name) "inner"
        * len(fields)
            * len(type) "int"   len(name) "a"
            * len(type) "int"   len(name) "c"

#### Receiving the struct values

INS | P1  | P2  | message
-----------------------------
0x1A  0x00  0x00  "outer"
0x1A  0x00  0xFF  "a" "34"
0x1A  0x00  0xFF  "a" "145"
0x1A  0x00  0xFF  "c" "7"

* After the first apdu (set name), we keep in mind which key we are expecting next :
  The type is outer, its first key is "a" of type "int", it is a solidity native type, so we will wait for it. -> "a"
* After we get our first value, we look for which will be the next key to expect :
  The next key is "b" of type "inner", it is not a solidity type and is a contract-defined struct so we will get the
  first key in it, "a" of type "int", it is a solidity native type so we will wait for it. -> "a"
* The next key is "c" of type "int", it is a solidity native type, so we will wait for it. -> "c"

How do we keep track of which key to get, two options :
* a depth first search index, for example to get the "c" of struct inner with outer as primary type, it would be index 3
  (forth one)
* a dynamic path-like index approach, each index would represent a struct depth, to get that same "c" key, it woud be 1->1

#### How to manage hashing in RAM

primary struct outer {
    int     a
    inner   b
}

struct inner {
    int     a
    int     c
}

Solution #1
-----------
-> struct outer
    -> compute typeHash
        -> start progressive struct hash on it (in RAM)
-> field a (outer)
    -> encode to 32 bytes & hash
        -> continue progressive struct hash on it (in RAM)
-> field a (inner)
    -> first field of struct inner
        -> compute typeHash
            -> start progressive struct hash on it (in RAM)
    -> encode to 32 bytes & hash
        -> continue progressive struct hash on it (in RAM)
-> field c (inner)
    -> encode to 32 bytes & hash
        -> continue progressive struct hash on it (in RAM)
    -> last field of struct inner
        -> finish progressive hash and continue progressive hash to the parent struct (in RAM)

Solution #2
-----------
-> struct outer
    -> compute typeHash (store in RAM)
TH  TypeHash
FH  FieldHash
SH  StructHash
| TH1 |
-> field a (outer)
    -> encode to 32 bytes & hash (store in RAM)
| TH1 | FH2 |
-> field a (inner)
    -> first field of struct inner
        -> compute typeHash (store in RAM)
| TH1 | FH2 | TH3 |
    -> encode to 32 bytes & hash (store in RAM)
| TH1 | FH2 | TH3 | FH4 |
-> field c (inner)
    -> encode to 32 bytes & hash (store in RAM)
| TH1 | FH2 | TH3 | FH4 | FH5 |
    -> last field of struct inner
        -> do a hash of all hashes from struct inner (store in RAM)
| TH1 | FH2 | SH6 |
    -> last field of struct outer
        -> do a hash of all hashes from struct outer (store in RAM)
| SH7 |


List of scope-indexes making up the path of the next field in the message
| IDX1 | IDX2 | IDX3 | ... |

Count of used indexes
| PATH_LENGTH |

List of array levels:
    Each element has two property:
        * Path index
        * Array size
    Memory heavy if one field as multiple array levels, but unlikely as we'll
    probably have multiple fields with only one array level.

    Works with array of structs even if we don't really evaluate them, rather only the
    native-type fields inside, since we can point to it with the path idx.

## How to make sense of all the computed hashes

Have a marker byte after each hash.

| HASH 1 | HASH MARKER 1 | HASH 2 | HASH MARKER 2 |

Hash marker : 1 byte

| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 | bits
|---------------|---------------|
| backward info | forward info  |

### backward info

About the hash that preceeds the marker :

* FIELD HASH
* TYPE HASH
* 


### forward info

About what follows the marker (not necessarily just the next hash)




Stack of progressive hashes :

* push when going down a depth level + start with typehash (for structs)
* pop when going up a depth level + continue the previous progressive hash (if it exists) with the computed one
* update the top one when encountering a new field of the same depth level


primary struct outer {
    int     a
    inner   b
}

struct inner {
    int     a
    int     c
}

-> push new prog hash + start with outer's typehash
-> continue last hash with hash of a
-> push new prog hash + start with inner's typehash
-> continue last hash with hash of a
-> continue last hash with hash of c
-> pop hash + continue with it the last hash
-> pop hash => global hash
