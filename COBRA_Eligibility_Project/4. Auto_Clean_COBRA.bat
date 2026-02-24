@echo off
setlocal EnableDelayedExpansion

REM ==================================================
REM Paths
REM ==================================================
set SCRIPT_DIR=%~dp0
set INPUT_FILE=%SCRIPT_DIR%cobra_raw.csv
set OUTPUT_FILE=%SCRIPT_DIR%cobra_out.csv
set EXE_FILE=%SCRIPT_DIR%COBRACLEAN.exe

REM Temp log in root
set TEMP_LOG=%SCRIPT_DIR%cobra_watch.log

REM Archive folders
set OUTPUT_DIR=%SCRIPT_DIR%outputs
set PROCESSED_DIR=%SCRIPT_DIR%processed
set LOG_DIR=%SCRIPT_DIR%logs

REM ==================================================
REM Timestamp (YYYYMMDD_HHMMSS)
REM ==================================================
for /f "tokens=1-3 delims=/" %%a in ("%DATE%") do (
    set MM=%%a
    set DD=%%b
    set YYYY=%%c
)

for /f "tokens=1-3 delims=:." %%a in ("%TIME%") do (
    set HH=%%a
    set MI=%%b
    set SS=%%c
)

if "%HH:~0,1%"==" " set HH=0%HH:~1,1%

set TS=%YYYY%%MM%%DD%_%HH%%MI%%SS%

REM ==================================================
REM Ensure folders exist
REM ==================================================
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%PROCESSED_DIR%" mkdir "%PROCESSED_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM ==================================================
REM Start logging
REM ==================================================
echo ================================================== >> "%TEMP_LOG%"
echo [%DATE% %TIME%] WATCHER STARTED >> "%TEMP_LOG%"
echo [%DATE% %TIME%] Working directory: %SCRIPT_DIR% >> "%TEMP_LOG%"

REM ==================================================
REM Validation
REM ==================================================
if not exist "%EXE_FILE%" (
    echo [%DATE% %TIME%] ERROR: COBRACLEAN.exe not found >> "%TEMP_LOG%"
    goto FINALIZE
)

if not exist "%INPUT_FILE%" (
    echo [%DATE% %TIME%] No cobra_raw.csv found. Exiting. >> "%TEMP_LOG%"
    goto FINALIZE
)

REM ==================================================
REM Run COBRACLEAN
REM ==================================================
echo [%DATE% %TIME%] Running COBRACLEAN.exe >> "%TEMP_LOG%"
"%EXE_FILE%" >> "%TEMP_LOG%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%DATE% %TIME%] COBRACLEAN.exe exit code: %EXIT_CODE% >> "%TEMP_LOG%"

REM ==================================================
REM Archive output file
REM ==================================================
if exist "%OUTPUT_FILE%" (
    move "%OUTPUT_FILE%" "%OUTPUT_DIR%\cobra_out_%TS%.csv" >> "%TEMP_LOG%" 2>&1
    echo [%DATE% %TIME%] Archived cobra_out.csv >> "%TEMP_LOG%"
) else (
    echo [%DATE% %TIME%] WARNING: cobra_out.csv not found >> "%TEMP_LOG%"
)

REM ==================================================
REM Archive input file
REM ==================================================
move "%INPUT_FILE%" "%PROCESSED_DIR%\cobra_raw_%TS%.csv" >> "%TEMP_LOG%" 2>&1
echo [%DATE% %TIME%] Archived cobra_raw.csv >> "%TEMP_LOG%"

REM ==================================================
REM Finalize log
REM ==================================================
:FINALIZE
echo [%DATE% %TIME%] WATCHER COMPLETE >> "%TEMP_LOG%"
echo ================================================== >> "%TEMP_LOG%"

copy "%TEMP_LOG%" "%LOG_DIR%\cobra_watch_%TS%.log" > nul
del "%TEMP_LOG%"

endlocal
