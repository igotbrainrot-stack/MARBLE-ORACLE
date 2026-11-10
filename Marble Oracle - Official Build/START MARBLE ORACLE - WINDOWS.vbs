Option Explicit
Dim sh, fs, base, boot, command, choice, result
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = fs.GetParentFolderName(WScript.ScriptFullName)
boot = fs.BuildPath(fs.BuildPath(fs.BuildPath(base, "Application"), "Runtime"), "launch_suite.pyw")
If Not fs.FileExists(boot) Then
  MsgBox "The application folder is missing. Extract the entire Marble Oracle ZIP.", 16, "Marble Oracle"
  WScript.Quit 2
End If
sh.CurrentDirectory = fs.BuildPath(fs.BuildPath(base, "Application"), "Runtime")
' The Windows launcher is WScript, not CMD or PowerShell.
' All child Python GUI processes use pyw.exe/pythonw.exe; window style 0 is hidden.
choice = "pyw -3"
On Error Resume Next
Err.Clear
result = sh.Run("pyw -3 -c " & Chr(34) & "import tkinter" & Chr(34), 0, True)
If Err.Number <> 0 Or result <> 0 Then
  Err.Clear
  result = sh.Run("pythonw -c " & Chr(34) & "import tkinter" & Chr(34), 0, True)
  If Err.Number <> 0 Or result <> 0 Then
    MsgBox "Python 3 with Tkinter is required before the setup window can appear." & vbCrLf & "Install Python 3, then reopen Marble Oracle.", 16, "Marble Oracle"
    WScript.Quit 3
  End If
  choice = "pythonw"
End If
command = choice & " " & Chr(34) & boot & Chr(34)
' Start the graphical requirements setup asynchronously with no terminal.
Err.Clear
sh.Run command, 0, False
If Err.Number <> 0 Then
  MsgBox "Unable to start the setup window: " & Err.Description, 16, "Marble Oracle"
  WScript.Quit 4
End If
