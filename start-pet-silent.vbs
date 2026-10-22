' Baishuang desktop pet - silent launcher (no console window flash).
' Double-click this file, or use the shortcut 白霜.lnk.
' It just runs start-pet.cmd with a hidden window; all logic lives in that .cmd.
' Keep this file pure ASCII.
Option Explicit
Dim sh, fso, here
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here
sh.Run """" & here & "\start-pet.cmd""", 0, False
