"""
    ros2 launch ur3_llm_control llm_robot.launch.py
    ros2 run ur3_llm_control send_command "Put the red cube in zone B."
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ur = LaunchConfiguration('ur_type')
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare('ur3_llm_control'), 'launch', 'sim.launch.py'])),
        launch_arguments={'ur_type': ur}.items())
    node = Node(package='ur3_llm_control', executable='llm_robot_node', output='screen',
                emulate_tty=True,
                parameters=[{'use_sim_time': True, 'interactive': False}])
    return LaunchDescription([
        DeclareLaunchArgument('ur_type', default_value='ur3e', choices=['ur3', 'ur3e']),
        sim,
        TimerAction(period=10.0, actions=[node]),  
    ])
