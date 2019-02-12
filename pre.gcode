; Ender 3 Custom Start G-code
M140 S60
M105
M190 S60
M104 S200
M105
M109 S200
G28 ; Home all axes
G92 E0 ; Reset Extruder
G1 Z2.0 F3000 ; Move Z Axis up little to prevent scratching of Heat Bed
G1 F1000 E10 ; extrude filament 10 mm
; End of custom start GCode