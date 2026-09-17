# Heart-T

- `Heart-T/`: STM32G431C6T6 firmware and STM32CubeMX CMake project.
- `Heart-T/user/driver/`: SPI1 and ADS1292R drivers; see [driver index](Heart-T/user/driver/driver.md).
- Bare-metal execution: TIM6 increments the millisecond clock; the main loop dispatches sensor (1 ms), communication (10 ms), algorithm (10 ms), and background (20 ms) functions from `Heart-T/user/app/system/taskmanager.c`. FreeRTOS is removed from the build.
- `develop/`: Device Tool scripts and per-computer configuration; see [development setup](develop/README.md).
- `.vscode/`: generated Build/Flash/Reset/RTT tasks, status bar buttons, and C/C++ indexing settings.
- `rule/`: project rules and naming conventions.

Open this repository root in VS Code. On Windows, deploy the development tasks with
`py -3 develop/quick_deploy.py deploy`, then reload the window to show the buttons.
