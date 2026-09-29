# ur3_llm_control – Điều khiển UR3e bằng ngôn ngữ tự nhiên (LLM + MoveIt 2)

- Sinh viên: **Nguyễn Trần Thu Thảo** – MSSV **23020772**
- Nhiệm vụ cá nhân: P = 72 mod 6 = **0** → Zone A = **red**, Zone B = **yellow**, Zone C = **blue**
- Môi trường: Ubuntu 22.04 (WSL2) · ROS 2 Humble · MoveIt 2 · Gazebo Classic 11 · UR3e · LLM qua 9Router
- Video demo: `<link Google Drive>`

## 1. Kiến trúc

```
Câu lệnh (tiếng Việt / tiếng Anh)
        ↓
LLM Planner        llm_planner.py     prompt (config/prompt.txt) → 9Router → JSON
        ↓
JSON Plan          {"plan": [{"skill": "pick", "object": "red_cube"}, ...]}
        ↓
Plan Validator     task_validator.py  sai → hỏi lại LLM 1 lần → vẫn sai thì từ chối
        ↓
Skill Executor     skill_executor.py  xử lý zone bị chiếm, chạy từng skill, in kết quả
        ↓
Robot Skills       robot_skills.py    home / pick / place / move_above / move_to_zone
        ↓
MoveIt 2           moveit_if.py       IK, lập kế hoạch, tránh va chạm, thực thi
        ↓
UR3e (Gazebo)
```

LLM **chỉ chọn và sắp xếp skill**. LLM không biết tên khớp, góc khớp hay tọa độ:
tọa độ nằm trong `config/scene.yaml`, góc khớp do IK của MoveIt tính, quỹ đạo do OMPL lập.

## 2. Cấu trúc package

```
ur3_llm_control/
├── config/
│   ├── scene.yaml            bàn, 3 khối, 3 zone, 2 vùng tạm, tư thế home
│   ├── student_config.yaml   họ tên, MSSV, cấu hình 9Router (model, model dự phòng)
│   └── prompt.txt            system prompt gửi cho LLM
├── launch/
│   ├── sim.launch.py         Gazebo + UR3e + ros2_control + MoveIt 2 + RViz
│   └── llm_robot.launch.py   sim.launch.py + node LLM (nhận lệnh qua topic)
├── ur3_llm_control/
│   ├── llm_robot_node.py     node ROS 2 chính
│   ├── llm_planner.py        tạo prompt, gọi 9Router, lấy JSON
│   ├── task_validator.py     danh sách skill cho phép + kiểm tra plan
│   ├── skill_executor.py     sửa plan khi zone bị chiếm, chạy plan, in kết quả
│   ├── robot_skills.py       các robot skill
│   ├── moveit_if.py          giao tiếp MoveIt 2 + gripper ảo trong Gazebo
│   ├── scene.py              đọc scene.yaml + trạng thái (khối nào ở đâu, đang cầm gì)
│   ├── student.py            P = XX mod 6 và bảng màu → zone
│   ├── world_gen.py          sinh world Gazebo từ scene.yaml
│   ├── send_command.py       gửi 1 lệnh lên topic /llm_robot/command
│   ├── offline_cli.py        thử LLM không cần Gazebo (robot giả)
│   └── fake_robot.py         robot giả dùng cho test
└── test/test_basic.py        15 unit test (không cần ROS, không cần mạng)
```

## 3. Robot skills

| Skill | Các bước (tất cả qua MoveIt 2) |
|---|---|
| `home()` | về 6 góc khớp home |
| `move_above(object)` | tool0 lên trên khối 12 cm, tool hướng xuống |
| `move_to_zone(zone)` | tool0 lên trên zone 12 cm |
| `pick(object)` | move_above → hạ thẳng xuống → close_gripper → nhấc lên |
| `place(object, zone)` | move_to_zone → hạ xuống → open_gripper → nhấc lên |
| `close_gripper / open_gripper` | gripper ảo: gắn / tháo khối khỏi tool0 |

Trạng thái trả về: `SUCCESS`, `FAILED`, `INVALID_OBJECT`, `INVALID_ZONE`, `PLANNING_FAILED`
(executor in thêm `SKIPPED` khi khối đã đúng chỗ, `NOT RUN` cho các bước sau khi có lỗi).

- **Di chuyển tới điểm:** gọi `/compute_ik` với seed là tư thế home để ra góc khớp, rồi MoveIt
  lập kế hoạch trong không gian khớp. Nhờ seed cố định, robot luôn ở tư thế "gần home" và không
  bị xoắn khớp tới giới hạn.
- **Hạ / nhấc:** đi thẳng đứng bằng `/compute_cartesian_path` với `avoid_collisions=True`.
- **An toàn:** URDF bật `safety_limits`. Bàn và 3 khối nằm trong planning scene, khối đang cầm
  được gắn vào tool0, nên MoveIt kiểm tra self-collision và va chạm môi trường cho mọi chuyển động.
- **Gripper ảo:** UR3e không có gripper. "Kẹp" = gắn khối vào tool0 trong MoveIt, còn trong Gazebo
  một timer 20 Hz đặt khối theo tool0 (`/gazebo/set_entity_state`).

## 4. Plan Validator

1. Output phải có dạng `{"plan": [...]}`, tối đa 20 bước.
2. Skill thuộc `home, pick, place, move_above, move_to_zone`, đúng tham số.
   Tham số lạ (vd `"joints"`, `"trajectory"`) → từ chối.
3. `object` ∈ {red_cube, yellow_cube, blue_cube}, `zone` ∈ {zone_a, zone_b, zone_c}.
4. Chạy thử logic: không pick khi đang cầm, chỉ place vật đang cầm, cuối plan tay phải trống.
5. Plan không kết thúc bằng `home` → tự thêm `home()`.

## 5. Mức nâng cao – zone bị chiếm

`fix_plan()` chạy thử plan trên bản sao trạng thái:
- khối đã nằm đúng zone → bỏ qua pick/place (`SKIPPED`);
- zone đích đang có khối khác → chèn bước dời khối đó sang vùng tạm `tmp_1` / `tmp_2` (đánh dấu `[tmp]`).

## 6. Cài đặt

```bash
sudo apt update
sudo apt install -y ros-humble-ur ros-humble-moveit ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-ros2-control ros-humble-ros2-controllers ros-humble-xacro python3-pytest

mkdir -p ~/ur3_ws/src && cd ~/ur3_ws/src
git clone -b humble https://github.com/UniversalRobots/Universal_Robots_ROS2_Gazebo_Simulation.git
git clone https://github.com/boanuen/UR3-control-using-LLM-Skill-based-Planning.git ur3_llm_control
cd ~/ur3_ws && colcon build --symlink-install
source install/setup.bash
```

### 9Router

```bash
npm install -g 9router
9router                       # dashboard: http://localhost:20128
```
Trong dashboard: kết nối provider (vd **Gemini** bằng API key của Google AI Studio), tạo API key
của 9Router, rồi đặt key vào biến môi trường (không ghi key vào file config):

```bash
echo 'export NINE_KEY="sk-..."' >> ~/.bashrc && source ~/.bashrc
```
Tên model đặt trong `config/student_config.yaml` (`model`, `backup_model`).

## 7. Chạy

Terminal 1 – 9Router: `9router`

Terminal 2 – mô phỏng:
```bash
ros2 launch ur3_llm_control sim.launch.py
```

Terminal 3 – node LLM (đợi terminal 2 hiện `joint_trajectory_controller` đã activated):
```bash
ros2 run ur3_llm_control llm_robot_node
```
```
Command> Please put the red cube in zone B.
Command> Hãy lấy khối màu vàng và đặt nó vào ô A.
Command> Move the green cube to zone D.
Command> Arrange all objects according to my student ID.
Command> state
```

Chạy 1 lệnh rồi thoát:
```bash
ros2 run ur3_llm_control llm_robot_node --ros-args -p command:="Move the blue cube to zone C."
```

Kiểm tra không cần Gazebo:
```bash
cd ~/ur3_ws/src/ur3_llm_control && python3 -m pytest test -q
ros2 run ur3_llm_control offline_cli "Đưa vật màu đỏ sang vùng B."
```

**Trên WSL2:** nếu cửa sổ Gazebo/RViz trống, chạy
`LIBGL_ALWAYS_SOFTWARE=1 ros2 launch ur3_llm_control sim.launch.py`. Khi chạy lại mô phỏng, tắt
hẳn tiến trình cũ trước: `pkill -9 gzserver; pkill -9 gzclient`.

## 8. Kết quả mẫu

```
USER COMMAND:
Arrange all objects according to my student ID.

LLM PLAN:
1. pick(red_cube)
2. place(red_cube, zone_a)
3. pick(yellow_cube)
4. place(yellow_cube, zone_b)
5. pick(blue_cube)
6. place(blue_cube, zone_c)
7. home()

EXECUTION:
pick(yellow_cube) [tmp] ......... SUCCESS
place(yellow_cube, tmp_1) [tmp] . SUCCESS
pick(red_cube) .................. SUCCESS
place(red_cube, zone_a) ......... SUCCESS
pick(yellow_cube) ............... SUCCESS
place(yellow_cube, zone_b) ...... SUCCESS
pick(blue_cube) ................. SUCCESS
place(blue_cube, zone_c) ........ SUCCESS
home() .......................... SUCCESS

TASK SUCCESS
```
(Ở lần chạy này khối vàng đang nằm ở zone A từ lệnh trước, nên executor dời nó sang vùng tạm trước.)
