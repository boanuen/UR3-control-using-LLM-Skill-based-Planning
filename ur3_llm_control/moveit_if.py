"""Giao tiep voi MoveIt 2 (move_group) qua cac action/service:
  /move_action            (MoveGroup)          lap ke hoach + thuc thi, co check va cham, joint limit
  /compute_ik             (GetPositionIK)      tinh goc khop cho vi tri tool0 (seed = home)
  /compute_cartesian_path (GetCartesianPath)   di thang len / xuong
  /execute_trajectory     (ExecuteTrajectory)  chay quy dao Cartesian
  /apply_planning_scene   (ApplyPlanningScene) them ban, khoi, gan/nha khoi vao tool
Gazebo:
  /gazebo/set_entity_state: gripper ao - khoi dang cam duoc dat theo vi tri tool0
"""
import math
import threading
import time

from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Pose
from moveit_msgs.action import ExecuteTrajectory, MoveGroup
from moveit_msgs.msg import (AttachedCollisionObject, CollisionObject, Constraints,
                             JointConstraint, MoveItErrorCodes, PlanningScene)
from moveit_msgs.srv import ApplyPlanningScene, GetCartesianPath, GetPositionIK
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.time import Time
from shape_msgs.msg import SolidPrimitive
import tf2_ros

try:                           
    from gazebo_msgs.msg import EntityState
    from gazebo_msgs.srv import SetEntityState
except ImportError:
    SetEntityState = None

JOINTS = ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
          'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint']


def mk_pose(p, q=(0.0, 0.0, 0.0, 1.0)):
    m = Pose()
    m.position.x, m.position.y, m.position.z = [float(v) for v in p]
    m.orientation.x, m.orientation.y, m.orientation.z, m.orientation.w = [float(v) for v in q]
    return m


def mk_box(name, size, p, q=(0, 0, 0, 1), frame='world'):
    b = SolidPrimitive()
    b.type = SolidPrimitive.BOX
    b.dimensions = [float(s) for s in size]
    co = CollisionObject()
    co.header.frame_id = frame
    co.id = name
    co.pose = mk_pose(p, q)
    co.primitives = [b]
    co.primitive_poses = [mk_pose((0, 0, 0))]
    co.operation = CollisionObject.ADD
    return co


def wait(fut, t):
    """Doi future xong (node duoc spin o thread khac)."""
    end = time.time() + t
    while not fut.done():
        if time.time() > end:
            return None
        time.sleep(0.01)
    return fut.result()


class MoveIt:
    def __init__(self, node, sc):
        self.nd = node
        self.sc = sc
        cb = ReentrantCallbackGroup()      # cho phep cac callback chay song song
        self.mv = ActionClient(node, MoveGroup, '/move_action', callback_group=cb)
        self.ex = ActionClient(node, ExecuteTrajectory, '/execute_trajectory', callback_group=cb)
        self.cart = node.create_client(GetCartesianPath, '/compute_cartesian_path',
                                       callback_group=cb)
        self.ps = node.create_client(ApplyPlanningScene, '/apply_planning_scene',
                                     callback_group=cb)
        self.ikc = node.create_client(GetPositionIK, '/compute_ik', callback_group=cb)
        self.yaw0 = None
        # action server cua controller (chi dung de biet controller da bat chua)
        self.jtc = ActionClient(node, FollowJointTrajectory,
                                '/joint_trajectory_controller/follow_joint_trajectory',
                                callback_group=cb)
        self.gz = None
        if SetEntityState:
            self.gz = node.create_client(SetEntityState, '/gazebo/set_entity_state',
                                         callback_group=cb)
        self.tfb = tf2_ros.Buffer()
        self.tfl = tf2_ros.TransformListener(self.tfb, node)
        self.held = None
        self.lock = threading.Lock()
        self.d = sc.gap + sc.cube / 2      # tu tool0 toi tam khoi
        node.create_timer(0.05, self.follow, callback_group=cb)

    def wait_ready(self, t=180.0):
        end = time.time() + t
        while time.time() < end:
            if (self.mv.server_is_ready() and self.ex.server_is_ready()
                    and self.cart.service_is_ready() and self.ps.service_is_ready()
                    and self.ikc.service_is_ready()
                    and self.jtc.server_is_ready() and self.tool() is not None):
                time.sleep(2.0)            # cho move_group nhan ra controller
                return True
            time.sleep(0.5)
        return False

    def tool(self):
        """Vi tri + huong cua tool0 trong frame world (TF)."""
        try:
            t = self.tfb.lookup_transform(self.sc.frame, self.sc.ee, Time(),
                                          timeout=Duration(seconds=0.5))
        except Exception:
            return None
        a, r = t.transform.translation, t.transform.rotation
        return (a.x, a.y, a.z), (r.x, r.y, r.z, r.w)

    def apply(self, ps):
        ps.is_diff = True
        ps.robot_state.is_diff = True
        req = ApplyPlanningScene.Request()
        req.scene = ps
        res = wait(self.ps.call_async(req), 10.0)
        return res is not None and res.success

    def setup_scene(self):
        """Them ban + 3 khoi vao planning scene cua MoveIt, dua khoi trong Gazebo ve cho cu.
        Khong them san nha: URDF cua UR (sim_gazebo) da co link ground_plane, them nua se
        bi MoveIt bao robot luon va cham."""
        sc = self.sc
        ps = PlanningScene()                # bo cac khoi con dinh o tool tu lan chay truoc
        for o in sc.objs:
            a = AttachedCollisionObject()
            a.link_name = sc.ee
            a.object.id = o
            a.object.operation = CollisionObject.REMOVE
            ps.robot_state.attached_collision_objects.append(a)
        self.apply(ps)

        tb, h, c = sc.tb, sc.tb['h'], sc.cube
        ps = PlanningScene()
        ps.world.collision_objects.append(mk_box('table', (tb['sx'], tb['sy'], h),
                                                 (tb['x'], tb['y'], h / 2), frame=sc.frame))
        for o, (x, y) in sc.pos.items():
            ps.world.collision_objects.append(mk_box(o, (c, c, c), (x, y, sc.z_cube),
                                                     frame=sc.frame))
            self.gz_set(o, (x, y, sc.z_cube), (0, 0, 0, 1), True)
        return self.apply(ps)

    # gripper ao
    def gz_set(self, name, p, q, block=False):
        if not self.gz or not self.gz.service_is_ready():
            return
        req = SetEntityState.Request()
        req.state = EntityState()
        req.state.name = name
        req.state.pose = mk_pose(p, q)
        req.state.reference_frame = 'world'
        f = self.gz.call_async(req)
        if block:
            wait(f, 2.0)

    def cube_from_tool(self):
        t = self.tool()
        if t is None:
            return None
        (px, py, pz), (x, y, z, w) = t
        # truc z cua tool0 trong world (cot 3 cua ma tran quay)
        zx, zy, zz = 2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)
        d = self.d
        # huong khoi = huong tool quay them 180 do quanh x (de khoi dung thang)
        return (px + zx * d, py + zy * d, pz + zz * d), (w, z, -y, -x)

    def follow(self):
        """Timer 20Hz: khoi dang cam di theo tool0."""
        with self.lock:
            o = self.held
        if o is None:
            return
        c = self.cube_from_tool()
        if c:
            self.gz_set(o, c[0], c[1])

    # chuyen dong
    def send(self, goal_c):
        g = MoveGroup.Goal()
        r = g.request
        r.group_name = self.sc.group
        r.num_planning_attempts = 10
        r.allowed_planning_time = 5.0
        r.max_velocity_scaling_factor = float(self.sc.vel)
        r.max_acceleration_scaling_factor = float(self.sc.vel)
        r.start_state.is_diff = True
        r.goal_constraints = [goal_c]
        g.planning_options.plan_only = False
        g.planning_options.replan = True
        g.planning_options.replan_attempts = 2
        g.planning_options.planning_scene_diff.is_diff = True
        g.planning_options.planning_scene_diff.robot_state.is_diff = True
        st = 'PLANNING_FAILED'
        for _ in range(2):                 # loi thi lap ke hoach + chay lai 1 lan
            h = wait(self.mv.send_goal_async(g), 10.0)
            if h is None or not h.accepted:
                continue
            res = wait(h.get_result_async(), 120.0)
            if res is None:
                st = 'FAILED'
                continue
            if res.result.error_code.val == MoveItErrorCodes.SUCCESS:
                return 'SUCCESS'
            time.sleep(1.0)
        return st

    def move_q(self, q):
        c = Constraints()
        for n, v in zip(JOINTS, q):
            j = JointConstraint()
            j.joint_name = n
            j.position = float(v)
            j.tolerance_above = j.tolerance_below = 0.01
            j.weight = 1.0
            c.joint_constraints.append(j)
        return self.send(c)

    def ik(self, p):
        """IK cua MoveIt (/compute_ik): tool0 tai p, huong xuong.
        Seed = tu home -> luon ra tu 'gan home', robot khong bi xoan khop."""
        if self.yaw0 is None:          # goc xoay cua tool luc o home (tool huong xuong:
            t = self.tool()            # q = (cos(yaw/2), sin(yaw/2), 0, 0))
            self.yaw0 = 2 * math.atan2(t[1][1], t[1][0]) if t else 0.0
        q = (math.cos(self.yaw0 / 2), math.sin(self.yaw0 / 2), 0.0, 0.0)
        req = GetPositionIK.Request()
        r = req.ik_request
        r.group_name = self.sc.group
        r.ik_link_name = self.sc.ee
        r.avoid_collisions = True
        r.timeout = Duration(seconds=1.0).to_msg()
        r.robot_state.joint_state.name = JOINTS
        r.robot_state.joint_state.position = [float(v) for v in self.sc.home_q]
        r.pose_stamped.header.frame_id = self.sc.frame
        r.pose_stamped.pose = mk_pose(p, q)
        res = wait(self.ikc.call_async(req), 5.0)
        if res is None or res.error_code.val != MoveItErrorCodes.SUCCESS:
            return None
        d = dict(zip(res.solution.joint_state.name, res.solution.joint_state.position))
        return [d[n] for n in JOINTS]

    def move_xyz(self, p):
        """tool0 toi diem p (tool huong xuong): IK -> goc khop -> MoveIt lap ke hoach."""
        q = self.ik(p)
        if q is None:
            return 'PLANNING_FAILED'
        return self.move_q(q)

    def move_z(self, z):
        t = self.tool()
        if t is None:
            return 'FAILED'
        (x, y, _), q = t
        req = GetCartesianPath.Request()
        req.header.frame_id = self.sc.frame
        req.start_state.is_diff = True
        req.group_name = self.sc.group
        req.link_name = self.sc.ee
        req.waypoints = [mk_pose((x, y, z), q)]
        req.max_step = 0.005
        req.jump_threshold = 0.0
        req.avoid_collisions = True
        res = wait(self.cart.call_async(req), 15.0)
        if res is None or res.fraction < 0.98:
            return 'PLANNING_FAILED'
        g = ExecuteTrajectory.Goal()
        g.trajectory = res.solution
        h = wait(self.ex.send_goal_async(g), 10.0)
        if h is None or not h.accepted:
            return 'FAILED'
        r = wait(h.get_result_async(), 60.0)
        if r is None or r.result.error_code.val != MoveItErrorCodes.SUCCESS:
            return 'FAILED'
        return 'SUCCESS'

    def attach(self, o):
        """Kep: xoa khoi khoi world, gan vao tool0 (MoveIt se tinh ca khoi khi check va cham).
        Hop va cham nho hon khoi that 1 chut (shrink) vi luc nhac len khoi van cham mat ban."""
        ps = PlanningScene()
        rm = CollisionObject()
        rm.header.frame_id = self.sc.frame
        rm.id = o
        rm.operation = CollisionObject.REMOVE
        ps.world.collision_objects = [rm]
        if not self.apply(ps):
            return 'FAILED'
        s = self.sc.cube - self.sc.shrink
        a = AttachedCollisionObject()
        a.link_name = self.sc.ee
        a.object = mk_box(o, (s, s, s), (0, 0, self.d), frame=self.sc.ee)
        a.touch_links = [self.sc.ee, 'wrist_3_link', 'flange']
        ps = PlanningScene()
        ps.robot_state.attached_collision_objects = [a]
        if not self.apply(ps):
            return 'FAILED'
        with self.lock:
            self.held = o
        return 'SUCCESS'

    def detach(self, o, p):
        """Tha: bo khoi khoi tool0, dat lai vao world tai p."""
        q = (0.0, 0.0, 0.0, 1.0)
        c = self.cube_from_tool()
        if c:                           # giu goc xoay quanh truc z cua khoi
            x, y, z, w = c[1]
            yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
            q = (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
        with self.lock:
            self.held = None
        a = AttachedCollisionObject()
        a.link_name = self.sc.ee
        a.object.id = o
        a.object.operation = CollisionObject.REMOVE
        ps = PlanningScene()
        ps.robot_state.attached_collision_objects = [a]
        if not self.apply(ps):
            return 'FAILED'
        c = self.sc.cube
        ps = PlanningScene()
        ps.world.collision_objects = [mk_box(o, (c, c, c), p, q, self.sc.frame)]
        if not self.apply(ps):
            return 'FAILED'
        self.gz_set(o, p, q, True)
        return 'SUCCESS'
