import os
from functools import reduce
from math import isclose, pi

import numpy as np

from PartSegImage import Image
from PartSegCore.analysis import load_metadata
from PartSegCore.analysis.measurement_calculation import Diameter, PixelBrightnessSum, Volume, ComponentsNumber, \
    MaximumPixelBrightness, MinimumPixelBrightness, MeanPixelBrightness, MedianPixelBrightness, \
    StandardDeviationOfPixelBrightness, MomentOfInertia, LongestMainAxisLength, MiddleMainAxisLength, \
    ShortestMainAxisLength, Surface, RimVolume, RimPixelBrightnessSum, MeasurementProfile, Sphericity, \
    DistanceMaskSegmentation, DistancePoint, ComponentsInfo, MeasurementResult, SplitOnPartVolume, \
    SplitOnPartPixelBrightnessSum
from PartSegCore.analysis.measurement_base import Node, MeasurementEntry, PerComponent, AreaType
from PartSegCore.autofit import density_mass_center
from PartSegCore.universal_const import UNIT_SCALE, Units


def get_cube_array():
    data = np.zeros((1, 50, 100, 100, 1), dtype=np.uint16)
    data[0, 10:40, 20:80, 20:80] = 50
    data[0, 15:35, 30:70, 30:70] = 70
    return data


def get_cube_image():
    return Image(get_cube_array(), (100, 50, 50), "")


def get_square_image():
    return Image(get_cube_array()[:, 25:26], (100, 50, 50), "")


def get_two_components_array():
    data = np.zeros((1, 20, 30, 60, 1), dtype=np.uint16)
    data[0, 3:-3, 2:-2, 2:19] = 60
    data[0, 3:-3, 2:-2, 22:-2] = 50
    return data


def get_two_components_image():
    return Image(get_two_components_array(), (100, 50, 50), "")


def get_two_component_mask():
    mask = np.zeros(get_two_components_image().get_channel(0).shape[1:], dtype=np.uint8)
    mask[3:-3, 2:-2, 2:-2] = 1
    return mask


class TestDiameter(object):
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert Diameter.calculate_property(mask1, image.spacing, 1) == np.sqrt(2 * (50 * 59) ** 2 + (100 * 29) ** 2)
        assert Diameter.calculate_property(mask2, image.spacing, 1) == np.sqrt(2 * (50 * 39) ** 2 + (100 * 19) ** 2)
        assert Diameter.calculate_property(mask3, image.spacing, 1) == np.sqrt(2 * (50 * 59) ** 2 + (100 * 29) ** 2)

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert Diameter.calculate_property(mask1, image.spacing, 1) == np.sqrt(2 * (50 * 59) ** 2)
        assert Diameter.calculate_property(mask2, image.spacing, 1) == np.sqrt(2 * (50 * 39) ** 2)
        assert Diameter.calculate_property(mask3, image.spacing, 1) == np.sqrt(2 * (50 * 59) ** 2)

    def test_scale(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        assert isclose(Diameter.calculate_property(mask1, image.spacing, 2),
                       2 * np.sqrt(2 * (50 * 59) ** 2 + (100 * 29) ** 2))
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        assert isclose(Diameter.calculate_property(mask1, image.spacing, 2), 2 * np.sqrt(2 * (50 * 59) ** 2))

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        assert Diameter.calculate_property(mask, image.spacing, 1) == 0


class TestPixelBrightnessSum(object):
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert PixelBrightnessSum.calculate_property(mask1,
                                                     image.get_channel(0)) == 30 * 60 * 60 * 50 + 20 * 40 * 40 * 20
        assert PixelBrightnessSum.calculate_property(mask2, image.get_channel(0)) == 20 * 40 * 40 * 70
        assert PixelBrightnessSum.calculate_property(mask3, image.get_channel(0)) == (30 * 60 * 60 - 20 * 40 * 40) * 50

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert PixelBrightnessSum.calculate_property(mask1, image.get_channel(0)) == 60 * 60 * 50 + 40 * 40 * 20
        assert PixelBrightnessSum.calculate_property(mask2, image.get_channel(0)) == 40 * 40 * 70
        assert PixelBrightnessSum.calculate_property(mask3, image.get_channel(0)) == (60 * 60 - 40 * 40) * 50

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert PixelBrightnessSum.calculate_property(mask, image.get_channel(0)) == 0


class TestVolume(object):
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = mask1 * ~mask2
        assert Volume.calculate_property(mask1, image.spacing, 1) == (100 * 30) * (50 * 60) * (50 * 60)
        assert Volume.calculate_property(mask2, image.spacing, 1) == (100 * 20) * (50 * 40) * (50 * 40)
        assert Volume.calculate_property(mask3, image.spacing, 1) == (100 * 30) * (50 * 60) * (50 * 60) -\
                                                                     (100 * 20) * (50 * 40) * (50 * 40)

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = mask1 * ~mask2
        assert Volume.calculate_property(mask1, image.spacing, 1) == (50 * 60) * (50 * 60)
        assert Volume.calculate_property(mask2, image.spacing, 1) == (50 * 40) * (50 * 40)
        assert Volume.calculate_property(mask3, image.spacing, 1) == (50 * 60) * (50 * 60) - (50 * 40) * (50 * 40)

    def test_scale(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        assert Volume.calculate_property(mask1, image.spacing, 2) == 2 ** 3 * (100 * 30) * (50 * 60) * (50 * 60)

        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        assert Volume.calculate_property(mask1, image.spacing, 2) == 2 ** 2 * (50 * 60) * (50 * 60)

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert Volume.calculate_property(mask, image.spacing, 1) == 0


class TestComponentsNumber(object):
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        assert ComponentsNumber.calculate_property(mask1) == 1
        assert ComponentsNumber.calculate_property(mask2) == 1
        assert ComponentsNumber.calculate_property(image.get_channel(0)) == 2

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        assert ComponentsNumber.calculate_property(mask1) == 1
        assert ComponentsNumber.calculate_property(mask2) == 1
        assert ComponentsNumber.calculate_property(image.get_channel(0)) == 2

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert ComponentsNumber.calculate_property(mask) == 0


class TestMaximumPixelBrightness:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = mask1 * ~mask2
        assert MaximumPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 70
        assert MaximumPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MaximumPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 50

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = mask1 * ~mask2
        assert MaximumPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 70
        assert MaximumPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MaximumPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 50

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert MaximumPixelBrightness.calculate_property(mask, image.get_channel(0)) == 0


class TestMinimumPixelBrightness:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MinimumPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 50
        assert MinimumPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MinimumPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 0

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MinimumPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 50
        assert MinimumPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MinimumPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 0

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert MinimumPixelBrightness.calculate_property(mask, image.get_channel(0)) == 0


class TestMedianPixelBrightness:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MedianPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 50
        assert MedianPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MedianPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 0

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MedianPixelBrightness.calculate_property(mask1, image.get_channel(0)) == 50
        assert MedianPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MedianPixelBrightness.calculate_property(mask3, image.get_channel(0)) == 0

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert MedianPixelBrightness.calculate_property(mask, image.get_channel(0)) == 0


class TestMeanPixelBrightness:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MeanPixelBrightness.calculate_property(mask1, image.get_channel(0)) == \
            (30 * 60 * 60 * 50 + 20 * 40 * 40 * 20) / (30 * 60 * 60)
        assert MeanPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MeanPixelBrightness.calculate_property(mask3, image.get_channel(0)) == \
            (30 * 60 * 60 * 50 + 20 * 40 * 40 * 20) / (50 * 100 * 100)

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        assert MeanPixelBrightness.calculate_property(mask1, image.get_channel(0)) == \
            (60 * 60 * 50 + 40 * 40 * 20) / (60 * 60)
        assert MeanPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 70
        assert MeanPixelBrightness.calculate_property(mask3, image.get_channel(0)) == \
            (60 * 60 * 50 + 40 * 40 * 20) / (100 * 100)

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert MeanPixelBrightness.calculate_property(mask, image.get_channel(0)) == 0


class TestStandardDeviationOfPixelBrightness:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        mean = (30 * 60 * 60 * 50 + 20 * 40 * 40 * 20) / (30 * 60 * 60)
        assert StandardDeviationOfPixelBrightness.calculate_property(mask1, image.get_channel(0)) == \
            np.sqrt(((30 * 60 * 60 - 20 * 40 * 40) * (50 - mean) ** 2 + ((20 * 40 * 40) * (70 - mean) ** 2)) / (
                       30 * 60 * 60))

        assert StandardDeviationOfPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 0
        mean = (30 * 60 * 60 * 50 + 20 * 40 * 40 * 20) / (50 * 100 * 100)
        assert isclose(StandardDeviationOfPixelBrightness.calculate_property(mask3, image.get_channel(0)),
                       np.sqrt(((30 * 60 * 60 - 20 * 40 * 40) * (50 - mean) ** 2 + ((20 * 40 * 40) * (70 - mean) ** 2) +
                                (50 * 100 * 100 - 30 * 60 * 60) * mean ** 2) / (50 * 100 * 100)))

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0) > 40
        mask2 = image.get_channel(0) > 60
        mask3 = image.get_channel(0) >= 0
        mean = (60 * 60 * 50 + 40 * 40 * 20) / (60 * 60)
        assert StandardDeviationOfPixelBrightness.calculate_property(mask1, image.get_channel(0)) == \
            np.sqrt(((60 * 60 - 40 * 40) * (50 - mean) ** 2 + ((40 * 40) * (70 - mean) ** 2)) / (60 * 60))

        assert StandardDeviationOfPixelBrightness.calculate_property(mask2, image.get_channel(0)) == 0
        mean = (60 * 60 * 50 + 40 * 40 * 20) / (100 * 100)
        assert isclose(StandardDeviationOfPixelBrightness.calculate_property(mask3, image.get_channel(0)),
                       np.sqrt(((60 * 60 - 40 * 40) * (50 - mean) ** 2 + ((40 * 40) * (70 - mean) ** 2) +
                                (100 * 100 - 60 * 60) * mean ** 2) / (100 * 100)))

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0) > 80
        assert StandardDeviationOfPixelBrightness.calculate_property(mask, image.get_channel(0)) == 0


class TestMomentOfInertia:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = image.get_channel(0)[0] >= 0
        in1 = MomentOfInertia.calculate_property(mask1, image.get_channel(0), image.spacing)
        in2 = MomentOfInertia.calculate_property(mask2, image.get_channel(0), image.spacing)
        in3 = MomentOfInertia.calculate_property(mask3, image.get_channel(0), image.spacing)
        assert in1 == in3
        assert in1 > in2

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = image.get_channel(0)[0] >= 0
        in1 = MomentOfInertia.calculate_property(mask1, image.get_channel(0), image.spacing)
        in2 = MomentOfInertia.calculate_property(mask2, image.get_channel(0), image.spacing)
        in3 = MomentOfInertia.calculate_property(mask3, image.get_channel(0), image.spacing)
        assert in1 == in3
        assert in1 > in2

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        assert MomentOfInertia.calculate_property(mask, image.get_channel(0), image.spacing) == 0

    def test_values(self):
        spacing = (10, 6, 6)
        image_array = np.zeros((10, 16, 16))
        mask = np.ones(image_array.shape)
        image_array[5, 8, 8] = 1
        assert MomentOfInertia.calculate_property(mask, image_array, spacing) == 0
        image_array[5, 8, 9] = 1
        assert MomentOfInertia.calculate_property(mask, image_array, spacing) == (0.5 * 6) ** 2 * 2
        image_array = np.zeros((10, 16, 16))
        image_array[5, 8, 8] = 1
        image_array[5, 10, 8] = 3
        assert MomentOfInertia.calculate_property(mask, image_array, spacing) == 9 ** 2 + 3 ** 2 * 3
        image_array = np.zeros((10, 16, 16))
        image_array[5, 6, 8] = 3
        image_array[5, 10, 8] = 3
        assert MomentOfInertia.calculate_property(mask, image_array, spacing) == 3 * 2 * 12 ** 2

    def test_density_mass_center(self):
        spacing = (10, 6, 6)
        image_array = np.zeros((10, 16, 16))
        image_array[5, 8, 8] = 1
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 48, 48)))
        image_array[5, 9, 8] = 1
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 51, 48)))
        image_array[5, 8:10, 9] = 1
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 51, 51)))
        image_array = np.zeros((10, 16, 16))
        image_array[2, 5, 5] = 1
        image_array[8, 5, 5] = 1
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 30, 30)))
        image_array = np.zeros((10, 16, 16))
        image_array[3:8, 4:13, 4:13] = 1
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 48, 48)))
        image_array = np.zeros((10, 16, 16))
        image_array[5, 8, 8] = 1
        image_array[5, 10, 8] = 3
        assert np.all(np.array(density_mass_center(image_array, spacing)) == np.array((50, 57, 48)))
        assert np.all(np.array(density_mass_center(image_array[5], spacing[1:])) == np.array((57, 48)))
        assert np.all(np.array(density_mass_center(image_array[5:6], spacing)) == np.array((0, 57, 48)))


class TestMainAxis:
    def test_cube(self):
        array = get_cube_array()
        image = Image(array, (10, 10, 20))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        assert LongestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 20 * 59
        assert MiddleMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 59
        assert ShortestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 29
        assert LongestMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 20 * 39
        assert MiddleMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 39
        assert ShortestMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 19

    def test_square(self):
        array = get_cube_array()
        image = Image(array[:, 25:26], (10, 10, 20))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        assert LongestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 20 * 59
        assert MiddleMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 59
        assert ShortestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 0
        assert LongestMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 20 * 39
        assert MiddleMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 39
        assert ShortestMainAxisLength.calculate_property(
            area_array=mask2, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 0

    def test_scale(self):
        array = get_cube_array()
        image = Image(array, (10, 10, 20))
        mask1 = image.get_channel(0)[0] > 40
        assert LongestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=2,
            _area=AreaType.Mask
        ) == 2 * 20 * 59

        array = get_cube_array()
        image = Image(array[:, 25:26], (10, 10, 20))
        mask1 = image.get_channel(0)[0] > 40
        assert LongestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), help_dict={}, voxel_size=image.spacing, result_scalar=2,
            _area=AreaType.Mask
        ) == 2 * 20 * 59

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        assert ShortestMainAxisLength.calculate_property(area_array=mask, channel=image.get_channel(0), help_dict={},
                                                         voxel_size=image.spacing, result_scalar=1,
                                                         _area=AreaType.Segmentation) == 0

    def test_without_help_dict(self):
        array = get_cube_array()
        image = Image(array, (10, 10, 20))
        mask1 = image.get_channel(0)[0] > 40
        assert LongestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 20 * 59
        assert MiddleMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 59
        assert ShortestMainAxisLength.calculate_property(
            area_array=mask1, channel=image.get_channel(0), voxel_size=image.spacing, result_scalar=1,
            _area=AreaType.Mask
        ) == 10 * 29


class TestSurface:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert Surface.calculate_property(mask1, image.spacing, 1) == 6 * (60 * 50) ** 2
        assert Surface.calculate_property(mask2, image.spacing, 1) == 6 * (40 * 50) ** 2
        assert Surface.calculate_property(mask3, image.spacing, 1) == 6 * (60 * 50) ** 2 + 6 * (40 * 50) ** 2

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert Surface.calculate_property(mask1, image.spacing, 1) == 4 * (60 * 50)
        assert Surface.calculate_property(mask2, image.spacing, 1) == 4 * (40 * 50)
        assert Surface.calculate_property(mask3, image.spacing, 1) == 4 * (60 * 50) + 4 * (40 * 50)

    def test_scale(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        assert Surface.calculate_property(mask1, image.spacing, 3) == 3 ** 2 * 6 * (60 * 50) ** 2

        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        assert Surface.calculate_property(mask1, image.spacing, 3) == 3 * 4 * (60 * 50)

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        assert Surface.calculate_property(mask, image.spacing, 1) == 0


class TestRimVolume:
    def test_cube(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == \
            np.count_nonzero(mask3) * result_scale
        assert RimVolume.calculate_property(segmentation=mask2, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == 0

    def test_square(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == \
            np.count_nonzero(mask3) * result_scale
        assert RimVolume.calculate_property(segmentation=mask2, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == 0

    def test_scale(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)
        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == \
            np.count_nonzero(mask3) * result_scale
        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=UNIT_SCALE[Units.nm.value], distance=10 * 50,
                                            units=Units.nm) == np.count_nonzero(mask3) * 100 * 50 ** 2

        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)
        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=1, distance=10 * 50, units=Units.nm) == \
            np.count_nonzero(mask3) * result_scale
        assert RimVolume.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=UNIT_SCALE[Units.nm.value], distance=10 * 50,
                                            units=Units.nm) == np.count_nonzero(mask3) * 50 ** 2

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        mask1 = image.get_channel(0)[0] > 40
        assert RimVolume.calculate_property(segmentation=mask1, mask=mask, voxel_size=image.voxel_size,
                                            result_scalar=UNIT_SCALE[Units.nm.value], distance=10 * 50,
                                            units=Units.nm) == 0
        assert RimVolume.calculate_property(segmentation=mask, mask=mask1, voxel_size=image.voxel_size,
                                            result_scalar=UNIT_SCALE[Units.nm.value], distance=10 * 50,
                                            units=Units.nm) == 0
        assert RimVolume.calculate_property(segmentation=mask, mask=mask, voxel_size=image.voxel_size,
                                            result_scalar=UNIT_SCALE[Units.nm.value], distance=10 * 50,
                                            units=Units.nm) == 0


class TestRimPixelBrightnessSum:
    def test_cube(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                                        distance=10 * 50, units=Units.nm, channel=image.get_channel(0)
                                                        ) == np.count_nonzero(mask3) * 50
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask2, mask=mask1, voxel_size=image.voxel_size,
                                                        distance=10 * 50, units=Units.nm,
                                                        channel=image.get_channel(0)) == 0

    def test_square(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask1, mask=mask1, voxel_size=image.voxel_size,
                                                        distance=10 * 50, units=Units.nm, channel=image.get_channel(0)
                                                        ) == np.count_nonzero(mask3) * 50
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask2, mask=mask1, voxel_size=image.voxel_size,
                                                        distance=10 * 50, units=Units.nm,
                                                        channel=image.get_channel(0)) == 0

    def test_empty(self):
        image = get_cube_image()
        mask = image.get_channel(0)[0] > 80
        mask1 = image.get_channel(0)[0] > 40
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask1, mask=mask, voxel_size=image.voxel_size,
                                                        distance=10 * 50, channel=image.get_channel(0),
                                                        units=Units.nm) == 0
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask, mask=mask1, voxel_size=image.voxel_size,
                                                        distance=10 * 50, channel=image.get_channel(0),
                                                        units=Units.nm) == 0
        assert RimPixelBrightnessSum.calculate_property(segmentation=mask, mask=mask, voxel_size=image.voxel_size,
                                                        distance=10 * 50, channel=image.get_channel(0),
                                                        units=Units.nm) == 0


class TestSphericity:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        mask1_radius = np.sqrt(2 * (50 * 59) ** 2 + (100 * 29) ** 2) / 2
        mask1_volume = np.count_nonzero(mask1) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask1, voxel_size=image.voxel_size, result_scalar=1),
                       mask1_volume / (4 / 3 * pi * mask1_radius ** 3))

        mask2_radius = np.sqrt(2 * (50 * 39) ** 2 + (100 * 19) ** 2) / 2
        mask2_volume = np.count_nonzero(mask2) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask2, voxel_size=image.voxel_size, result_scalar=1),
                       mask2_volume / (4 / 3 * pi * mask2_radius ** 3))

        mask3_radius = mask1_radius
        mask3_volume = np.count_nonzero(mask3) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask3, voxel_size=image.voxel_size, result_scalar=1),
                       mask3_volume / (4 / 3 * pi * mask3_radius ** 3))

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        mask3 = mask1 * ~mask2
        mask1_radius = np.sqrt(2 * (50 * 59) ** 2) / 2
        mask1_volume = np.count_nonzero(mask1) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask1, voxel_size=image.voxel_size, result_scalar=1),
                       mask1_volume / (pi * mask1_radius ** 2))

        mask2_radius = np.sqrt(2 * (50 * 39) ** 2) / 2
        mask2_volume = np.count_nonzero(mask2) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask2, voxel_size=image.voxel_size, result_scalar=1),
                       mask2_volume / (pi * mask2_radius ** 2))

        mask3_radius = mask1_radius
        mask3_volume = np.count_nonzero(mask3) * reduce(lambda x, y: x * y, image.voxel_size)
        assert isclose(Sphericity.calculate_property(area_array=mask3, voxel_size=image.voxel_size, result_scalar=1),
                       mask3_volume / (pi * mask3_radius ** 2))


class TestDistanceMaskSegmentation:
    def test_cube(self):
        image = get_cube_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Mass_center) == 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Mass_center,
                                                           DistancePoint.Geometrical_center) == 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Border,
                                                           DistancePoint.Geometrical_center) == 1400

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Border) == 900

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Border,
                                                           DistancePoint.Border) == 500

    def test_two_components(self):
        data = np.zeros((1, 30, 30, 60, 1), dtype=np.uint16)
        data[0, 5:-5, 5:-5, 5:29] = 60
        data[0, 5:-5, 5:-5, 31:-5] = 50
        image = Image(data, (100, 100, 50), "")
        mask = np.zeros(data.shape[1:-1], dtype=np.uint8)
        mask[2:-2, 2:-2, 2:-2] = 1

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                           image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 50, mask,
                                                           image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 650

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 60, mask,
                                                           image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 650

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 50, mask,
                                                           image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Mass_center) == 650

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 60, mask,
                                                           image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Mass_center) == 650

        assert isclose(
            DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                        image.voxel_size, 1, DistancePoint.Geometrical_center,
                                                        DistancePoint.Mass_center), 1300 * 6 / 11 - 650)

        assert isclose(
            DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                        image.voxel_size, 1, DistancePoint.Mass_center,
                                                        DistancePoint.Geometrical_center), 1300 * 6 / 11 - 650)

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                           image.voxel_size, 1, DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                           image.voxel_size, 1, DistancePoint.Border,
                                                           DistancePoint.Geometrical_center) == 1200

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                           image.voxel_size, 1, DistancePoint.Geometrical_center,
                                                           DistancePoint.Border) == 50

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0], mask,
                                                           image.voxel_size, 1, DistancePoint.Border,
                                                           DistancePoint.Border) == 150

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 50, mask,
                                                           image.voxel_size, 1, DistancePoint.Border,
                                                           DistancePoint.Border) == 150

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), image.get_channel(0)[0] == 60, mask,
                                                           image.voxel_size, 1, DistancePoint.Border,
                                                           DistancePoint.Border) == 150

    def test_square(self):
        image = get_square_image()
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 0
        mask3 = mask2.astype(np.uint8)
        mask3[:, 50:] = 2
        mask3[mask2 == 0] = 0

        assert DistanceMaskSegmentation.calculate_property(image.get_channel(0), mask2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 0

        assert DistanceMaskSegmentation.calculate_property(mask3, mask3 == 1, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 500

        assert DistanceMaskSegmentation.calculate_property(mask3, mask3 == 2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Geometrical_center) == 500

        assert DistanceMaskSegmentation.calculate_property(mask3, mask3 == 1, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Mass_center) == 500

        assert DistanceMaskSegmentation.calculate_property(mask3, mask3 == 2, mask1, image.voxel_size, 1,
                                                           DistancePoint.Geometrical_center,
                                                           DistancePoint.Mass_center) == 500

        assert isclose(DistanceMaskSegmentation.calculate_property(mask3, mask2, mask1, image.voxel_size, 1,
                                                                   DistancePoint.Geometrical_center,
                                                                   DistancePoint.Mass_center), 1000 * 2 / 3 - 500)


class TestSplitOnPartVolume:
    def test_cube_equal_radius(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)


        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (30*60*60 - 20*40*40)  * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (20 * 40 * 40 - 10 * 20 * 20) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (10 * 20 * 20) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (20 * 40 * 40 - 10 * 20 * 20) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (10 * 20 * 20) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

    def test_result_scalar(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert SplitOnPartVolume.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=2) == \
               (10 * 20 * 20) * result_scale * 8

    def test_cube_equal_volume(self):
        data = np.zeros((1, 60, 100, 100, 1), dtype=np.uint16)
        data[0, 10:50, 20:80, 20:80] = 50
        data[0, 15:45, 30:70, 30:70] = 70
        image = Image(data, (100, 50, 50), "")
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60
        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (40*60*60 - 36 * 52 * 52) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (36 * 52 * 52 - 30 * 40 * 40) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (30 * 40 * 40) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (30 * 40 * 40) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

    def test_square_equal_radius(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60

        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (60 * 60 - 40 * 40) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (60 * 60 - 30 * 30) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (40 * 40 - 30 * 30) * result_scale

    def test_square_equal_volume(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60

        result_scale = reduce(lambda x, y: x * y, image.voxel_size)

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (60 * 60 - 50 * 50) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (60 * 60 - 44 * 44) * result_scale

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == 0

        assert SplitOnPartVolume.calculate_property(
            part_selection=2, num_of_parts=2, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, result_scalar=1) == (40 * 40 ) * result_scale


class TestSplitOnPartPixelBrightnessSum:
    def test_cube_equal_radius(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60


        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (30*60*60 - 20*40*40) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (20 * 40 * 40 - 10 * 20 * 20) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (10 * 20 * 20) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == \
               (20 * 40 * 40 - 10 * 20 * 20) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (10 * 20 * 20) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

    def test_cube_equal_volume(self):
        data = np.zeros((1, 60, 100, 100, 1), dtype=np.uint16)
        data[0, 10:50, 20:80, 20:80] = 50
        data[0, 15:45, 30:70, 30:70] = 70
        image = Image(data, (100, 50, 50), "")
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size,  channel = image.get_channel(0)) == (40*60*60 - 36 * 52 * 52) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (36 * 52 * 52 - 30 * 40 * 40) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (30 * 40 * 40) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=2, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=3, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == \
               (30 * 40 * 40) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=4, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

    def test_square_equal_radius(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (60 * 60 - 40 * 40) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=False, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == \
               (60 * 60 - 40 * 40) * 50 + (40 * 40 - 30 * 30) * 70

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=False, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (40 * 40 - 30 * 30) * 70

    def test_square_equal_volume(self):
        image = get_square_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask1 = image.get_channel(0)[0] > 40
        mask2 = image.get_channel(0)[0] > 60

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (60 * 60 - 50 * 50) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=True, segmentation=mask1, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (60 * 60 - 44 * 44) * 50

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=3, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=1, num_of_parts=2, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == 0

        assert SplitOnPartPixelBrightnessSum.calculate_property(
            part_selection=2, num_of_parts=2, equal_volume=True, segmentation=mask2, mask=mask1,
            voxel_size=image.voxel_size, channel = image.get_channel(0)) == (40 * 40 ) * 70

class TestStatisticProfile:
    def test_cube_volume_area_type(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask = (image.get_channel(0)[0] > 40).astype(np.uint8)
        segmentation = (image.get_channel(0)[0] > 60).astype(np.uint8)

        statistics = [
            MeasurementEntry("Mask Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No)),
            MeasurementEntry("Segmentation Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                               per_component=PerComponent.No)),
            MeasurementEntry("Mask without segmentation Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                               per_component=PerComponent.No))
        ]
        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.µm)
        tot_vol, seg_vol, rim_vol = list(result.values())
        assert isclose(tot_vol[0], seg_vol[0] + rim_vol[0])

    def test_cube_pixel_sum_area_type(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask = (image.get_channel(0)[0] > 40).astype(np.uint8)
        segmentation = (image.get_channel(0)[0] > 60).astype(np.uint8)

        statistics = [
            MeasurementEntry("Mask PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                           per_component=PerComponent.No)),
            MeasurementEntry("Segmentation PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                                           per_component=PerComponent.No)),
            MeasurementEntry("Mask without segmentation PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                                           per_component=PerComponent.No))
        ]
        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.µm)
        tot_vol, seg_vol, rim_vol = list(result.values())
        assert isclose(tot_vol[0], seg_vol[0] + rim_vol[0])

    def test_cube_surface_area_type(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask = (image.get_channel(0)[0] > 40).astype(np.uint8)
        segmentation = (image.get_channel(0)[0] > 60).astype(np.uint8)

        statistics = [
            MeasurementEntry("Mask Surface",
                             Surface.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No)),
            MeasurementEntry("Segmentation Surface",
                             Surface.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                                per_component=PerComponent.No)),
            MeasurementEntry("Mask without segmentation Surface",
                             Surface.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                                per_component=PerComponent.No))
        ]
        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.µm)
        tot_vol, seg_vol, rim_vol = list(result.values())
        assert isclose(tot_vol[0] + seg_vol[0], rim_vol[0])

    def test_cube_density(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask = (image.get_channel(0)[0] > 40).astype(np.uint8)
        segmentation = (image.get_channel(0)[0] > 60).astype(np.uint8)

        statistics = [
            MeasurementEntry("Mask Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No)),
            MeasurementEntry("Segmentation Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                               per_component=PerComponent.No)),
            MeasurementEntry("Mask without segmentation Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                               per_component=PerComponent.No)),
            MeasurementEntry("Mask PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                           per_component=PerComponent.No)),
            MeasurementEntry("Segmentation PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                                           per_component=PerComponent.No)),
            MeasurementEntry("Mask without segmentation PixelBrightnessSum",
                             PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                                           per_component=PerComponent.No)),
            MeasurementEntry("Mask Volume/PixelBrightnessSum",
                             Node(
                               Volume.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No),
                               "/",
                               PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                               per_component=PerComponent.No)
                           )),
            MeasurementEntry("Segmentation Volume/PixelBrightnessSum",
                             Node(
                               Volume.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                                   per_component=PerComponent.No),
                               "/",
                               PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Segmentation,
                                                                               per_component=PerComponent.No)
                           )),
            MeasurementEntry("Mask without segmentation Volume/PixelBrightnessSum",
                             Node(
                               Volume.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                                   per_component=PerComponent.No),
                               "/",
                               PixelBrightnessSum.get_starting_leaf().replace_(area=AreaType.Mask_without_segmentation,
                                                                               per_component=PerComponent.No)
                           )),

        ]
        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.µm)
        values = list(result.values())
        for i in range(3):
            volume, brightness, density = values[i::3]
            assert isclose(volume[0] / brightness[0], density[0])

    def test_cube_volume_power(self):
        image = get_cube_image()
        image.set_spacing(tuple([x / UNIT_SCALE[Units.nm.value] for x in image.spacing]))
        mask = (image.get_channel(0)[0] > 40).astype(np.uint8)
        segmentation = (image.get_channel(0)[0] > 60).astype(np.uint8)

        statistics = [
            MeasurementEntry("Mask Volume",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No)),
            MeasurementEntry("Mask Volume power 2",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                 per_component=PerComponent.No, power=2)),
            MeasurementEntry("Mask Volume 2",
                             Node(
                               Volume.get_starting_leaf().replace_(area=AreaType.Mask, per_component=PerComponent.No,
                                                                   power=2),
                               "/",
                               Volume.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                   per_component=PerComponent.No)
                              )),
            MeasurementEntry("Mask Volume power -1",
                             Volume.get_starting_leaf().replace_(area=AreaType.Mask,
                                                                 per_component=PerComponent.No, power=-1)),
        ]
        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.µm)
        vol1, vol2, vol3, vol4 = list(result.values())
        assert isclose(vol1[0], vol3[0])
        assert isclose(vol1[0] ** 2, vol2[0])
        assert isclose(vol1[0] * vol4[0], 1)

    def test_per_component_cache_collision(self):
        image = get_two_components_image()
        mask = get_two_component_mask()
        segmentation = np.zeros(mask.shape, dtype=np.uint8)
        segmentation[image.get_channel(0)[0] == 50] = 1
        segmentation[image.get_channel(0)[0] == 60] = 2
        statistics = [
            MeasurementEntry("Volume", Volume.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.No)),
            MeasurementEntry("Volume per component", Volume.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.Yes)),
            MeasurementEntry("Diameter", Diameter.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.No)),
            MeasurementEntry("Diameter per component", Diameter.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.Yes)),
            MeasurementEntry("MaximumPixelBrightness", MaximumPixelBrightness.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.No)),
            MeasurementEntry("MaximumPixelBrightness per component", MaximumPixelBrightness.get_starting_leaf().
                             replace_(area=AreaType.Segmentation, per_component=PerComponent.Yes)),
            MeasurementEntry("Sphericity", Sphericity.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.No)),
            MeasurementEntry("Sphericity per component", Sphericity.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.Yes)),
            MeasurementEntry("LongestMainAxisLength", LongestMainAxisLength.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.No)),
            MeasurementEntry("LongestMainAxisLength per component", LongestMainAxisLength.get_starting_leaf().replace_(
                area=AreaType.Segmentation, per_component=PerComponent.Yes)),
        ]

        profile = MeasurementProfile("statistic", statistics)
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.nm)
        assert result["Volume"][0] == result["Volume per component"][0][0] + result["Volume per component"][0][1]
        assert len(result["Diameter per component"][0]) == 2
        assert result["MaximumPixelBrightness"][0] == 60
        assert result["MaximumPixelBrightness per component"][0] == [50, 60]
        assert result["Sphericity per component"][0] == [
            Sphericity.calculate_property(area_array=segmentation == 1, voxel_size=image.voxel_size,
                                          result_scalar=UNIT_SCALE[Units.nm.value]),
            Sphericity.calculate_property(area_array=segmentation == 2, voxel_size=image.voxel_size,
                                          result_scalar=UNIT_SCALE[Units.nm.value])
        ]
        assert result["LongestMainAxisLength"][0] == 55 * 50 * UNIT_SCALE[Units.nm.value]
        assert result["LongestMainAxisLength per component"][0][0] == 35 * 50 * UNIT_SCALE[Units.nm.value]
        assert result["LongestMainAxisLength per component"][0][1] == 26 * 50 * UNIT_SCALE[Units.nm.value]

    def test_all_variants(self):
        """ This test check if all calculations finished, not values. """
        file_path = os.path.join(os.path.dirname(__file__), "test_data", "measurements_profile.json")
        profile = load_metadata(file_path)["all_statistic"]
        image = get_two_components_image()
        mask = get_two_component_mask()
        segmentation = np.zeros(mask.shape, dtype=np.uint8)
        segmentation[image.get_channel(0)[0] == 50] = 1
        segmentation[image.get_channel(0)[0] == 60] = 2
        result = profile.calculate(image.get_channel(0), segmentation, full_mask=mask, mask=mask,
                                   voxel_size=image.voxel_size, result_units=Units.nm)
        names = set([x.name for x in profile.chosen_fields])
        assert names == set(result.keys())


# noinspection DuplicatedCode
class TestMeasurementResult:
    def test_simple(self):
        info = ComponentsInfo(np.arange(0), np.arange(0), dict())
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = 5, "np", (PerComponent.No, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), (5, "np")]
        assert storage.get_separated() == [[1, 5]]
        assert storage.get_labels() == ["aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), (5, "np")]
        assert storage.get_separated() == [["test.tif", 1, 5]]
        assert storage.get_labels() == ["File name", "aa", "bb"]

    def test_simple2(self):
        info = ComponentsInfo(np.arange(1, 5), np.arange(1, 5), {i: [i] for i in range(1, 5)})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = 5, "np", (PerComponent.No, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), (5, "np")]
        assert storage.get_separated() == [[1, 5]]
        assert storage.get_labels() == ["aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), (5, "np")]
        assert storage.get_separated() == [["test.tif", 1, 5]]
        assert storage.get_labels() == ["File name", "aa", "bb"]

    def test_segmentation_components(self):
        info = ComponentsInfo(np.arange(1, 3), np.arange(0), {1: [], 2: []})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = [4, 5], "np", (PerComponent.Yes, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), ([4, 5], "np")]
        assert storage.get_separated() == [[1, 1, 4], [2, 1, 5]]
        assert storage.get_labels() == ["Segmentation component", "aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4], ["test.tif", 2, 1, 5]]
        assert storage.get_labels() == ["File name", "Segmentation component", "aa", "bb"]
        storage["cc"] = [11, 3], "np", (PerComponent.Yes, AreaType.Segmentation)
        assert list(storage.keys()) == ["File name", "aa", "bb", "cc"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np"), ([11, 3], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4, 11], ["test.tif", 2, 1, 5, 3]]
        assert storage.get_labels() == ["File name", "Segmentation component", "aa", "bb", "cc"]

    def test_mask_components(self):
        info = ComponentsInfo(np.arange(1, 2), np.arange(1, 3), {1: [], 2: []})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = [4, 5], "np", (PerComponent.Yes, AreaType.Mask)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), ([4, 5], "np")]
        assert storage.get_labels() == ["Mask component", "aa", "bb"]
        assert storage.get_separated() == [[1, 1, 4], [2, 1, 5]]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4], ["test.tif", 2, 1, 5]]
        assert storage.get_labels() == ["File name", "Mask component", "aa", "bb"]
        storage["cc"] = [11, 3], "np", (PerComponent.Yes, AreaType.Mask_without_segmentation)
        assert list(storage.keys()) == ["File name", "aa", "bb", "cc"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np"), ([11, 3], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4, 11], ["test.tif", 2, 1, 5, 3]]
        assert storage.get_labels() == ["File name", "Mask component", "aa", "bb", "cc"]

    def test_mask_segmentation_components(self):
        info = ComponentsInfo(np.arange(1, 3), np.arange(1, 3), {1: [1], 2: [2]})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = [4, 5], "np", (PerComponent.Yes, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), ([4, 5], "np")]
        assert storage.get_separated() == [[1, 1, 4], [2, 1, 5]]
        assert storage.get_labels() == ["Segmentation component", "aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4], ["test.tif", 2, 1, 5]]
        assert storage.get_labels() == ["File name", "Segmentation component", "aa", "bb"]
        storage["cc"] = [11, 3], "np", (PerComponent.Yes, AreaType.Mask)
        assert list(storage.keys()) == ["File name", "aa", "bb", "cc"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5], "np"), ([11, 3], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 1, 4, 11], ["test.tif", 2, 2, 1, 5, 3]]
        assert storage.get_labels() == ["File name", "Segmentation component", "Mask component", "aa", "bb", "cc"]

    def test_mask_segmentation_components2(self):
        info = ComponentsInfo(np.arange(1, 4), np.arange(1, 3), {1: [1], 2: [2], 3: [1]})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = [4, 5, 6], "np", (PerComponent.Yes, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), ([4, 5, 6], "np")]
        assert storage.get_separated() == [[1, 1, 4], [2, 1, 5], [3, 1, 6]]
        assert storage.get_labels() == ["Segmentation component", "aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5, 6], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4], ["test.tif", 2, 1, 5], ["test.tif", 3, 1, 6]]
        assert storage.get_labels() == ["File name", "Segmentation component", "aa", "bb"]
        storage["cc"] = [11, 3], "np", (PerComponent.Yes, AreaType.Mask)
        assert list(storage.keys()) == ["File name", "aa", "bb", "cc"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5, 6], "np"), ([11, 3], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 1, 4, 11], ["test.tif", 2, 2, 1, 5, 3],
                                           ["test.tif", 3, 1, 1, 6, 11]]
        assert storage.get_labels() == ["File name", "Segmentation component", "Mask component", "aa", "bb", "cc"]

    def test_mask_segmentation_components3(self):
        info = ComponentsInfo(np.arange(1, 4), np.arange(1, 3), {1: [1], 2: [2], 3: [1, 2]})
        storage = MeasurementResult(info)
        storage["aa"] = 1, "", (PerComponent.No, AreaType.Segmentation)
        storage["bb"] = [4, 5, 6], "np", (PerComponent.Yes, AreaType.Segmentation)
        assert list(storage.keys()) == ["aa", "bb"]
        assert list(storage.values()) == [(1, ""), ([4, 5, 6], "np")]
        assert storage.get_separated() == [[1, 1, 4], [2, 1, 5], [3, 1, 6]]
        assert storage.get_labels() == ["Segmentation component", "aa", "bb"]
        storage.set_filename("test.tif")
        assert list(storage.keys()) == ["File name", "aa", "bb"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5, 6], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 4], ["test.tif", 2, 1, 5], ["test.tif", 3, 1, 6]]
        assert storage.get_labels() == ["File name", "Segmentation component", "aa", "bb"]
        storage["cc"] = [11, 3], "np", (PerComponent.Yes, AreaType.Mask)
        assert list(storage.keys()) == ["File name", "aa", "bb", "cc"]
        assert list(storage.values()) == [("test.tif", ""), (1, ""), ([4, 5, 6], "np"), ([11, 3], "np")]
        assert storage.get_separated() == [["test.tif", 1, 1, 1, 4, 11], ["test.tif", 2, 2, 1, 5, 3],
                                           ["test.tif", 3, 1, 1, 6, 11], ["test.tif", 3, 2, 1, 6, 3]]
        assert storage.get_labels() == ["File name", "Segmentation component", "Mask component", "aa", "bb", "cc"]