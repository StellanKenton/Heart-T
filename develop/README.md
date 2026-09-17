# Device Tool

Open `D:/Space/Cosmos/Heart-T` as the VS Code workspace root.

## Setup on Windows

```powershell
py -3 develop/quick_deploy.py deploy
py -3 develop/device_tool.py info
```

The deployment updates `.vscode/tasks.json`, `.vscode/settings.json`, and
`.vscode/extensions.json`, preserving unrelated settings. Install the recommended
`usernamehw.commands` extension and run `Developer: Reload Window` to display
Build, Flash, Reset, and RTT in the bottom status bar. C/C++ and CMake Tools are
recommended for navigation and editing. C/C++ indexes the generated
`Heart-T/build/Debug/compile_commands.json` after the first build.

## Commands

Use the bottom buttons or the matching `Device Tool:` tasks. Ctrl+Shift+B runs
the default Device Tool build. The same entry points are available in a terminal:

```powershell
py -3 develop/quick_deploy.py build
py -3 develop/quick_deploy.py flash
py -3 develop/quick_deploy.py reset
py -3 develop/quick_deploy.py rtt
```

- Build: configure and compile the STM32CubeMX project with CMake, Ninja, and Arm GNU GCC.
- Flash: download `Heart-T/build/Debug/Heart-T.elf` via J-Link and run the target.
- Reset: reset and run the target via J-Link.
- RTT: stop existing J-Link server/client processes, start the GDB server, and read the RTT Telnet port. Ctrl+C stops the session.

The current firmware does not include SEGGER RTT support. The RTT task is ready,
but firmware RTT logging must be added before target logs can appear. If RTT
produces no output with an RTT-enabled firmware, try Reset before reconnecting.

## Files and machine configuration

- `quick_deploy.py`: VS Code deployment and task entry point.
- `device_tool.py`: build, J-Link operations, and machine detection.
- `device_tool_config.json`: OS/hostname profiles, tool paths, target, and ports.

The Windows `computer2` profile matches `WorkStation` and uses:

- CMake: `C:/Program Files/CMake/bin/cmake.exe`
- Ninja: `C:/msys64/mingw64/bin/ninja.exe`
- GCC: `C:/Program Files (x86)/Arm/GNU Toolchain mingw-w64-i686-arm-none-eabi/bin`
- J-Link: `C:/Program Files/SEGGER/JLink_V918`
- Target: `STM32F103C8`, SWD, 4000 kHz

Edit the profile when tool locations change. Add a profile for another machine,
or explicitly select one with `--computer computer2` after the quick-deploy action.
The macOS profile retains its own tool locations and has not been validated on this Windows host.
