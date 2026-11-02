@echo off
cls
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Windows Flash Script
color 3f

echo ========================================================
echo               HyperOS Flashing Script (Windows)
echo ========================================================
echo.

set "FASTBOOT=bin\windows\fastboot.exe"
if not exist "%FASTBOOT%" set "FASTBOOT=fastboot"

set "EXPECTED_DEVICE=device_code"

:: ==========================================================
:: 1. Check phone codename / type / name
:: ==========================================================
echo [1/4] Checking connected device...
echo Please ensure your device is connected in Fastboot/Bootloader mode.
echo.

set "PRODUCT="
for /f "tokens=2 delims=: " %%i in ('"%FASTBOOT%" getvar product 2^>^&1 ^| findstr /r /c:"^product:"') do (
    set "PRODUCT=%%i"
)

if "%PRODUCT%"=="" (
    echo [WARNING] No device detected or unable to read device codename.
    echo Please make sure your device is connected in Fastboot mode with drivers installed.
    echo.
    set /p "RETRY_CHOICE=Do you want to continue anyway? (y/n): "
    if /i "!RETRY_CHOICE!" neq "y" (
        echo Flashing aborted by user.
        pause
        exit /b 1
    )
) else (
    echo Detected device codename : !PRODUCT!
    echo Expected ROM codename    : %EXPECTED_DEVICE%
    echo.
    if /i "!PRODUCT!" neq "%EXPECTED_DEVICE%" (
        echo [WARNING] Device codename mismatch!
        echo ROM is designed for [%EXPECTED_DEVICE%], but detected device is [!PRODUCT!].
        set /p "MISMATCH_CHOICE=Are you sure you want to continue anyway? (y/n): "
        if /i "!MISMATCH_CHOICE!" neq "y" (
            echo Flashing aborted by user.
            pause
            exit /b 1
        )
    ) else (
        echo [OK] Device codename verified successfully.
    )
)
echo.

:: ==========================================================
:: 2. Ask user whether to format data or not
:: ==========================================================
echo [2/4] User Data Format Options:
echo.
echo   1. Keep user data (Dirty flash / Update) [Default]
echo   2. Format data    (Clean flash - wipes userdata and metadata)
echo.
set "FORMAT_CHOICE=1"
set /p "FORMAT_CHOICE=Please select [1 or 2, default is 1]: "

if "%FORMAT_CHOICE%"=="2" (
    echo Option selected: [2] Format user data.
) else (
    echo Option selected: [1] Keep user data.
)
echo.

:: ==========================================================
:: 3. Flash phone firmware
:: ==========================================================
echo [3/4] Flashing firmware and boot partitions...
echo.

if exist "%~dp0boot.img" (
    echo Flashing boot...
    "%FASTBOOT%" flash boot_a "%~dp0boot.img"
    "%FASTBOOT%" flash boot_b "%~dp0boot.img"
) else if exist "%~dp0firmware-update\boot.img" (
    echo Flashing boot...
    "%FASTBOOT%" flash boot_a "%~dp0firmware-update\boot.img"
    "%FASTBOOT%" flash boot_b "%~dp0firmware-update\boot.img"
)

for %%P in (
    dtbo
    init_boot
    vendor_boot
    recovery
    vbmeta
    vbmeta_system
    vm-bootsys
    pvmfw
    modem
    modemfirmware
    dsp
    bluetooth
    xbl
    xbl_config
    xbl_ramdump
    tz
    hyp
    uefi
    uefisecapp
    keymaster
    qupfw
    devcfg
    featenabler
    cpucp
    cpucp_dtb
    aop
    aop_config
    abl
    shrm
    soccp_debug
    soccp_dcd
    spuservice
    imagefv
    countrycode
    idmanager
    multiimgqti
) do (
    if exist "%~dp0firmware-update\%%P.img" (
        echo Flashing %%P...
        "%FASTBOOT%" flash %%P_a "%~dp0firmware-update\%%P.img"
        "%FASTBOOT%" flash %%P_b "%~dp0firmware-update\%%P.img"
    )
)

REM firmware

echo.

:: ==========================================================
:: 4. Flash super image
:: ==========================================================
echo [4/4] Flashing super image...
echo.

if not exist "%~dp0super.img" (
    echo [ERROR] super.img not found at "%~dp0super.img"!
    echo Please make sure super.img is placed in the ROM directory.
    pause
    exit /b 1
)

echo Flashing super.img (this may take several minutes)...
"%FASTBOOT%" flash super "%~dp0super.img"
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to flash super.img!
    pause
    exit /b 1
)

if "%FORMAT_CHOICE%"=="2" (
    echo.
    echo Wiping userdata and metadata as requested...
    "%FASTBOOT%" erase userdata
    "%FASTBOOT%" erase metadata
)

:: Set active slot to a
REM SET_ACTION_SLOT_A_BEGIN
echo.
echo Setting active slot to 'a'...
"%FASTBOOT%" set_active a
REM SET_ACTION_SLOT_A_END

echo.
echo Rebooting device into system...
"%FASTBOOT%" reboot

echo.
echo ========================================================
echo Flashing completed successfully!
echo If your phone does not restart automatically, please restart manually.
echo ========================================================
pause
exit /b 0
