"""Small bounded Android binary-XML edits; indices and resource IDs stay unchanged."""
import struct


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def chunks(data):
    offset = u16(data, 2)
    while offset < len(data):
        size = u32(data, offset + 4)
        if size < 8 or offset + size > len(data):
            raise ValueError("Malformed Android XML chunk")
        yield u16(data, offset), data[offset:offset + size]
        offset += size
    if offset != len(data):
        raise ValueError("Malformed Android XML size")


def read_length(data, offset, utf8):
    if utf8:
        value = data[offset]
        return (((value & 127) << 8) | data[offset + 1], offset + 2) if value & 128 else (value, offset + 1)
    value = u16(data, offset)
    return (((value & 32767) << 16) | u16(data, offset + 2), offset + 4) if value & 32768 else (value, offset + 2)


def write_length(length, utf8):
    if utf8:
        if length > 32767:
            raise ValueError("UTF-8 XML string is too long")
        return bytes([128 | (length >> 8), length & 255]) if length > 127 else bytes([length])
    return struct.pack("<HH", 32768 | (length >> 16), length & 65535) if length > 32767 else struct.pack("<H", length)


def read_pool(chunk):
    count, styles, flags, start, style_start = struct.unpack_from("<5I", chunk, 8)
    utf8 = bool(flags & 256)
    values = []
    for index in range(count):
        offset = start + u32(chunk, u16(chunk, 2) + 4 * index)
        length, offset = read_length(chunk, offset, utf8)
        if utf8:
            length, offset = read_length(chunk, offset, True)
            values.append(chunk[offset:offset + length].decode("utf-8"))
        else:
            values.append(chunk[offset:offset + length * 2].decode("utf-16le"))
    return values


def write_pool(original, values):
    header_size = u16(original, 2)
    count, styles, flags, old_start, old_style_start = struct.unpack_from("<5I", original, 8)
    if len(values) != count:
        raise ValueError("String indices must be preserved")
    utf8 = bool(flags & 256)
    offsets, encoded = [], bytearray()
    for value in values:
        offsets.append(len(encoded))
        utf16 = value.encode("utf-16le")
        encoded.extend(write_length(len(utf16) // 2, utf8))
        if utf8:
            raw = value.encode("utf-8")
            encoded.extend(write_length(len(raw), True))
            encoded.extend(raw + b"\0")
        else:
            encoded.extend(utf16 + b"\0\0")
    while len(encoded) % 4:
        encoded.append(0)
    style_offsets = original[header_size + count * 4:header_size + (count + styles) * 4]
    style_data = original[old_style_start:] if styles else b""
    start = header_size + (count + styles) * 4
    style_start = start + len(encoded) if styles else 0
    header = bytearray(original[:header_size])
    struct.pack_into("<5I", header, 8, count, styles, flags & ~1, start, style_start)
    result = header + b"".join(struct.pack("<I", offset) for offset in offsets) + style_offsets + encoded + style_data
    struct.pack_into("<I", result, 4, len(result))
    return bytes(result)


def patch_manifest(data, replacements, remove_permissions, *, min_sdk=26):
    if u16(data, 0) != 3 or u32(data, 4) != len(data):
        raise ValueError("Expected a complete binary Android manifest")
    entries = list(chunks(data))
    pools = [chunk for kind, chunk in entries if kind == 1]
    if len(pools) != 1:
        raise ValueError("Expected exactly one manifest string pool")
    strings = read_pool(pools[0])
    for old in replacements:
        if strings.count(old) != 1:
            raise ValueError(f"Missing or ambiguous manifest string: {old}")
    modified = [replacements.get(value, value) for value in strings]
    output, removed, skip_depth = [], set(), 0
    for kind, original in entries:
        if kind == 1:
            output.append(write_pool(original, modified))
            continue
        if skip_depth:
            if kind == 0x102:
                skip_depth += 1
            elif kind == 0x103:
                skip_depth -= 1
            continue
        chunk = bytearray(original)
        if kind == 0x102:
            element = strings[u32(chunk, 20)]
            attribute_start, attribute_size, attribute_count = struct.unpack_from("<3H", chunk, 24)
            attributes = {}
            for index in range(attribute_count):
                offset = 16 + attribute_start + index * attribute_size
                attributes[strings[u32(chunk, offset + 4)]] = offset
            if element == "uses-permission" and "name" in attributes:
                offset = attributes["name"]
                name_index = u32(chunk, offset + 16)
                if strings[name_index] in remove_permissions:
                    removed.add(strings[name_index])
                    skip_depth = 1
                    continue
            if element == "application" and "debuggable" in attributes:
                offset = attributes["debuggable"]
                struct.pack_into("<I", chunk, offset + 8, 0xffffffff)
                chunk[offset + 15] = 0x12
                struct.pack_into("<I", chunk, offset + 16, 0)
            if element == "uses-sdk" and "minSdkVersion" in attributes and min_sdk is not None:
                offset = attributes["minSdkVersion"]
                struct.pack_into("<I", chunk, offset + 8, 0xffffffff)
                chunk[offset + 15] = 0x10
                struct.pack_into("<I", chunk, offset + 16, min_sdk)
        output.append(bytes(chunk))
    if skip_depth:
        raise ValueError("Unclosed manifest element")
    header = bytearray(data[:u16(data, 2)])
    result = header + b"".join(output)
    struct.pack_into("<I", result, 4, len(result))
    return bytes(result), sorted(removed)
