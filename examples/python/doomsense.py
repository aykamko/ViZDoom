#!/usr/bin/env python

#####################################################################
# This script presents how to use the most basic features of the environment.
# It configures the engine, and makes the agent perform random actions.
# It also gets current state and reward earned with the action.
# <episodes> number of episodes are played.
# Random combination of buttons is chosen for every action.
# Game variables from state and last reward are printed.
#
# To see the scenario description go to "../../scenarios/README.md"
#####################################################################

from __future__ import print_function

from vizdoom import *

from random import choice
from time import sleep
import os
import ctypes
import serial, time
import numpy as np
import sys
import gflags
import signal
import math

NUM_COINS = 4

gflags.DEFINE_boolean('nucleo', True, 'send to nucleo through serial')
gflags.DEFINE_string('serialport', '/dev/tty.usbmodem1423', 'serial port to write messages')
gflags.DEFINE_integer('baud', 115200, 'baudrate')

FLAGS = gflags.FLAGS
FLAGS(sys.argv)  # parses flags

class DoomState(ctypes.Structure):
  _fields_ = [
    ("heart", ctypes.c_float),
    ("ammo", ctypes.c_float),
    ("coins", ctypes.c_float * NUM_COINS),
  ]

  def __str__(self):
      d = {
          'heart': self.heart,
          'ammo': self.ammo,
          'coins': list(np.frombuffer(self.coins, dtype=np.float32, count=NUM_COINS)),
      }
      return str(d)

ser = None
game = None

def signal_handler(*_):
    print('Pressed Ctrl+C, exiting!')
    if ser and ser.isOpen():
      # reset all motors
      doomstate_struct = DoomState(
          1.0, 1.0,
          (ctypes.c_float * NUM_COINS)(0.0, 0.0, 0.0, 0.0),
      )
      struct_str = ctypes.string_at(ctypes.addressof(doomstate_struct),
                                    ctypes.sizeof(doomstate_struct))
      ser.write(struct_str)
      ser.flush()
      ser.close()
    game.close()
    sys.exit(0)

# Nucleo setup (http://stackoverflow.com/q/25662489)
if FLAGS.nucleo:
  try:
      ser = serial.Serial(FLAGS.serialport, FLAGS.baud)
      ser.bytesize = serial.EIGHTBITS
      ser.parity = serial.PARITY_NONE #set parity check: no parity
      ser.stopbits = serial.STOPBITS_ONE #number of stop bits
      ser.timeout = None
  except serial.serialutil.SerialException:
      print('*****************************')
      print('ATTENTION: NUCLEO NOT CONNECTED VIA SERIAL!!!')
      print("COULDN'T OPEN PORT AT {}".format(FLAGS.serialport))
      print('*****************************')
      exit(1)

# Create DoomGame instance. It will run the game and communicate with you.
game = DoomGame()

# Now it's time for configuration!
# load_config could be used to load configuration instead of doing it here with code.
# If load_config is used in-code configuration will work. Note that the most recent changes will add to previous ones.
# game.load_config("../../examples/config/basic.cfg")

VIZDOOM_HOME = os.getenv('VIZDOOM_HOME') or '/Users/Aleks/lib/ViZDoom'

# Sets path to ViZDoom engine executive which will be spawned as a separate process. Default is "./vizdoom".
game.set_vizdoom_path(VIZDOOM_HOME+"/bin/vizdoom")

# Sets path to iwad resource file which contains the actual doom game. Default is "./doom2.wad".
game.set_doom_game_path(VIZDOOM_HOME+"/scenarios/freedoom2.wad")
# game.set_doom_game_path("../../scenarios/doom2.wad")  # Not provided with environment due to licences.

# Sets path to additional resources wad file which is basically your scenario wad.
# If not specified default maps will be used and it's pretty much useless... unless you want to play good old Doom.

game.set_doom_scenario_path(VIZDOOM_HOME+"/scenarios/basic.wad")
# game.set_doom_scenario_path(VIZDOOM_HOME+"/scenarios/defend_the_center.wad")

# Sets map to start (scenario .wad files can contain many maps).
game.set_doom_map("map01")
# game.set_doom_map("map03")

# Sets resolution. Default is 320X240
game.set_screen_resolution(ScreenResolution.RES_640X480)
# game.set_screen_resolution(ScreenResolution.RES_1600X1200)

# Enables labeling of in game objects labeling.
game.set_labels_buffer_enabled(True)

# Sets other rendering options
game.set_render_hud(True)
game.set_render_minimal_hud(False) # If hud is en105abled
game.set_render_crosshair(True)
game.set_render_weapon(True)
game.set_render_decals(True)
game.set_render_particles(True)
game.set_render_effects_sprites(True)

# Adds buttons that will be allowed.
for name in Button.names.keys():
    game.add_available_button(getattr(Button, name))

# Adds game variables that will be included in state.
game.add_available_game_variable(GameVariable.AMMO2)
game.add_available_game_variable(GameVariable.HEALTH)
game.set_automap_mode(AutomapMode.OBJECTS)

# Causes episodes to finish after 200 tics (actions)
game.set_episode_timeout(2000000)

# Makes episodes start after 10 tics (~after raising the weapon)
game.set_episode_start_time(10)

# Makes the window appear (turned on by default)
game.set_window_visible(True)

# Turns on the sound. (turned off by default)
game.set_sound_enabled(True)

# Sets the livin reward (for each move) to -1
game.set_living_reward(-1)

# Sets ViZDoom mode (PLAYER, ASYNC_PLAYER, SPECTATOR, ASYNC_SPECTATOR, PLAYER mode is default)
game.set_mode(Mode.ASYNC_SPECTATOR)

# Initialize the game. Further configuration won't take any effect from now on.
game.init()

# Define some actions. Each list entry corresponds to declared buttons:
# MOVE_LEFT, MOVE_RIGHT, ATTACK
# 5 more combinations are naturally possible but only 3 are included for transparency when watching.

# Run this many episodes

# Sets time that will pause the engine after each action (in seconds)
# Without this everything would go too fast for you to keep track of what's happening.
sleep_time = 1 / DEFAULT_TICRATE # = 0.028

# have to set handler here otherwise vizdoom has its own
signal.signal(signal.SIGINT, signal_handler)

def heart(x, health):
  health = min(health, 100)

  r = (((100 - health) * (20 - 5)) / 100) + 5
  motor_value = abs(math.cos(x * r) + math.sin(x * (r*2))) / 1.8

  health_scale = max(0.3, (100 - health) / 100.0)

  return 1.0 - motor_value * health_scale

heart_time = 0
i = 0
while True:
    print("Episode #" + str(i + 1))

    try:
      # Starts a new episode. It is not needed right after init() but it doesn't cost much. At least the loop is nicer.
      game.new_episode()

      while not game.is_episode_finished():

          # Gets the state
          state = game.get_state()

          # Which consists of:
          n           = state.number
          vars        = state.game_variables
          labels      = state.labels

          game.advance_action()

          vars_dict = {'ammo': vars[0], 'health': vars[1]}

          MIN_DIST = 135.0
          MAX_DIST = 375.0 * 2
          demon_labels = labels
          demon_labels.sort(key=lambda d: d.distance) # sort by distance
          demon_labels = filter(lambda d: d.distance < MAX_DIST, demon_labels) # filter by distance
          demon_labels.sort(key=lambda d: d.angle) # sort by angle

          neck_activations = {
            0: {'dist': 10000, 'pwr': 0.0},
            1: {'dist': 10000, 'pwr': 0.0},
            2: {'dist': 10000, 'pwr': 0.0},
            3: {'dist': 10000, 'pwr': 0.0},
          }
          for d in demon_labels:
            activations = []
            # if 195 < d.angle < 255:
            if 195 < d.angle < 300:
              activations.append(neck_activations[3])
            # if 165 < d.angle < 225:
            if 165 < d.angle < 225:
              activations.append(neck_activations[2])
            # if 135 < d.angle < 195:
            if 135 < d.angle < 195:
              activations.append(neck_activations[1])
            # if 105 < d.angle < 165:
            if 60 < d.angle < 165:
              activations.append(neck_activations[0])

            for activation in activations:
              if d.distance > activation['dist']:
                continue
              norm_dist = (max(MIN_DIST, d.distance) - MAX_DIST) / (MIN_DIST - MAX_DIST)
              activation['pwr'] = (norm_dist * 1.0) ** 4
          neck_activations = [neck_activations[i]['pwr'] for i in range(4)]

          doomstate_struct = DoomState(
              heart(time.time(), vars_dict['health']),
              vars_dict['ammo'] / 50.0,
              (ctypes.c_float * NUM_COINS)(*neck_activations),
          )
          struct_str = ctypes.string_at(ctypes.addressof(doomstate_struct),
                                        ctypes.sizeof(doomstate_struct))
          print(doomstate_struct)

          if ser and ser.isOpen():
              ser.write(struct_str)
              ser.flush()

          print("State #" + str(n))
          print("Game variables:", vars_dict)
          print("Ammo proportion: {}".format(vars_dict['ammo'] / 50.0))
          # for label in labels:
          #     print("Demon angle: %f, distance: %f" % (label.angle, label.distance))
          print("=====================")

          if sleep_time > 0:
              sleep(sleep_time)

      print("************************")
      i += 1

    except ViZDoomUnexpectedExitException:
      signal_handler(None, None)
