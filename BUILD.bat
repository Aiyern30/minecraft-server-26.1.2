@echo off
echo Building GitSavePlugin...

REM Compile using your paper jar as the API
javac -cp "paper-26.1.2-69.jar" -source 17 -target 17 GitSavePlugin.java

REM Package into a jar with plugin.yml
jar cf plugins\GitSavePlugin.jar GitSavePlugin.class plugin.yml

echo.
echo Done! Plugin saved to plugins\GitSavePlugin.jar
echo Now restart your server and type /save-all !
pause
