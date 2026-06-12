@echo off
echo ================================
echo  GitSavePlugin Builder
echo ================================

REM Download Bukkit API jar using PowerShell (built into Windows)
echo Downloading Bukkit API...
powershell -Command "Invoke-WebRequest -Uri 'https://hub.spigotmc.org/nexus/content/repositories/snapshots/org/bukkit/bukkit/1.21.4-R0.1-SNAPSHOT/bukkit-1.21.4-R0.1-SNAPSHOT.jar' -OutFile 'bukkit-api.jar'"

if not exist bukkit-api.jar (
    echo ERROR: Failed to download Bukkit API. Check your internet.
    pause
    exit /b 1
)

echo Compiling plugin...
javac -cp ".;bukkit-api.jar" GitSavePlugin.java

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Compile failed!
    pause
    exit /b 1
)

echo Packaging jar...
jar cf plugins\GitSavePlugin.jar GitSavePlugin.class plugin.yml

echo.
echo ================================
echo  Done! GitSavePlugin installed!
echo  Restart server and type /save-all in-game
echo ================================
pause
