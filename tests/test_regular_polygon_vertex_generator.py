from unittest import TestCase
import single_image
from single_image import regular_polygon_vertex_generator

class TestRegular_polygon_vertex_generator(TestCase):
    def test_regular_polygon_vertex_generator(self):

        square = regular_polygon_vertex_generator(4,1)
        TestCase()
        print(square)
        hex = regular_polygon_vertex_generator(6,1)
        print(hex)
        self.assertEqual(len(square), 4)
        self.assertEqual((0,0), square[0])
        self.assertEqual((0,1), square[1])
        self.assertEqual((1,0), square[2])
        self.assertEqual((1,1,), square[3])

        square2 = regular_polygon_vertex_generator(4, 4, 100, 57)
        self.assertEqual(len(square), 4)
        self.assertEqual((100,57), square2[0])

        triangle = regular_polygon_vertex_generator(3, 10)
        self.assertEqual(len(triangle), 3)
        self.assertEqual((00,00), triangle[0])

        #add cases for angled polygons


        #Throw exception for 1 or 2 sided shapes
        # self.fail()
