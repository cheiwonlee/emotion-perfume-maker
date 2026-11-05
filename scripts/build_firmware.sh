#!/usr/bin/env bash
# STM32CubeIDE 없이 펌웨어가 컴파일되는지 확인하는 스크립트 (CI 에서도 사용)
#   필요: arm-none-eabi-gcc  (Ubuntu: sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi)
#   사용: scripts/build_firmware.sh            # main-board, sub-board 둘 다
#         scripts/build_firmware.sh main-board
# 결과물: build/<보드>/fw.elf   (보드에 올리는 건 CubeIDE 로 하는 것을 권장)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ $# -eq 0 ]; then BOARDS=(main-board sub-board); else BOARDS=("$@"); fi

FLAGS="-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -DUSE_HAL_DRIVER -DSTM32F446xx -DDEBUG
       -O0 -g -Wall -ffunction-sections -fdata-sections --specs=nano.specs"

for board in "${BOARDS[@]}"; do
  P="$ROOT/$board"; OUT="$ROOT/build/$board"
  rm -rf "$OUT"; mkdir -p "$OUT"
  INC="-I$P/Core/Inc -I$P/Drivers/STM32F4xx_HAL_Driver/Inc -I$P/Drivers/STM32F4xx_HAL_Driver/Inc/Legacy
       -I$P/Drivers/CMSIS/Device/ST/STM32F4xx/Include -I$P/Drivers/CMSIS/Include"
  objs=()
  while IFS= read -r src; do
    obj="$OUT/$(basename "${src%.*}").o"
    arm-none-eabi-gcc $FLAGS $INC -c "$src" -o "$obj"
    objs+=("$obj")
  done < <(find "$P/Core" "$P/Drivers" -name '*.c'; find "$P/Core/Startup" -name '*.s')
  arm-none-eabi-gcc $FLAGS -T"$P/STM32F446RETX_FLASH.ld" -Wl,--gc-sections --specs=nosys.specs \
    "${objs[@]}" -o "$OUT/fw.elf" -lc -lm
  echo "== $board"; arm-none-eabi-size "$OUT/fw.elf"
done
