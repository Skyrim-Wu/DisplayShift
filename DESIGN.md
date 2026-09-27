# DisplayShift desktop UX

Primary task: send the correct per-display input command to the other computer.
Use the OS-native Tk/ttk theme, keyboard focus, resizable windows, text status,
and standard form controls. Avoid custom Apple glyphs that are missing on Windows.
Main actions stay visible above the per-display table; detailed failures live in a
scrollable log. Modal settings support Escape, cancel, inline validation, and focus
restoration. Repeated hotkeys are ignored while a job or settings dialog is active.

HIG reference: https://developer.apple.com/design/human-interface-guidelines/windows
and https://developer.apple.com/design/human-interface-guidelines/accessibility
(the public pages require JavaScript; local HIG guidance informed the implementation).

Hardware truth: detected does not mean controllable; accepted writes do not prove
visible switching. Use “command sent”, not “switched successfully”. Keep raw DDC
values for unusual firmware replies; never silently truncate them into a known port.
The LG USB-C code remains unset until calibrated on this exact monitor.

Validation: Python engine tests and Tk lifecycle smoke checks. Native screen-reader
behavior, macOS rendering and physical switching require tests on the target hosts.
