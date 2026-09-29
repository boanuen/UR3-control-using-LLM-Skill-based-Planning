"""Sinh file world Gazebo (SDF) tu scene.yaml: ban, 3 vung, 2 vung tam, 3 khoi.
Khoi la link kinematic (khong roi), chi di chuyen qua /gazebo/set_entity_state."""


def box(name, p, size, rgba, coll=True, kin=False):
    g = f'<geometry><box><size>{size[0]} {size[1]} {size[2]}</size></box></geometry>'
    c = ' '.join(str(v) for v in rgba)
    return f"""
    <model name="{name}">
      <static>{'false' if kin else 'true'}</static>
      <pose>{p[0]} {p[1]} {p[2]} 0 0 0</pose>
      <link name="link">
        {'<kinematic>true</kinematic><gravity>false</gravity>' if kin else ''}
        {f'<collision name="c">{g}</collision>' if coll else ''}
        <visual name="v">{g}<material><ambient>{c}</ambient><diffuse>{c}</diffuse></material></visual>
      </link>
    </model>"""


def make_world(sc):
    t, h, c = sc.tb, sc.tb['h'], sc.cube
    ms = [box('work_table', (t['x'], t['y'], h / 2), (t['sx'], t['sy'], h), (0.55, 0.4, 0.25, 1))]
    for n, z in sc.zones.items():
        x, y = z['xy']
        ms.append(box(n, (x, y, h + 0.001), (0.09, 0.09, 0.002), z['rgba'], coll=False))
    for n, (x, y) in sc.tmp.items():
        ms.append(box(n, (x, y, h + 0.001), (0.06, 0.06, 0.002), (0.7, 0.7, 0.7, 0.5), coll=False))
    for n, o in sc.objs.items():
        x, y = o['xy']
        # khoi khong co collision trong Gazebo: vi tri do gripper ao dat, neu co collision
        # thi co tay robot cham vao khoi dang cam va bi day lech (controller bao loi)
        ms.append(box(n, (x, y, sc.z_cube), (c, c, c), o['rgba'], coll=False, kin=True))
    return f"""<?xml version="1.0"?>
<sdf version="1.6">
  <world name="ur3_llm_world">
    <include><uri>model://ground_plane</uri></include>
    <include><uri>model://sun</uri></include>
    <plugin name="gazebo_ros_state" filename="libgazebo_ros_state.so">
      <ros><namespace>/gazebo</namespace></ros>
      <update_rate>10.0</update_rate>
    </plugin>
    <gui><camera name="user_camera"><pose>1.2 -0.9 0.9 0 0.45 2.45</pose></camera></gui>
    {''.join(ms)}
  </world>
</sdf>
"""
