; Ender 3 Custom End G-code
G4 ; Wait
G91 ; Set coordinates to relative
G1 F1800 E-3 ; Retract filament 3 mm to prevent oozing
G1 F3000 Z20 ; Move Z Axis up 20 mm to allow filament ooze freely
G90 ; Set coordinates to absolute
M84 ; Disable stepper motors
; End of custom end GCode