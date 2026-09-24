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

ESP32-S3 buttons/tasks are `Device Tool: ESP Build`, `ESP Flash`, `ESP Reset`, and
`ESP Console`; their terminal equivalents are `esp-build`, `esp-flash`,
`esp-reset`, and `esp-console` through `quick_deploy.py`. Set `HEART_ESP_PORT`
to the ESP USB port for flash/reset. The TCP console discovers the device by
UDP, or uses `HEART_ESP_HOST` when set. These ESP actions use the `esp` paths in
the selected computer profile; the STM32 actions retain their existing entry.

The current firmware does not include SEGGER RTT support. The RTT task is ready,
but firmware RTT logging must be added before target logs can appear. If RTT
produces no output with an RTT-enabled firmware, try Reset before reconnecting.

## Files and machine configuration

- `quick_deploy.py`: VS Code deployment and task entry point.
- `device_tool.py`: build, J-Link operations, and machine detection.
- `device_tool_config.json`: OS/hostname profiles, tool paths, target, and ports.
- `esp_device_tool.py`, `run_esp_idf.ps1`: ESP-IDF build/flash/reset and TCP console through Device Tool.

The Windows `computer2` profile matches `WorkStation` and uses:

- CMake: `C:/Program Files/CMake/bin/cmake.exe`
- Ninja: `C:/msys64/mingw64/bin/ninja.exe`
- GCC: `C:/Program Files (x86)/Arm/GNU Toolchain mingw-w64-i686-arm-none-eabi/bin`
- J-Link: `C:/Program Files/SEGGER/JLink_V918`
- Target: `STM32F103C8`, SWD, 4000 kHz

Edit the profile when tool locations change. Add a profile for another machine,
or explicitly select one with `--computer computer2` after the quick-deploy action.
The macOS profile retains its own tool locations and has not been validated on this Windows host.

## USB reset self-test

`usb_selftest_result.json` records the Windows USB CDC hardware test: before reset and after three Device Tool resets, COM25 was reopened and binary echo passed. The monitor recorded COM25 disappearing and reappearing on each reset. Existing serial handles must be closed and reopened after USB disconnect.

## ESP RLD battery comparison

`rld_measurement_20260924.json` records the V1.0.1 battery-powered `0xC0 -> 0xEC -> 0xC0` comparison, acquisition checks, metric definitions and final state. `rld_measurement_20260924.npz` preserves all raw CH1/CH2 pairs under keys `off_before`, `on`, and `off_after`. Each analysis uses the last 10000 pairs and a Hann window; values are raw ADC codes. RLD off reduced CH2 50 Hz band RMS but increased its 100 Hz component. Analog feedback circuitry remains unverified.
