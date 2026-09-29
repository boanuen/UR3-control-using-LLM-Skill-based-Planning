"""Thu phan LLM khong can ROS (9Router that + robot gia).

    python3 -m ur3_llm_control.offline_cli "Move the blue cube to zone C."
    python3 -m ur3_llm_control.offline_cli          # go nhieu lenh
"""
import readline  # noqa: F401  (go/xoa tieng Viet dung trong Command>)
import sys

import yaml

from .fake_robot import Fake
from .llm_planner import Planner
from .robot_skills import Skills
from .scene import Scene, cfg_path
from .skill_executor import run_cmd
from .student import info


def main():
    sc = Scene(cfg_path('scene.yaml'))
    with open(cfg_path('student_config.yaml'), encoding='utf-8') as f:
        st = yaml.safe_load(f)
    sk = Skills(sc, Fake())
    pl = Planner(st['llm'], sc, st['student_name'], st['student_id'])
    print(info(st['student_name'], st['student_id']))

    if len(sys.argv) > 1:
        run_cmd(' '.join(sys.argv[1:]), pl, sk)
        return 0
    while True:
        try:
            cmd = input('\nCommand> ').strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if cmd in ('q', 'quit', 'exit'):
            return 0
        if cmd:
            run_cmd(cmd, pl, sk)


if __name__ == '__main__':
    sys.exit(main())
