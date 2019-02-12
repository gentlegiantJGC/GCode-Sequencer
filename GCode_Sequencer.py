import json
import copy
from typing import Dict, Union, List, TextIO


def run(options: Dict[str, Union[int, float, List[str]]], file_list: List[str], save_file: TextIO, pre_gcode: str, mid_gcode: str, post_gcode: str):
	# check all the entries are present and valid
	if not save_file.writable():
		raise Exception('save_file must have write permissions')
	if not pre_gcode.endswith('\n'):
		pre_gcode += '\n'
	if not mid_gcode.endswith('\n'):
		mid_gcode += '\n'

	assert 'gantry_z_clearance' in options
	assert isinstance(options['gantry_z_clearance'], (int, float)) and options['gantry_z_clearance'] >= 0
	assert 'head_x_min' in options
	assert isinstance(options['head_x_min'], (int, float)) and options['head_x_min'] >= 0
	assert 'head_x_max' in options
	assert isinstance(options['head_x_max'], (int, float)) and options['head_x_max'] >= 0
	assert 'head_y_min' in options
	assert isinstance(options['head_y_min'], (int, float)) and options['head_y_min'] >= 0
	assert 'head_y_max' in options
	assert isinstance(options['head_y_max'], (int, float)) and options['head_y_max'] >= 0
	assert 'gantry_head_y_offset' in options
	assert isinstance(options['gantry_head_y_offset'], (int, float)) and options['gantry_head_y_offset'] >= 0
	assert 'nozzle_outer_diameter' in options
	assert isinstance(options['nozzle_outer_diameter'], (int, float)) and options['nozzle_outer_diameter'] >= 0
	assert 'head_z_clearance' in options
	assert isinstance(options['head_z_clearance'], (int, float)) and options['head_z_clearance'] >= 0
	assert 'xy_air_gap' in options
	assert isinstance(options['xy_air_gap'], (int, float)) and options['xy_air_gap'] >= 0
	assert 'bed_x_min' in options
	assert isinstance(options['bed_x_min'], (int, float)) and options['bed_x_min'] >= 0
	assert 'bed_x_max' in options
	assert isinstance(options['bed_x_max'], (int, float)) and options['bed_x_max'] >= 0
	assert 'bed_y_min' in options
	assert isinstance(options['bed_y_min'], (int, float)) and options['bed_y_min'] >= 0
	assert 'bed_y_max' in options
	assert isinstance(options['bed_y_max'], (int, float)) and options['bed_y_max'] >= 0
	assert 'bed_z_max' in options
	assert isinstance(options['bed_z_max'], (int, float)) and options['bed_z_max'] >= 0
	assert 'iteration_step' in options
	assert isinstance(options['iteration_step'], (int, float)) and options['iteration_step'] >= 0
	assert 'remove_commands_starting' in options
	assert isinstance(options['remove_commands_starting'], list)

	# the algorithm works by checking if the model axis aligned bounding box fits on the base and around other models
	# it tries putting the bounding box on every point on a grid of points until it finds one that doesn't intersect other models
	# step is the grid unit size and starting_coord is the origin of the grid
	step = {'y': options['iteration_step']}
	starting_coord = {'y': options['bed_y_min']}

	# sign keeps track of which corner is started in based on the smallest dimension of the extruder head
	sign = {}
	if options['head_x_max'] < options['head_x_min']:
		step['x'] = - options['iteration_step']
		sign['x'] = -1
		starting_coord['x'] = options['bed_x_max']
	else:
		step['x'] = options['iteration_step']
		sign['x'] = 1
		starting_coord['x'] = options['bed_x_min']

	# a list of the axis aligned bounding boxes of the models plus an offset based on the printer settings
	blocked_bounding_boxes = []  # contains a list in the format [x_min, x_max, y_min, y_max]
	# much the same as blocked_bounding_boxes but just the bounding boxes without the offset
	# used to look back and find space for models that could be printed before other models
	model_bouding_boxes = []
	# the class instance for each model that has been placed. Used so that the gcode can be generated at the end
	placed_models = []
	failed_models = []

	file_counter = 0
	# iterate through all files in file_list
	while file_counter < len(file_list):
		if file_list[file_counter] == '':
			# skip blank entries
			file_counter += 1
			continue
		elif file_list[file_counter] in failed_models:
			print(f'Could not find space for model {file_list[file_counter]}')
			file_counter += 1
			continue
		# load and parse gcode file
		current_model = GCode(file_list[file_counter], options)

		is_placed = False
		# set up the iteration grid
		coord = copy.deepcopy(starting_coord)
		# the dimensions of the current model
		model_x_dim = current_model.max_x - current_model.min_x
		model_y_dim = current_model.max_y - current_model.min_y
		model_z_dim = current_model.max_z

		# iterate across every point in the grid. (while is used here to make breaking out easier)
		while options['bed_y_min'] <= coord['y'] <= options['bed_y_max'] and options['bed_y_min'] <= coord['y'] + model_y_dim <= options['bed_y_max'] and not is_placed:
			while options['bed_x_min'] <= coord['x'] <= options['bed_x_max'] and options['bed_x_min'] <= coord['x'] + model_x_dim * sign['x'] <= options['bed_x_max'] and not is_placed:
				# ^^^ check that the model fits on the bed at the current location and that it hasn't already been placed
				# check that the current model location does not intersect with any other placed model
				if not any(
					[
						box_collision(
							coord['x'],
							coord['x'] + model_x_dim * sign['x'],
							coord['y'],
							coord['y'] + model_y_dim,
							*box
						) for box in blocked_bounding_boxes
					]
				):
					# the current position does not interfere with any other blocked bounding boxes
					is_placed = True  # set this so that it breaks out of the while loop on the next loop
					placed_models.append(current_model)
					# move the coordinates in the gcode file to the new location
					if options['head_z_clearance'] < model_z_dim:
						# if the height of the model is greater than the clearance between the build plate
						# and the bottom of the print head when the nozzle is touching the build plate add
						# a bounding box equal to the model bounding box plus the dimensions of the print head
						blocked_bounding_boxes.append(
							[
								coord['x'] - max(options['head_x_min'], options['head_x_max']) * sign['x'],
								coord['x'] + (model_x_dim + min(options['head_x_min'], options['head_x_max']) + options['xy_air_gap']) * sign['x'],
								coord['y'] - options['head_y_max'],
								coord['y'] + model_y_dim + options['head_y_min'] + options['xy_air_gap']
							]
						)
						if options['gantry_z_clearance'] < model_z_dim:
							# if the model is taller than the gantry clearance then it also has the gantry to worry about
							# block off the whole width of the print bed such that the gantry does not collide
							blocked_bounding_boxes.append(
								[
									options['bed_x_min'],
									options['bed_x_max'],
									coord['y'] - options['head_y_max'],
									coord['y'] + model_y_dim + options['xy_air_gap'] - options['gantry_head_y_offset']
								]
							)
					else:
						# if the model can fit below the print head then add the dimension of the nozzle
						blocked_bounding_boxes.append(
							[
								coord['x'] - (options['nozzle_outer_diameter']/2 + options['xy_air_gap']) * sign['x'],
								coord['x'] + (model_x_dim + options['nozzle_outer_diameter']/2 + options['xy_air_gap']) * sign['x'],
								coord['y'] - (options['nozzle_outer_diameter']/2 + options['xy_air_gap']),
								coord['y'] + model_y_dim + options['nozzle_outer_diameter']/2 + options['xy_air_gap']
							]
						)
				elif model_z_dim < options['head_z_clearance'] and not any(
					[
						box_collision(
							coord['x'] - (options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']) * sign['x'],
							coord['x'] + (model_x_dim + options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']) * sign['x'],
							coord['y'] - (options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']),
							coord['y'] + model_y_dim + options['nozzle_outer_diameter'] / 2 + options['xy_air_gap'],
							*box
						) for box in model_bouding_boxes
					]
				):
					is_placed = True
					blocked_bounding_boxes.append(
						[
							coord['x'] - (options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']) * sign['x'],
							coord['x'] + (model_x_dim + options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']) * sign['x'],
							coord['y'] - (options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']),
							coord['y'] + model_y_dim + options['nozzle_outer_diameter'] / 2 + options['xy_air_gap']
						]
					)
					placed_models.insert(0, current_model)
				elif options['head_z_clearance'] < model_z_dim < options['gantry_z_clearance'] and not any(
					[
						box_collision(
							coord['x'] - max(options['head_x_min'], options['head_x_max']) * sign['x'],
							coord['x'] + (model_x_dim + min(options['head_x_min'], options['head_x_max']) + options['xy_air_gap']) * sign['x'],
							coord['y'] - options['head_y_max'],
							coord['y'] + model_y_dim + options['head_y_min'] + options['xy_air_gap'],
							*box
						) for box in model_bouding_boxes
					]
				):
					is_placed = True
					blocked_bounding_boxes.append(
						[
							coord['x'] - max(options['head_x_min'], options['head_x_max']) * sign['x'],
							coord['x'] + (model_x_dim + min(options['head_x_min'], options['head_x_max']) + options['xy_air_gap']) * sign['x'],
							coord['y'] - options['head_y_max'],
							coord['y'] + model_y_dim + options['head_y_min'] + options['xy_air_gap']
						]
					)
					placed_models.insert(0, current_model)

				if is_placed:
					model_bouding_boxes.append([coord['x'], coord['x'] + model_x_dim * sign['x'], coord['y'], coord['y'] + model_y_dim])
					current_model.move(min(coord['x'], coord['x'] + model_x_dim * sign['x']) - current_model.min_x, min(coord['y'], coord['y'] + model_y_dim) - current_model.min_y)

				# continue to next iteration step
				coord['x'] += step['x']
			coord['x'] = starting_coord['x']
			coord['y'] += step['y']

		if not is_placed:
			print(f'Could not find space for model {file_list[file_counter]}')
			failed_models.append(file_list[file_counter])

		file_counter += 1

	max_model_height = 0
	write_mid_gcode = False
	save_file.write(pre_gcode)
	for current_model in placed_models:
		if write_mid_gcode:
			# retract a little and hop up then prime the nozzle again
			save_file.write(mid_gcode)
		# lift the print head above the maximum model height to ensure it does not collide with any other prints
		save_file.write(f'G0 Z{max_model_height + 10}\n')
		# travel to the location of the new print staying at a height greater than the maximum model height
		if options['head_x_max'] < options['head_x_min']:
			save_file.write(f'G0 X{current_model.max_x - options["head_x_max"]} Y{current_model.min_y + options["head_y_min"]}\n')
		else:
			save_file.write(f'G0 X{current_model.min_x - options["head_x_min"]} Y{current_model.min_y + options["head_y_min"]}\n')

		# add the actual model gcode that should first travel to the starting location and then start printing
		save_file.write(f'{current_model.output}')

		# update the max model height if the new model is taller
		if max_model_height < current_model.max_z:
			max_model_height = current_model.max_z

		write_mid_gcode = True

	save_file.write(post_gcode)


def box_collision(
		a_min_x: Union[int, float], a_max_x: Union[int, float], a_min_y: Union[int, float], a_max_y: Union[int, float],
		b_min_x: Union[int, float], b_max_x: Union[int, float], b_min_y: Union[int, float], b_max_y: Union[int, float]
) -> bool:
	"""Return if two axis alligned bounding boxes intersect"""
	if a_min_x > a_max_x:
		a_max_x, a_min_x = a_min_x, a_max_x
	if a_min_y > a_max_y:
		a_max_y, a_min_y = a_min_y, a_max_y
	if b_min_x > b_max_x:
		b_max_x, b_min_x = b_min_x, b_max_x
	if b_min_y > b_max_y:
		b_max_y, b_min_y = b_min_y, b_max_y
	return (abs(a_max_x + a_min_x - b_max_x - b_min_x) < (a_max_x - a_min_x + b_max_x - b_min_x)) and (abs(a_max_y + a_min_y - b_max_y - b_min_y) < (a_max_y - a_min_y + b_max_y - b_min_y))
	# if the distance between the centre point in each axis is less than the length of that side then they intersect
	# https://gamedev.stackexchange.com/questions/586/what-is-the-fastest-way-to-work-out-2d-bounding-box-intersection


class GCode:
	"""A container to load a .gcode file and methods to access some attributes and modify the data"""
	def __init__(self, file_path: str, options: Dict[str, Union[int, float, List[str]]]):
		self.command_list = []
		with open(file_path) as f:
			for command in f.readlines():
				command = command.replace('\r', '').replace('\n', '')
				if command.startswith('G0 ') or command.startswith('G1 '):
					self.command_list.append(GCodeMove(command))
				elif any(command.startswith(prefix) for prefix in options['remove_commands_starting']):
					continue
				else:
					if command.startswith('G28 '):
						print('Found a G28 (home command). This will cause issues. Run this in the pre.gcode file')
					elif command.startswith('M84'):
						print('Found a M84 (disable stepper) command. This will cause issues. Run this in post.gcode to run at the very end')
					elif command.startswith('M140 S0') or command.startswith('M104 S0'):
						print('Found cooldown command ("M140 S0" or "M104 S0"). Might want to remove this and put it in the post.gcode file')
					elif command.startswith('G2 ') or command.startswith('G3 ') or command.startswith('G5 ') or command.startswith('G42 '):
						print(f'This command "{command}" may cause issues.')
					self.command_list.append(GCodeMisc(command))

	def move(self, dx: Union[int, float], dy: Union[int, float]):
		"""Move the X and Y coordinates of all the valid commands by offset dx and dy if applicable to the command."""
		for command in self.command_list:
			command.move(dx, dy)

	@property
	def output(self) -> str:
		"""Return the whole gcode file in string form."""
		return ''.join([command.output for command in self.command_list])

	@property
	def min_x(self) -> Union[int, float]:
		"""Return the smallest x coordinate."""
		return min([command.x for command in self.command_list if command.x is not None])

	@property
	def max_x(self) -> Union[int, float]:
		"""Return the largest x coordinate."""
		return max([command.x for command in self.command_list if command.x is not None])

	@property
	def min_y(self) -> Union[int, float]:
		"""Return the smallest y coordinate."""
		return min([command.y for command in self.command_list if command.y is not None])

	@property
	def max_y(self) -> Union[int, float]:
		"""Return the largest y coordinate."""
		return max([command.y for command in self.command_list if command.y is not None])

	@property
	def max_z(self) -> Union[int, float]:
		"""Return the largest z coordinate."""
		return max([command.z for command in self.command_list if command.z is not None])


class BaseGCodeCommand:
	"""Base class that all other gcode commands should inherit."""
	@property
	def output(self) -> str:
		"""Return the command in string form"""
		raise NotImplemented

	def move(self, dx: Union[int, float], dy: Union[int, float]):
		"""Move the X and Y coordinates of the command by offset dx and dy if applicable to the command"""
		pass

	@property
	def x(self) -> Union[int, float, None]:
		"""return the x coordinate of the command if applicable and defined otherwise returns None"""
		return None

	@property
	def y(self) -> Union[int, float, None]:
		"""return the y coordinate of the command if applicable and defined otherwise returns None"""
		return None

	@property
	def z(self) -> Union[int, float, None]:
		"""return the z coordinate of the command if applicable and defined otherwise returns None"""
		return None


class GCodeMove(BaseGCodeCommand):
	"""Container to hold G0 and G1 commands so that they can be moved in space."""
	def __init__(self, command: str):
		# define all empty variables
		self.e = None
		self.f = None
		self._x = None
		self._y = None
		self._z = None
		self.comment = None

		# parse the command
		comment_location = command.find(';')
		if comment_location != -1:
			self.comment = command[comment_location:]
			command = command[:comment_location]
		command = command.rstrip()

		command_split = command.split(' ')
		self.command = command_split[0]
		for arg in command_split[1:]:
			if arg.startswith('E'):
				self.e = float(arg[1:])
			elif arg.startswith('F'):
				self.f = float(arg[1:])
			elif arg.startswith('X'):
				self._x = float(arg[1:])
			elif arg.startswith('Y'):
				self._y = float(arg[1:])
			elif arg.startswith('Z'):
				self._z = float(arg[1:])
			else:
				print(f'Unknown argument "{arg}". Skipping it')

	def move(self, dx: Union[int, float], dy: Union[int, float]):
		"""Move the X and Y coordinates of the command by offset dx and dy"""
		if self.x is not None:
			self._x += dx
		if self.y is not None:
			self._y += dy

	@property
	def output(self) -> str:
		"""Return the command in string form"""
		command = self.command
		for arg_key, arg in (('E', self.e), ('F', self.f), ('X', self.x), ('Y', self.y), ('Z', self.z)):
			if arg is not None:
				command += f' {arg_key}{round(arg,3)}'
		if self.comment is not None:
			command += f' {self.comment}'
		return command + '\n'

	@property
	def x(self) -> Union[int, float, None]:
		"""return the x coordinate of the command if defined otherwise returns None"""
		return self._x

	@property
	def y(self) -> Union[int, float, None]:
		"""return the y coordinate of the command if defined otherwise returns None"""
		return self._y

	@property
	def z(self) -> Union[int, float, None]:
		"""return the z coordinate of the command if defined otherwise returns None"""
		return self._z


class GCodeMisc(BaseGCodeCommand):
	"""Container to hold all other commands to make exporting back out easier."""
	def __init__(self, command: str):
		self.command = command

	@property
	def output(self) -> str:
		"""Return the command in string form"""
		return self.command + '\n'


if __name__ == '__main__':
	# load all the needed files and call the run function
	with open('options.json') as _f:
		_options = json.load(_f)
	with open('print_order.txt') as _f:
		_file_list = [file_path.replace('\r', '').replace('\n', '') for file_path in _f.readlines()]
	with open('pre.gcode') as _f:
		_pre_gcode = _f.read()
	with open('mid.gcode') as _f:
		_mid_gcode = _f.read()
	with open('post.gcode') as _f:
		_post_gcode = _f.read()
	with open('output.gcode', 'w') as _save_file:
		run(_options, _file_list, _save_file, _pre_gcode, _mid_gcode, _post_gcode)
