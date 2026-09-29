"""Robot Skills. Moi skill la chuoi chuyen dong MoveIt 2 co dinh, tra ve trang thai.

rb la lop giao tiep MoveIt (moveit_if.MoveIt) hoac robot gia (fake_robot.Fake), co cac ham:
  move_q(q)      : di chuyen toi 6 goc khop (MoveIt lap ke hoach)
  move_xyz(p)    : dua tool0 toi diem p, tool huong xuong
  move_z(z)      : di thang dung toi do cao z (Cartesian path)
  attach(o) / detach(o, p) : "kep" / "tha" vat (gripper ao)
"""
OK = 'SUCCESS'


class Skills:
    def __init__(self, sc, rb):
        self.sc = sc
        self.rb = rb

    def home(self):
        return self.rb.move_q(self.sc.home_q)

    def move_above(self, obj):
        if obj not in self.sc.objs:
            return 'INVALID_OBJECT'
        if obj == self.sc.held:
            return 'FAILED'
        x, y = self.sc.pos[obj]
        return self.rb.move_xyz((x, y, self.sc.z_up))

    def move_to_zone(self, zone, tmp=False):
        if zone not in self.sc.zones and not (tmp and zone in self.sc.tmp):
            return 'INVALID_ZONE'
        x, y = self.sc.xy(zone)
        return self.rb.move_xyz((x, y, self.sc.z_up))

    def close_gripper(self, obj):
        st = self.rb.attach(obj)
        if st == OK:
            self.sc.held = obj
        return st

    def open_gripper(self, obj, zone):
        x, y = self.sc.xy(zone)
        st = self.rb.detach(obj, (x, y, self.sc.z_cube))
        if st == OK:
            self.sc.pos[obj] = (x, y)
            self.sc.held = None
        return st

    def pick(self, obj):
        if obj not in self.sc.objs:
            return 'INVALID_OBJECT'
        if self.sc.held:
            return 'FAILED'            # dang cam vat khac
        acts = [lambda: self.move_above(obj),
                lambda: self.rb.move_z(self.sc.z_grasp),   # ha xuong
                lambda: self.close_gripper(obj),
                lambda: self.rb.move_z(self.sc.z_up)]      # nhac len
        for a in acts:
            st = a()
            if st != OK:
                return st
        return OK

    def place(self, obj, zone, tmp=False):
        if obj not in self.sc.objs:
            return 'INVALID_OBJECT'
        if zone not in self.sc.zones and not (tmp and zone in self.sc.tmp):
            return 'INVALID_ZONE'
        if self.sc.held != obj:
            return 'FAILED'            # khong cam dung vat
        if self.sc.who(zone, skip=obj):
            return 'FAILED'            # zone dang co vat khac
        acts = [lambda: self.move_to_zone(zone, tmp),
                lambda: self.rb.move_z(self.sc.z_place),
                lambda: self.open_gripper(obj, zone),
                lambda: self.rb.move_z(self.sc.z_up)]
        for a in acts:
            st = a()
            if st != OK:
                return st
        return OK
