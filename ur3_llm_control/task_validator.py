"""Plan Validator: kiem tra plan cua LLM truoc khi cho robot chay.

1. Dung dinh dang {"plan": [...]}
2. Skill nam trong danh sach cho phep, dung tham so (khong co joint, trajectory...)
3. Object / zone ton tai
4. Logic: khong pick khi dang cam vat, chi place vat dang cam, ket thuc tay phai trong
"""

# Danh sach skill LLM duoc dung: ten -> tham so
SKILLS = {
    'home': [],
    'pick': ['object'],
    'place': ['object', 'zone'],
    'move_above': ['object'],
    'move_to_zone': ['zone'],
}

MAX_STEPS = 20


def to_str(s):
    """{'skill': 'place', 'object': 'red_cube', 'zone': 'zone_b'} -> place(red_cube, zone_b)"""
    args = [str(s.get(k)) for k in SKILLS.get(s.get('skill'), [])]
    return f"{s.get('skill')}({', '.join(args)})"


def clean(v):
    return str(v).strip().lower().replace(' ', '_').replace('-', '_')


def check(raw, sc):
    """Tra ve (plan, errs). errs rong = hop le."""
    if not isinstance(raw, dict) or not isinstance(raw.get('plan'), list):
        return [], ['output phai co dang {"plan": [...]}']
    steps = raw['plan']
    if not steps:
        return [], ['LLM tu choi: ' + str(raw.get('error', 'plan rong'))]
    if len(steps) > MAX_STEPS:
        return [], [f'plan qua dai ({len(steps)} buoc)']

    plan, errs = [], []
    for i, st in enumerate(steps, 1):
        if not isinstance(st, dict):
            errs.append(f'buoc {i}: khong phai object JSON')
            continue
        sk = clean(st.get('skill', ''))
        if sk not in SKILLS:
            errs.append(f'buoc {i}: skill "{sk}" khong duoc phep')
            continue
        keys = SKILLS[sk]
        extra = [k for k in st if k != 'skill' and k not in keys]
        if extra:
            # vd LLM sinh "joints", "trajectory" -> tu choi
            errs.append(f'buoc {i}: tham so khong hop le {extra} cho {sk}')
            continue
        s = {'skill': sk}
        for k in keys:
            s[k] = clean(st.get(k, ''))
        if 'object' in s and s['object'] not in sc.objs:
            errs.append(f'buoc {i}: INVALID_OBJECT "{s["object"]}"')
            continue
        if 'zone' in s and s['zone'] not in sc.zones:
            errs.append(f'buoc {i}: INVALID_ZONE "{s["zone"]}"')
            continue
        plan.append(s)
    if errs:
        return plan, errs

    # chay thu logic tay gap
    held = sc.held
    for i, s in enumerate(plan, 1):
        sk = s['skill']
        if sk == 'pick':
            if held:
                errs.append(f'buoc {i}: pick({s["object"]}) khi dang cam {held}')
            held = s['object']
        elif sk == 'place':
            if held != s['object']:
                errs.append(f'buoc {i}: place({s["object"]}) nhung dang cam {held}')
            held = None
        elif sk == 'move_above' and s['object'] == held:
            errs.append(f'buoc {i}: move_above({held}) trong khi dang cam no')
    if held:
        errs.append(f'plan ket thuc khi van con cam {held}')

    if not errs and plan[-1]['skill'] != 'home':
        plan.append({'skill': 'home'})    # luon ve home cuoi cung
    return plan, errs
