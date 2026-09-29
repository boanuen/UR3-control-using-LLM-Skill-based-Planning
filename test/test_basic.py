"""Test khong can ROS / 9Router:  python3 -m pytest test -q"""
import json
import os

from ur3_llm_control.fake_robot import Fake
from ur3_llm_control.llm_planner import Planner, get_json, make_prompt
from ur3_llm_control.robot_skills import Skills
from ur3_llm_control.scene import Scene
from ur3_llm_control.skill_executor import fix_plan, run_cmd
from ur3_llm_control.student import assign, get_p
from ur3_llm_control.task_validator import check

SCENE = os.path.join(os.path.dirname(__file__), '..', 'config', 'scene.yaml')
CFG = {'base_url': 'x', 'model': 'x', 'tries': 2}


def P(*steps):
    """P(('pick','red_cube'), ('place','red_cube','zone_b'), ('home',)) -> dict plan"""
    out = []
    for s in steps:
        d = {'skill': s[0]}
        if s[0] in ('pick', 'move_above'):
            d['object'] = s[1]
        if s[0] == 'place':
            d['object'], d['zone'] = s[1], s[2]
        if s[0] == 'move_to_zone':
            d['zone'] = s[1]
        out.append(d)
    return {'plan': out}


def fake_llm(*answers):
    """LLM gia: lan luot tra ve cac cau tra loi cho truoc."""
    ans = list(answers)
    return lambda cfg, msgs: ans.pop(0)


# ---------------------------------------------------------------- student
def test_p():
    assert get_p('23020123') == 5
    assert get_p('23020772') == 0
    assert assign('23020123') == {'zone_a': 'blue_cube', 'zone_b': 'yellow_cube',
                                  'zone_c': 'red_cube'}
    assert assign('23020772') == {'zone_a': 'red_cube', 'zone_b': 'yellow_cube',
                                  'zone_c': 'blue_cube'}


def test_prompt_has_everything():
    s = make_prompt(Scene(SCENE), 'A', '23020772')
    for w in ['pick(object)', 'place(object, zone)', 'home()', 'red_cube', 'zone_c',
              'red_cube -> zone_a']:
        assert w in s


# -------------------------------------------------------------- validator
def test_ok_plan_adds_home():
    plan, errs = check(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_b')), Scene(SCENE))
    assert errs == []
    assert plan[-1] == {'skill': 'home'}


def test_bad_skill_object_zone():
    sc = Scene(SCENE)
    assert check({'plan': [{'skill': 'fly'}]}, sc)[1]
    assert 'INVALID_OBJECT' in check(P(('pick', 'green_cube')), sc)[1][0]
    assert 'INVALID_ZONE' in check(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_d')),
                                   sc)[1][0]


def test_reject_joint_commands():
    raw = {'plan': [{'skill': 'home', 'joints': [0, 0, 0, 0, 0, 0]}]}
    assert check(raw, Scene(SCENE))[1]


def test_reject_bad_logic():
    sc = Scene(SCENE)
    assert check(P(('place', 'red_cube', 'zone_a')), sc)[1]                      # chua pick
    assert check(P(('pick', 'red_cube'), ('pick', 'blue_cube')), sc)[1]          # cam 2 vat
    assert check(P(('pick', 'red_cube'), ('home',)), sc)[1]                      # chua tha


def test_get_json():
    assert get_json('```json\n{"plan": []}\n```') == {'plan': []}
    assert get_json('<think>hmm {x}</think> ok {"plan": [1]}') == {'plan': [1]}


# --------------------------------------------------------------- executor
def test_basic_task_success():
    sc = Scene(SCENE)
    sk = Skills(sc, Fake())
    ans = json.dumps(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_b'), ('home',)))
    pl = Planner(CFG, sc, 'A', '23020772', ask_fn=fake_llm(ans))
    rep = run_cmd('Put the red cube in zone B.', pl, sk, log=lambda s: None)
    assert rep['status'] == 'TASK SUCCESS'
    assert sc.where('red_cube') == 'zone_b'


def test_llm_retry_after_reject():
    sc = Scene(SCENE)
    bad = json.dumps(P(('pick', 'purple_cube')))
    good = json.dumps(P(('pick', 'blue_cube'), ('place', 'blue_cube', 'zone_c')))
    pl = Planner(CFG, sc, 'A', '23020772', ask_fn=fake_llm(bad, good))
    plan, errs, _ = pl.plan('Move the blue cube to zone C.')
    assert errs == [] and plan[0]['object'] == 'blue_cube'


def test_rejected_plan_not_executed():
    sc = Scene(SCENE)
    rb = Fake()
    ans = json.dumps({'plan': [], 'error': 'no green cube'})
    pl = Planner(CFG, sc, 'A', '23020772', ask_fn=fake_llm(ans))
    rep = run_cmd('Move the green cube', pl, Skills(sc, rb), log=lambda s: None)
    assert rep['status'] == 'TASK REJECTED'
    assert rb.log == []                       # robot khong nhuc nhich


def test_arrange_by_student_id():
    sc = Scene(SCENE)
    sk = Skills(sc, Fake())
    steps = []
    for z, o in assign('23020772').items():
        steps += [('pick', o), ('place', o, z)]
    pl = Planner(CFG, sc, 'A', '23020772', ask_fn=fake_llm(json.dumps(P(*steps, ('home',)))))
    rep = run_cmd('Arrange all objects according to my student ID.', pl, sk, log=lambda s: None)
    assert rep['status'] == 'TASK SUCCESS'
    assert sc.state() == {'red_cube': 'zone_a', 'yellow_cube': 'zone_b', 'blue_cube': 'zone_c'}


def test_occupied_zone_uses_tmp():
    sc = Scene(SCENE)
    sc.pos['red_cube'] = sc.xy('zone_a')
    sc.pos['blue_cube'] = sc.xy('zone_b')
    # doi cho 2 khoi -> phai dung vung tam
    plan, _ = check(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_b'),
                      ('pick', 'blue_cube'), ('place', 'blue_cube', 'zone_a')), sc)
    steps = fix_plan(plan, sc)
    assert steps[0] == {'skill': 'pick', 'object': 'blue_cube', 'note': 'auto'}
    assert steps[1]['zone'] == 'tmp_1'
    from ur3_llm_control.skill_executor import run
    ok, _ = run(steps, Skills(sc, Fake()), log=lambda s: None)
    assert ok
    assert sc.where('red_cube') == 'zone_b' and sc.where('blue_cube') == 'zone_a'


def test_skip_when_already_there():
    sc = Scene(SCENE)
    sc.pos['red_cube'] = sc.xy('zone_a')
    plan, _ = check(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_a')), sc)
    steps = fix_plan(plan, sc)
    assert steps[0]['note'] == 'skip' and steps[1]['note'] == 'skip'


def test_planning_failed_stops():
    sc = Scene(SCENE)
    ans = json.dumps(P(('pick', 'red_cube'), ('place', 'red_cube', 'zone_b')))
    pl = Planner(CFG, sc, 'A', '23020772', ask_fn=fake_llm(ans))
    rep = run_cmd('x', pl, Skills(sc, Fake(fail=True)), log=lambda s: None)
    assert rep['status'] == 'TASK FAILED'
    assert rep['steps'][0][1] == 'PLANNING_FAILED'
    assert rep['steps'][1][1] == 'NOT RUN'


def test_fix_text_removes_broken_utf8():
    from ur3_llm_control.skill_executor import fix_text
    bad = 'l\udce1\udcba\udca5y khối màu vàng'     # "ấ" = 3 byte E1 BA A5 bi tach loi
    assert fix_text(bad) == 'lấy khối màu vàng'
    assert fix_text('x\udce1') == 'x'                       # byte le -> bo di
