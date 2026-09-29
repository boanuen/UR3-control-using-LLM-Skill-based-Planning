"""Skill Executor: chay plan da duoc validator duyet va in ket qua ra terminal.

Xu ly them (muc nang cao):
- Vat da o dung zone -> bo qua pick/place (SKIPPED)
- Zone dich dang bi vat khac chiem -> tu chen buoc dua vat do sang vung tam (tmp)
"""
import json

from .task_validator import to_str

BAR = '=' * 50


def next_place(plan, i, obj):
    """Tim buoc place(obj, ...) sau buoc pick thu i (truoc lan pick tiep theo)."""
    for j in range(i + 1, len(plan)):
        if plan[j]['skill'] == 'place' and plan[j]['object'] == obj:
            return j
        if plan[j]['skill'] == 'pick':
            return None
    return None


def fix_plan(plan, sc):
    w = sc.copy()          # chay thu tren ban sao trang thai
    out, skip = [], set()
    for i, s in enumerate(plan):
        if i in skip:
            out.append(dict(s, note='skip'))
            continue
        if s['skill'] == 'pick':
            o = s['object']
            j = next_place(plan, i, o)
            if j is not None:
                z = plan[j]['zone']
                if w.where(o) == z:            
                    out.append(dict(s, note='skip'))
                    skip.add(j)
                    continue
                y = w.who(z, skip=o)
                if y:                          # zone bi chiem -> don sang vung tam
                    t = w.free_tmp()
                    if t is None:
                        raise ValueError(f'{z} dang co {y} va het vung tam')
                    out.append({'skill': 'pick', 'object': y, 'note': 'auto'})
                    out.append({'skill': 'place', 'object': y, 'zone': t, 'note': 'auto'})
                    w.pos[y] = w.xy(t)
            w.held = o
        elif s['skill'] == 'place':
            w.pos[s['object']] = w.xy(s['zone'])
            w.held = None
        out.append(dict(s))
    return out


def do_step(s, sk):
    n = s['skill']
    tmp = s.get('note') == 'auto'
    if n == 'home':
        return sk.home()
    if n == 'pick':
        return sk.pick(s['object'])
    if n == 'place':
        return sk.place(s['object'], s['zone'], tmp)
    if n == 'move_above':
        return sk.move_above(s['object'])
    if n == 'move_to_zone':
        return sk.move_to_zone(s['zone'])
    return 'FAILED'


def run(steps, sk, log=print):
    """Tra ve (ok, [(buoc, trang thai)]). loi => dung"""
    ok, res = True, []
    for s in steps:
        lb = to_str(s)
        if s.get('note') == 'auto':
            lb += ' [tmp]'
        if not ok:
            st = 'NOT RUN'
        elif s.get('note') == 'skip':
            st = 'SKIPPED'
        else:
            try:
                st = do_step(s, sk)
            except Exception as e:
                log(f'  loi: {e}')
                st = 'FAILED'
            if st != 'SUCCESS':
                ok = False
        log(f'{lb} {"." * max(2, 32 - len(lb))} {st}')
        res.append((lb, st))
    return ok, res


def fix_text(s):
    """Bo byte loi UTF-8 truoc khi gui LLM."""
    return s.encode('utf-8', 'surrogateescape').decode('utf-8', 'ignore').strip()


def run_cmd(cmd, pl, sk, log=print):
    """Toan bo luong: USER COMMAND -> LLM -> validator -> executor. Tra ve dict ket qua."""
    cmd = fix_text(cmd)
    rep = {'command': cmd, 'plan': [], 'status': 'TASK FAILED'}
    log(BAR)
    log('USER COMMAND:')
    log(cmd)
    log('')
    try:
        plan, errs, ans = pl.plan(cmd)
    except RuntimeError as e:
        log(f'LLM ERROR: {e}')
        rep['status'] = 'TASK REJECTED'
        log(BAR)
        return rep

    if errs:
        log('LLM PLAN: REJECTED')
        for e in errs:
            log('  - ' + e)
        log('  LLM tra loi: ' + ans.strip()[:300])
        log('')
        log('TASK REJECTED')
        rep['status'] = 'TASK REJECTED'
        log(BAR)
        return rep

    rep['plan'] = plan
    log('LLM PLAN:')
    for i, s in enumerate(plan, 1):
        log(f'{i}. {to_str(s)}')
    log('')
    log('JSON: ' + json.dumps({'plan': plan}))
    log('')

    try:
        steps = fix_plan(plan, pl.sc)
    except ValueError as e:
        log(f'KHONG THUC HIEN DUOC: {e}')
        log(BAR)
        return rep

    log('EXECUTION:')
    ok, res = run(steps, sk, log)
    rep['steps'] = res
    rep['status'] = 'TASK SUCCESS' if ok else 'TASK FAILED'
    log('')
    log(rep['status'])
    log('State: ' + ', '.join(f'{o}={w}' for o, w in sk.sc.state().items()))
    log(BAR)
    return rep
