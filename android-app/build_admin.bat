@echo off
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"
echo JAVA_HOME is %JAVA_HOME%
java -version
call gradlew.bat assembleAdminDebug --no-daemon
