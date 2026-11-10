Option Explicit
Dim sh, fso, base, entry, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
entry = fso.BuildPath(base, "Marble_Oracle.pyw")
If Not fso.FileExists(entry) Then
  MsgBox "Marble_Oracle.pyw is missing. Extract the full application.", 16, "Marble Oracle"
  WScript.Quit 2
End If
' The Python Launcher for Windows normally supplies pyw.exe; run without a console.
cmd = "pyw -3 " & Chr(34) & entry & Chr(34)
sh.CurrentDirectory = base
sh.Run cmd, 0, False
