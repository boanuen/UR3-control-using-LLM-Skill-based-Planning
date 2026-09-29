""" ros2 launch ur3_llm_control sim.launch.py
    ros2 launch ur3_llm_control sim.launch.py ur_type:=ur3 gazebo_gui:=false

Giong ur_simulation_gazebo/ur_sim_moveit.launch.py nhung dung world rieng
"""
import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction,
                            RegisterEventHandler)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

from ur3_llm_control.scene import Scene
from ur3_llm_control.world_gen import make_world


def setup(context):
    ur = LaunchConfiguration('ur_type')
    share = get_package_share_directory('ur3_llm_control')

    # 1. sinh file world
    world = os.path.join(tempfile.gettempdir(), 'ur3_llm.world')
    with open(world, 'w') as f:
        f.write(make_world(Scene(os.path.join(share, 'config', 'scene.yaml'))))

    # 2. mo ta robot (xacro)
    ctrl = PathJoinSubstitution([FindPackageShare('ur_simulation_gazebo'), 'config',
                                 'ur_controllers.yaml'])
    init = PathJoinSubstitution([FindPackageShare('ur_description'), 'config',
                                 'initial_positions.yaml'])
    urdf = Command([
        PathJoinSubstitution([FindExecutable(name='xacro')]), ' ',
        PathJoinSubstitution([FindPackageShare('ur_description'), 'urdf', 'ur.urdf.xacro']),
        ' safety_limits:=true safety_pos_margin:=0.15 safety_k_position:=20',
        ' name:=ur ur_type:=', ur, ' prefix:=""',
        ' sim_gazebo:=true simulation_controllers:=', ctrl,
        ' initial_positions_file:=', init,
    ])
    desc = {'robot_description': ParameterValue(urdf, value_type=str)}

    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher',
               output='both', parameters=[{'use_sim_time': True}, desc])
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([FindPackageShare('gazebo_ros'), '/launch/gazebo.launch.py']),
        launch_arguments={'gui': LaunchConfiguration('gazebo_gui'), 'world': world}.items())
    # timeout 120s: tren WSL gzserver co luc khoi dong ~30s 
    spawn = Node(package='gazebo_ros', executable='spawn_entity.py',
                 arguments=['-entity', 'ur', '-topic', 'robot_description', '-timeout', '120'],
                 output='screen')

    # 3. controller: joint_state_broadcaster roi den joint_trajectory_controller
    jsb = Node(package='controller_manager', executable='spawner',
               arguments=['joint_state_broadcaster', '-c', '/controller_manager'])
    jtc = Node(package='controller_manager', executable='spawner',
               arguments=['joint_trajectory_controller', '-c', '/controller_manager'])
    jtc_after = RegisterEventHandler(OnProcessExit(target_action=jsb, on_exit=[jtc]))

    # 4. MoveIt 2 (use_sim_time:=true -> ur_moveit dung joint_trajectory_controller)
    moveit = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([FindPackageShare('ur_moveit_config'),
                                       '/launch/ur_moveit.launch.py']),
        launch_arguments={'ur_type': ur, 'safety_limits': 'true', 'prefix': '""',
                          'description_package': 'ur_description',
                          'description_file': 'ur.urdf.xacro',
                          'moveit_config_package': 'ur_moveit_config',
                          'moveit_config_file': 'ur.srdf.xacro',
                          'use_sim_time': 'true', 'launch_servo': 'false',
                          'launch_rviz': LaunchConfiguration('launch_rviz')}.items())

    return [gazebo, rsp, spawn, jsb, jtc_after, moveit]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('ur_type', default_value='ur3e', choices=['ur3', 'ur3e']),
        DeclareLaunchArgument('gazebo_gui', default_value='true'),
        DeclareLaunchArgument('launch_rviz', default_value='true'),
        OpaqueFunction(function=setup),
    ])
