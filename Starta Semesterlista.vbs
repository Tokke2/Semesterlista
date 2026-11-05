Option Explicit
Dim shell, files, root, command, result, maintenance
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
maintenance = WScript.Arguments.Named.Exists("maintenance")
command = """" & shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & root & "\tools\start_semesterlista.ps1"""
If maintenance Then command = command & " -MaintenanceOnly"
' Window style 0 hides the console before creation. Wait preserves task status.
On Error Resume Next
result = shell.Run(command, 0, True)
If Err.Number <> 0 Then
    If Not maintenance Then MsgBox "Semesterlista could not start: " & Err.Description, 16, "Semesterlista"
    WScript.Quit 1
End If
On Error GoTo 0
WScript.Quit result
