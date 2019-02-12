; custom mid-gcode
G4 ; Wait
G91 ; Set coordinates to relative
G1 F1800 E-3 ; Retract filament 3 mm to prevent oozing
G0 F3000 Z10 ; Move Z Axis up 10 mm
G1 F1800 E6 ; Unretract filament 6 mm
G90 ; Set coordinates to absolute
G92 E0 ; Reset Extruder
; end of custom mid-gcode