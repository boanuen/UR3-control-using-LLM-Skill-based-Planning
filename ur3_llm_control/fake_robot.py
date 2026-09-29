"""Robot gia (khong can ROS/MoveIt) de test LLM + validator + executor tren may bat ky.
Chi kiem tra diem den nam trong tam voi cua UR3 (~0.5 m)."""
import math


class Fake:
    def __init__(self, fail=False):
        self.fail = fail       # True -> moi lenh di chuyen deu PLANNING_FAILED
        self.log = []          # ghi lai cac lenh da goi (dung cho test)
        self.held = None

    def move_q(self, q):
        self.log.append(('move_q',))
        return 'PLANNING_FAILED' if self.fail else 'SUCCESS'

    def move_xyz(self, p):
        self.log.append(('move_xyz', tuple(round(v, 3) for v in p)))
        if self.fail or math.hypot(p[0], p[1]) > 0.5:
            return 'PLANNING_FAILED'
        return 'SUCCESS'

    def move_z(self, z):
        self.log.append(('move_z', round(z, 3)))
        return 'PLANNING_FAILED' if self.fail else 'SUCCESS'

    def attach(self, o):
        self.log.append(('attach', o))
        self.held = o
        return 'SUCCESS'

    def detach(self, o, p):
        self.log.append(('detach', o))
        self.held = None
        return 'SUCCESS'
