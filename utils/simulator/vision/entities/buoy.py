
from math import pi, radians
from itertools import izip
import numpy

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

from base import Entity, Container


class BuoyEntity(Entity):

    def __init__(self, *args, **kwargs):
        """
         pos, color=(0.5, 0.5, 0.5), yaw=0, pitch=0, roll=0):
        ARGS:
            * pos: list of format [x,y,z] specifying the location of the buoy
            group/array/entity. 
            * color: ???
            * yaw: z-axis rotation of the buoys entity
            * pitch: y-axis rotation of the buoys entity
            * roll: x-axis rotation of the buoys entity

        KWARGS:
            * pos_<color>: the XYZ position of a buoy entity.
            <color> can be red, green, or yellow.
        """
        # pop off class specific keyword arguments first
        pos_red = numpy.array(kwargs.pop("pos_red", (0, 0, 0)))
        pos_green = numpy.array(kwargs.pop("pos_green", (0, 0, 0)))
        pos_yellow = numpy.array(kwargs.pop("pos_yellow", (0, 0, 0)))

        # inherit base class
        super(BuoyEntity, self).__init__(*args, **kwargs)

        # visual parameters
        self.positions = [
            pos_red,
            pos_green,
            pos_yellow,
        ]
        self.colors = [
            (1, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
        ]
        self.color_names = ("red", "green", "yellow")

        # internal buoy tracking variables
        self.buoys = []
        self.id_counter = 0
        
        # generate output container
        self.output = Container()
        self.output.buoys = []


    def draw(self):
        self.pre_draw()
        glMatrixMode(GL_MODELVIEW)

        for pos, color in izip(self.positions, self.colors):
            glColor(color)
            glPushMatrix()
            glTranslate(*pos)
            glutSolidSphere(0.75, 8, 8)  # 9 inch diameter
            glPopMatrix()

        self.post_draw()

    def find(self, robot):

        self.buoys = filter(lambda x: x.found, self.buoys)
        for buoy in self.buoys:
            buoy.found = False

        new_buoys = []
        for pos, color in izip(self.positions, self.color_names):
            absolute_pos = self.absolute_point(pos)
            theta, phi = robot.find_point("forward", absolute_pos)
            dist = numpy.linalg.norm(absolute_pos - robot.pos)
            if dist > 6 and dist < 25 and \
                    theta != None and \
                    phi != None:
                theta *= robot.get_camera_fov("forward", vertical=False) / 2
                phi *= robot.get_camera_fov("forward", vertical=True) / 2

                # Find existing bouy with similar theta and phi
                similar_buoy_found = False
                for buoy in self.buoys:
                    if buoy.color == color:
                        similar_buoy_found = True

                        buoy.found = True
                        buoy.theta = theta
                        buoy.phi = phi
                        buoy.r = dist

                        break

                # Create new buoy
                if not similar_buoy_found:
                    buoy = Container()
                    buoy.found = True
                    buoy.theta = theta
                    buoy.phi = phi
                    buoy.r = dist
                    buoy.color = color
                    buoy.id = self.id_counter
                    self.id_counter += 1

                    new_buoys.append(buoy)
        self.buoys.extend(new_buoys)

        # Copy self.buoys to self.output.buoys
        buoy_found = False
        self.output.buoys = []
        for buoy in self.buoys:
            if buoy.found:
                buoy_found = True
                self.output.buoys.append(buoy)
        return buoy_found, self.output
