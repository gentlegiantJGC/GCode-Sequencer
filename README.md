# GCode Sequencer
This program will take pre-sliced gcode with the models placed in any position and stitch them together such that they can be immediatly printed one after the other without any human interaction during printing. It will place them on the build plate as close together but far enough apart that no parts of the printer will come into contact with any of the previously printed models.

It means you can slice different models at different layer heights and totally different settings and have them print in sequence which many slicers struggle with (particulary Cura which is what I use).

This code has been designed with the Creatlity Ender 3 in mind since it is what I own and I could not find anything that already existed. This being said all the dimensions have been offloaded to the json file "options.json" so that if you have a printer that is a similar design you can modify the dimensions to fit.

**IMPORTANT** : Once the program has created the output run it through a gcode viewer to make sure that everything is correct. While I am fairly confident the script should not cause the printer to crash into anything it is down to you to be certain before you run it on your machine. You are responsible for any code you upload to your printer.

# Limitations
The script is limited to the linear G0 and G1 commands. If there are any other movement commands present it should print a message in the console. (I believe most slicers just use linear movement but make sure).

Everything must be in absolute mode otherwise it may produce unpredictable results (again I think most slicers do use absolute positioning).

The pre-sliced gcode must not have any of their own pre or post gcode that will effect the print. This includes G28 (auto-home), M84 (disable steppers) or temperature setting commands turning off the build plate (M140 S0) or hot end (M104 S0).

# Running
Install Python (written for Python 3.7 but other versions of Python 3 may also work)

Slice your models using the settings you want in your favourite slicer (taking note of the limitations above)

Again make sure that the slicer hasn't slipped in any of the commands mentioned above

Open print_order.txt and put the paths to the gcode files that you want to print (one path per line). If you want a model printed a number of times duplicate it as many as you want.

Modify pre.gcode, mid.gcode and post.gcode if you like. These will be added in before the first print, between every print and after the last print respectively.

Make sure the settings in options.json are correct for your printer. They have been set up for a Creatliy Ender 3 but make sure they are correct even if you have the same printer.

Run GCode_Sequencer.py and it will try and fit them as best as it can. It will create a file called ouput.gcode which is the combined file

Preview it in a gcode viewer to make sure everything is correct then send it to the printer if it is.

# Options.json
All dimensions are in mm. Directions are from looking at the front with the origin in the bottom left.

gantry_z_clearance - The distance between the build plate and the bottom of the beam running left to right when the nozzle is touching the build plate.

head_x_min - The distance between the print nozzle and the left of the print head assembly.

head_x_max - The distance between the print nozzle and the right of the print head assembly.

head_y_min - The distance between the print nozzle and the front of the print head assembly.

head_y_max - The distance between the print nozzle and the back of the print head assembly (the gantry on the Ender 3).

gantry_head_y_offset - The distance in the y (front to back) direction that the nozzle is offset from the gantry. Used to stop the gantry hitting prints.

nozzle_outer_diameter - The outer diameter of the print nozzle. Used to stop it colliding with prints.

head_z_clearance - The distance between the build plate and the bottom of the print head assembly when the nozzle is touching the build plate.

xy_air_gap - The gap to leave between the printer head and gantry and the printed parts.

bed_x_min - The minimum printable coordinate in the x direction

bed_x_max - The maximum printable coordinate in the x direction

bed_y_min - The minimum printable coordinate in the y direction

bed_y_max - The maximum printable coordinate in the y direction

bed_z_max - The minimum printable coordinate in the z direction

iteration_step - The distance between points to test if the space is free

remove_commands_starting - A list of strings. If the command starts with a string in this list it will be removed.
