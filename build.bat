@echo off
rem Rebuild the castle kit:  build.bat   (every piece into export\*.glb and export\catalog.json)
rem Uses Blender 5.2 from its default install folder; set BLENDER to another blender.exe to use that instead.
setlocal
if not defined BLENDER set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
"%BLENDER%" -b --python "%~dp0blender\make.py" || exit /b 1
