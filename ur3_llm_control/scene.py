"""Doc scene.yaml + luu trang thai the gioi"""
import copy
import math
import os

import yaml


def cfg_path(n):
    """Duong dan file trong config: lay trong workspace da build, neu khong trong source."""
    try:
        from ament_index_python.packages import get_package_share_directory
        p = os.path.join(get_package_share_directory('ur3_llm_control'), 'config', n)
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', n)


class Scene:
    def __init__(self, path):
        with open(path, encoding='utf-8') as f:
            d = yaml.safe_load(f)
        self.frame = d['frame']
        self.group = d['group']
        self.ee = d['ee']
        self.tb = d['table']
        self.cube = d['cube']
        self.objs = d['objects']
        self.zones = d['zones']
        self.tmp = d['tmp']
        self.home_q = d['home']
        self.shrink = d['shrink']
        self.vel = d['vel']

        # do cao cua tool0 (tinh tu mat ban)
        h = self.tb['h']
        self.gap = d['gap']
        self.z_cube = h + self.cube / 2                # tam khoi khi nam tren ban
        self.z_grasp = h + self.cube + self.gap        # tool0 khi gap
        self.z_place = self.z_grasp + 0.003            # tool0 khi dat (cao hon 3mm)
        self.z_up = self.z_grasp + d['up']             # tool0 khi o tren vat

        # trang thai
        self.pos = {n: tuple(o['xy']) for n, o in self.objs.items()}
        self.held = None

    def xy(self, slot):
        if slot in self.zones:
            return tuple(self.zones[slot]['xy'])
        return tuple(self.tmp[slot])

    def where(self, obj):
        """Tra ve zone / vung tam ma vat dang nam, None neu khong o dau ca."""
        if obj == self.held:
            return None
        x, y = self.pos[obj]
        for s in list(self.zones) + list(self.tmp):
            sx, sy = self.xy(s)
            if math.hypot(x - sx, y - sy) < 0.02:
                return s
        return None

    def who(self, slot, skip=None):
        """Vat dang chiem slot (tru vat skip)."""
        for o in self.pos:
            if o != skip and self.where(o) == slot:
                return o
        return None

    def free_tmp(self):
        for t in self.tmp:
            if self.who(t) is None:
                return t
        return None

    def state(self):
        out = {}
        for o in self.pos:
            if o == self.held:
                out[o] = 'in gripper'
            else:
                out[o] = self.where(o) or 'start position'
        return out

    def copy(self):
        return copy.deepcopy(self)
