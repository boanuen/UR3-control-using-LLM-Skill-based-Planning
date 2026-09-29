"""LLM Planner: cau lenh ngon ngu tu nhien -> JSON plan (qua 9Router).

LLM chi duoc chon va sap xep skill, khong bao gio sinh goc khop / quy dao.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

from .scene import cfg_path
from .student import assign, get_p
from .task_validator import SKILLS, check


def make_prompt(sc, name, sid):
    """Doc mau prompt config/prompt.txt roi dien skill, object, zone, MSSV vao."""
    with open(cfg_path('prompt.txt'), encoding='utf-8') as f:
        tpl = f.read()
    return tpl.format(
        skills='\n'.join(f"  {k}({', '.join(v)})" for k, v in SKILLS.items()),
        objects='\n'.join(f'  {o}' for o in sc.objs),
        zones='\n'.join(f'  {z}   ("Zone {z[-1].upper()}")' for z in sc.zones),
        name=name, sid=sid, p=get_p(sid),
        assign='\n'.join(f'  {o} -> {z}' for z, o in assign(sid).items()))


def ask_one(url, key, model, msgs):
    body = {'model': model, 'messages': msgs, 'temperature': 0}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        return data['choices'][0]['message']['content'] or ''
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode(errors="replace")[:200]}')
    except Exception as e:
        raise RuntimeError(str(e))


def ask(cfg, msgs):
    """Goi 9Router (API kieu OpenAI), tra ve text tra loi.
    Model free hay loi tam thoi -> thu lai 3 lan, roi doi sang backup_model (neu co)."""
    url = cfg['base_url'].rstrip('/') + '/chat/completions'
    key = os.environ.get('NINE_KEY') or cfg.get('api_key', '')
    models = [cfg['model']] + ([cfg['backup_model']] if cfg.get('backup_model') else [])
    err = ''
    for m in models:
        for _ in range(3):
            try:
                return ask_one(url, key, m, msgs)
            except RuntimeError as e:
                err = f'{m}: {e}'
                print(f'  [LLM] loi {err} -> thu lai', flush=True)
                time.sleep(2)
    raise RuntimeError(f'loi goi 9Router ({url}): {err}')


def get_json(txt):
    """Lay object JSON dau tien trong cau tra loi (bo qua ```json va <think>)."""
    txt = re.sub(r'<think>.*?</think>', '', txt, flags=re.S)
    i = txt.find('{')
    if i < 0:
        raise ValueError('khong co JSON')
    obj, _ = json.JSONDecoder().raw_decode(txt[i:])
    return obj


class Planner:
    def __init__(self, cfg, sc, name, sid, ask_fn=ask):
        self.cfg = cfg
        self.sc = sc
        self.sys = make_prompt(sc, name, sid)
        self.ask = ask_fn          # doi duoc de test khong can mang

    def plan(self, cmd):
        """Tra ve (plan, errs, cau tra loi goc cua LLM)."""
        st = ', '.join(f'{o}: {w}' for o, w in self.sc.state().items())
        msgs = [{'role': 'system', 'content': self.sys},
                {'role': 'user', 'content': f'Current state: {st}.\nCommand: {cmd}'}]
        plan, errs, ans = [], [], ''
        for _ in range(int(self.cfg.get('tries', 2))):
            ans = self.ask(self.cfg, msgs)
            try:
                raw = get_json(ans)
            except ValueError as e:
                raw, errs = None, [f'LLM tra ve khong phai JSON: {e}']
            if raw is not None:
                plan, errs = check(raw, self.sc)
            if not errs:
                return plan, [], ans
            if isinstance(raw, dict) and raw.get('plan') == []:
                break              # LLM tu choi -> khong hoi lai
            # bao loi cho LLM va hoi lai
            msgs.append({'role': 'assistant', 'content': ans})
            msgs.append({'role': 'user', 'content':
                         'Your plan was rejected: ' + '; '.join(errs) +
                         '. Return a corrected JSON plan. Do not change the object or zone '
                         'the user asked for; if impossible return {"plan": [], "error": "..."}.'})
        return plan, errs, ans
