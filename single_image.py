import math
import numpy as np
from PIL import Image, ImageFilter, ImageFile, ImageDraw, ImageChops
#import pgmagick
from scipy import ndimage
import cv2
import argparse
import os
from os import path
import datetime


def _regular_polygon_vertex_generator_helper(sides, center, radius, index):
    """
    Determines the the coordinates of a particular vertice of a polygon

    :param sides: Amount of sides in the polygon
    :param center: The center point of the polygon
    :param radius: The radius of the polygon
    :param index: Which vertex in being determined
    :return: (x, y) corrdinate tuple
    """
    x = radius * math.cos(2 * math.pi * index / sides) + center[0]
    y = radius * math.sin(2 * math.pi * index / sides) + center[1]
    return (x,y)

#TODO: implement the ability to change the angle of the crop
def regular_polygon_vertex_generator( sides, side_length, x=0, y=0, angle=0):
    """
    Creates a list of coordinate points corresponding to the vertices of a polygon

    :param sides: Amount of sides of a polygon
    :param side_length: The length of each side of a polygon
    :param individual_angle: The angle of the polygon ____
    :param x: the offset of the array along the X axis
    :param y: the offset of the array along the Y axis
    :return: A list of (x, y) coordinate tuples
    """
    total_interior_angle = 180*(sides -2)
    individual_angle = total_interior_angle / sides
    # We create a tangent intersecting the midpoint of the polygon by splitting any angle down the middle
    theta = individual_angle / 2
    # center = (midpoint, midpoint)
    radius = side_length / (2 * math.cos(theta))
    # midpoint = radius * math.acos(side_length /2 / radius)
    midpoint = (x, y)
    vertex_list = []
    for i in range(sides):
        vertex_list.append(_regular_polygon_vertex_generator_helper(sides, midpoint, radius, i))
    return vertex_list

class SingleImage:
    def __init__(self, path):
        self.path = path
        self.image = Image.open(path)
        self.shape_sides = 4
        self.width = self.image.getbbox()[2]
        self.height = self.image.getbbox()[3]

    def show(self):
        self.image.show()

    def polygon_crop(self, sides, side_length, x=0, y=0):

        polygon = regular_polygon_vertex_generator(sides, side_length, x, y)
        mask, mask_arr = self._mask_from_polygon(polygon)
        self.image.putalpha(mask)

        image_array = np.asarray(self.image)

        # assemble new image (uint8: 0-255)
        newImArray = np.empty(image_array.shape, dtype='uint8')
        # colors (three first columns, RGB)
        newImArray[:,:,:3] = image_array[:,:,:3]
        # transparency (4th column)
        newImArray[:,:,3] = mask_arr*255
        # back to Image from numpy
        newIm = Image.fromarray(newImArray, "RGBA")

        target_dir = "images/working_images/poly_cropped"
        if not path.exists(target_dir):
            os.mkdir(target_dir)

        target_path = "images/working_images/poly_cropped"+ '/' + str(hash(self))  + str(datetime.datetime.now().isoformat().replace('.','-').replace(':','_'))+ '.png'
        newIm.save(target_path)
        self.image = Image.open(target_path)
        self.path = target_path
        # return self.image

    def _mask_from_polygon(self, polygon):

        poly_img = Image.new('L', (self.width, self.height), 255)
        ImageDraw.Draw(poly_img).polygon(polygon, outline=1, fill=1)
        mask_arr = np.array(poly_img)
        return Image.fromarray(mask_arr), mask_arr


if True:
    a = SingleImage('images/starting_images/palm_trees.jpg')
    a.polygon_crop(6, 500,500,500)
