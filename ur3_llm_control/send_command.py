""" ros2 run ur3_llm_control send_command "Dua khoi mau do vao vung B."
"""
import sys
import time

import rclpy
from std_msgs.msg import String


def main():
    args = rclpy.utilities.remove_ros_args(sys.argv)[1:]
    if not args:
        print('ros2 run ur3_llm_control send_command "<cau lenh>"')
        return 1
    rclpy.init()
    nd = rclpy.create_node('send_command')
    pub = nd.create_publisher(String, '/llm_robot/command', 10)
    t = time.time()
    while pub.get_subscription_count() == 0 and time.time() - t < 5:   # cho node nhan
        rclpy.spin_once(nd, timeout_sec=0.1)
    pub.publish(String(data=' '.join(args)))
    rclpy.spin_once(nd, timeout_sec=0.3)
    nd.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
