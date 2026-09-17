# Heart-T

- `Heart-T/`: STM32F103C8T6 firmware and STM32CubeMX CMake project.
- `Heart-T/user/driver/`: SPI2, ADS1292R and USB CDC drivers; see [driver index](Heart-T/user/driver/driver.md).
- MCU: Cortex-M3, 64 KB Flash, 20 KB RAM; 8 MHz external crystal, 72 MHz core clock.
- ADS1292 wiring matches the reference STM32-V2.0 project: PWDN/RESET PB10, START PB11, CS PB12, SCLK PB13, DOUT PB14, DIN PB15, DRDY PA8 (EXTI9_5).
- Bare-metal execution: TIM2 increments the millisecond clock; the main loop dispatches sensor (1 ms), communication (10 ms), algorithm (10 ms), and background (20 ms) functions from `Heart-T/user/app/system/taskmanager.c`. FreeRTOS is removed from the build.
- `develop/`: Device Tool scripts and per-computer configuration; see [development setup](develop/README.md).
- `.vscode/`: generated Build/Flash/Reset/RTT tasks, status bar buttons, and C/C++ indexing settings.
- `rule/`: project rules and naming conventions.

Open this repository root in VS Code. On Windows, deploy the development tasks with
`py -3 develop/quick_deploy.py deploy`, then reload the window to show the buttons.

USB CDC echo runs in `communicationProcess`: bytes received on the board USB data port
(PA11/PA12) are returned unchanged. See [USB driver contract](Heart-T/user/driver/drvusb/drvusb.md)
for hardware, buffering and verification.

`Heart-T/Middlewares/ST/STM32_USB_Device_Library/` contains the Core and CDC subset of
[ST USB Device library v2.11.3](https://github.com/STMicroelectronics/stm32-mw-usb-device/tree/v2.11.3),
with its `LICENSE.md`. The vendor control-request fallback `USBD_MAX_STR_DESC_SIZ` macro
is supplied by the project `usbd_conf.h` to keep macro definitions in headers.
