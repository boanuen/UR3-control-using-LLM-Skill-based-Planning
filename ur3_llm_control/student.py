"""Ca nhan hoa: P = (2 so cuoi MSSV) mod 6."""

# P -> mau o Zone A, Zone B, Zone C
TB = {
    0: ('red', 'yellow', 'blue'),
    1: ('red', 'blue', 'yellow'),
    2: ('yellow', 'red', 'blue'),
    3: ('yellow', 'blue', 'red'),
    4: ('blue', 'red', 'yellow'),
    5: ('blue', 'yellow', 'red'),
}


def get_p(sid):
    return int(str(sid)[-2:]) % 6


def assign(sid):
    """{'zone_a': 'red_cube', 'zone_b': ..., 'zone_c': ...}"""
    a, b, c = TB[get_p(sid)]
    return {'zone_a': a + '_cube', 'zone_b': b + '_cube', 'zone_c': c + '_cube'}


def info(name, sid):
    s = f'Student: {name} ({sid})\n'
    s += f'P = {str(sid)[-2:]} mod 6 = {get_p(sid)}\n'
    for z, o in assign(sid).items():
        s += f'  Zone {z[-1].upper()} -> {o}\n'
    return s.rstrip()
