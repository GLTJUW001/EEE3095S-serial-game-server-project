# EEE3095S Serial Game Server - standalone GNU Arm build.
# CubeIDE has its own managed Debug/Release builds in .cproject.
# Expects Core/Src, Core/Inc, Core/Startup and Drivers/ from the CubeIDE project.

.DEFAULT_GOAL := all

TARGET := GameServer
CONFIG ?= Debug
PREFIX ?= arm-none-eabi-

ifeq ($(CONFIG),Debug)
OPT ?= -O0
DEBUG_FLAGS := -g3
else ifeq ($(CONFIG),Release)
OPT ?= -Os
DEBUG_FLAGS :=
else
$(error CONFIG must be Debug or Release)
endif

VARIANT := server
BUILD_DIR ?= build/$(CONFIG)/$(VARIANT)

# Use the compiler on PATH, an explicitly supplied GCC_PATH, or the usual
# Linux/macOS CubeIDE toolchain location. No toolchain is downloaded by make.
ifndef GCC_PATH
ifeq ($(shell command -v $(PREFIX)gcc 2>/dev/null),)
GCC_PATH := $(firstword $(wildcard \
  /opt/st/stm32cubeide*/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin \
  $(HOME)/st/stm32cubeide*/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin \
  /Applications/STM32CubeIDE.app/Contents/Eclipse/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin))
endif
endif

TOOL_PREFIX := $(if $(GCC_PATH),$(GCC_PATH)/,)$(PREFIX)
CC := "$(TOOL_PREFIX)gcc"
OBJCOPY := "$(TOOL_PREFIX)objcopy"
SIZE := "$(TOOL_PREFIX)size"

C_SOURCES := $(sort $(wildcard Core/Src/*.c) \
                    $(wildcard Drivers/STM32F0xx_HAL_Driver/Src/*.c))
ASM_SOURCES := Core/Startup/startup_stm32f051c6tx.s
OBJECTS := $(addprefix $(BUILD_DIR)/,$(C_SOURCES:.c=.o)) \
           $(addprefix $(BUILD_DIR)/,$(ASM_SOURCES:.s=.o))
DEPS := $(OBJECTS:.o=.d)
LDSCRIPT := STM32F051C6TX_FLASH.ld

MCU_FLAGS := -mcpu=cortex-m0 -mthumb -mfloat-abi=soft
CPPFLAGS := -DSTM32F051x8 -DUSE_HAL_DRIVER \
            -ICore/Inc \
            -IDrivers/STM32F0xx_HAL_Driver/Inc \
            -IDrivers/STM32F0xx_HAL_Driver/Inc/Legacy \
            -IDrivers/CMSIS/Device/ST/STM32F0xx/Include \
            -IDrivers/CMSIS/Include
CFLAGS := $(MCU_FLAGS) $(OPT) $(DEBUG_FLAGS) -std=gnu11 -Wall -Wextra \
          -fdata-sections -ffunction-sections -fno-common -MMD -MP
ASFLAGS := $(MCU_FLAGS) $(DEBUG_FLAGS) -x assembler-with-cpp -MMD -MP
LDFLAGS := $(MCU_FLAGS) --specs=nano.specs --specs=nosys.specs \
           -T$(LDSCRIPT) -Wl,--gc-sections -Wl,--print-memory-usage \
           -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref
LDLIBS := -Wl,--start-group -lc -lm -Wl,--end-group

.PHONY: all clean size help test

all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

# These ST drivers intentionally leave some parameters unused on the F051.
# Keep the additional warnings enabled for the application source files.
$(BUILD_DIR)/Drivers/%.o: CFLAGS += -Wno-unused-parameter

$(BUILD_DIR)/%.o: %.c Makefile
	@mkdir -p "$(dir $@)"
	$(CC) $(CPPFLAGS) $(CFLAGS) -c "$<" -o "$@"

$(BUILD_DIR)/%.o: %.s Makefile
	@mkdir -p "$(dir $@)"
	$(CC) $(CPPFLAGS) $(ASFLAGS) -c "$<" -o "$@"

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) $(LDSCRIPT) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"
	$(SIZE) "$@"

$(BUILD_DIR)/$(TARGET).hex: $(BUILD_DIR)/$(TARGET).elf
	$(OBJCOPY) -O ihex "$<" "$@"

$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	$(OBJCOPY) -O binary "$<" "$@"

size: $(BUILD_DIR)/$(TARGET).elf
	$(SIZE) "$<"

clean:
	$(RM) -r "$(BUILD_DIR)"

help:
	@echo 'make                       Build the firmware'
	@echo 'make CONFIG=Release        Build with size optimisation'
	@echo 'make GCC_PATH=/path/to/bin  Use a specific GNU Arm toolchain'
	@echo 'make clean                 Remove the selected build directory'
	@echo 'make test                  Run game and protocol tests on the host'

# Host tests compile the real game, parser and server sources on the PC
# (uart_send_line is replaced by a capture stub in tests/protocol_test.c).
HOST_CC ?= cc
HOST_TEST_DIR := build/host-tests
HOST_FLAGS := -std=c11 -O2 -Wall -Wextra -Werror -ICore/Inc

test:
	@mkdir -p "$(HOST_TEST_DIR)"
	$(HOST_CC) $(HOST_FLAGS) Core/Src/game.c tests/game_test.c -o "$(HOST_TEST_DIR)/game_test"
	"$(HOST_TEST_DIR)/game_test"
	$(HOST_CC) $(HOST_FLAGS) Core/Src/game.c Core/Src/server.c Core/Src/parser.c \
		tests/protocol_test.c -o "$(HOST_TEST_DIR)/protocol_test"
	"$(HOST_TEST_DIR)/protocol_test"

-include $(DEPS)
