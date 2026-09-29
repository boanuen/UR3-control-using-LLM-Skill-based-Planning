from glob import glob

from setuptools import find_packages, setup

pkg = 'ur3_llm_control'

setup(
    name=pkg,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + pkg]),
        ('share/' + pkg, ['package.xml', 'README.md']),
        ('share/' + pkg + '/launch', glob('launch/*.launch.py')),
        ('share/' + pkg + '/config', glob('config/*.yaml') + ['config/prompt.txt']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nguyen Tran Thu Thao',
    maintainer_email='student@example.com',
    description='Dieu khien UR3/UR3e bang ngon ngu tu nhien (LLM + MoveIt 2)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'llm_robot_node = ur3_llm_control.llm_robot_node:main',
            'send_command = ur3_llm_control.send_command:main',
            'offline_cli = ur3_llm_control.offline_cli:main',
        ],
    },
)
