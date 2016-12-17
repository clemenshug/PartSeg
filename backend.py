from __future__ import print_function, division
import matplotlib
from matplotlib import pyplot
import numpy as np
import SimpleITK as sitk
import h5py
import json
import tempfile
import os
import tarfile
import auto_fit as af
import logging
import sys
from enum import Enum
from copy import deepcopy
from collections import OrderedDict, namedtuple
UPPER = "Upper"
GAUSS = "Gauss"

UNITS_DICT = {
    "Volume": "{}^3",
    "Mass": "pixel sum",
    "Border Volume": "{}^3",
    "Border Surface": "{}^2",
    "Border Surface Opening": "{}^2",
    "Border Surface Closing": "{}^2",
    "Pixel min": "pixel brightness",
    "Pixel max": "pixel brightness",
    "Pixel mean": "pixel brightness",
    "Pixel median": "pixel brightness",
    "Pixel std": "pixel brightness",
    "Mass to Volume": "pixel sum/{}^3",
    "Volume to Border Surface": "{}",
    "Volume to Border Surface Opening": "{}",
    "Volume to Border Surface Closing": "{}",
    "Moment of inertia": "",
    "Noise_std": "pixel brightness"
}


class MaskChange(Enum):
    prev_seg = 1
    next_seg = 2


class GaussUse(Enum):
    no_gauss = 1
    gauss_2d = 2
    gauss_3d = 3


class MorphChange(Enum):
    no_morph = 1
    opening_morph = 2
    closing_morph = 3


def class_to_dict(obj, *args):
    """
    Create dict which contains values of given fields
    :type obj: object
    :type args: list[str]
    :return:
    """
    res = dict()
    for name in args:
        res[name] = getattr(obj, name)
    return res


def dict_set_class(obj, dic, *args):
    """
    Set fields of given object based on values from dict.
    If *args contains no names all values from dict are used
    :type obj: object
    :type dic: dict[str,object]
    :param args: list[str]
    :return:
    """
    if len(args) == 0:
        li = dic.keys()
    else:
        li = args
    for name in li:
        try:
            getattr(obj, name)
            setattr(obj, name, dic[name])
        except AttributeError as ae:
            logging.warning(ae)


def gaussian(image, radius):
    """
    :param image: image to apply gaussian filter
    :param radius: radius for gaussian kernel
    :return:
    """
    if len(image.shape) == 2:
        return sitk.GetArrayFromImage(sitk.DiscreteGaussian(sitk.GetImageFromArray(image), radius))
    res = np.copy(image)
    for layer in res:
        layer[...] = sitk.GetArrayFromImage(sitk.DiscreteGaussian(sitk.GetImageFromArray(layer), radius))
    return res


def dilate(image, radius):
    """
    :param image: image to apply gaussian filter
    :param radius: radius for gaussian kernel
    :return:
    """
    if len(image.shape) == 2:
        return sitk.GetArrayFromImage(sitk.GrayscaleDilate(sitk.GetImageFromArray(image), radius))
    res = np.copy(image)
    for layer in res:
        layer[...] = sitk.GetArrayFromImage(sitk.GrayscaleDilate(sitk.GetImageFromArray(layer), radius))
    return res


def to_binary_image(image):
    return np.array(image > 0).astype(np.uint8)


def bisect(arr, val, comp):
    l = -1
    r = len(arr)
    while r - l > 1:
        e = (l + r) >> 1
        if comp(arr[e], val):
            l = e
        else:
            r = e
    return r

SettingsValue = namedtuple("SettingsValue", ["function_name", "help_message", "arguments"])
Leaf = namedtuple("Leaf", ["name", "dict"])
Node = namedtuple("Node", ["left", 'op', 'right'])


class StatisticProfile(object):

    STATISTIC_DICT = {
        "Volume": SettingsValue("calculate_volume", "Calculate volume of current segmentation", None),
        "Volume per component": SettingsValue("calculate_component_volume", "Calculate volume of each component "
                                              "of cohesion of current segmentation", None),
        "Mass": SettingsValue("calculate_mass", "Sum of pixel brightness for current segmentation", None),
        "Mass per component": SettingsValue("calculate_component_mass", "Sum of pixel brightness of each component of"
                                            " cohesion for current segmentation", None),
        "Border surface": SettingsValue("calculate_border_surface",
                                        "Calculating surface of current segmentation", None),
        "Maximum pixel brightness": SettingsValue(
            "maximum_brightness", "Calculate maximum brightness of pixel for current segmentation", None),
        "Minimum pixel brightness": SettingsValue(
            "minimum_brightness", "Calculate minimum brightness of pixel for current segmentation", None),
        "Median pixel brightness": SettingsValue(
            "median_brightness", "Calculate median brightness of pixel for current segmentation", None),
        "Mean pixel brightness": SettingsValue(
            "mean_brightness", "Calculate median brightness of pixel for current segmentation", None),
        "Standard deviation of pixel brightness": SettingsValue(
            "std_brightness", "Calculate  standard deviation of pixel brightness for current segmentation", None),
        "Standard deviation of Noise": SettingsValue(
            "std_noise", "Calculate standard deviation of pixel brightness outside current segmentation", None),
        "Moment of inertia": SettingsValue("moment_of_inertia", "Calculate moment of inertia for segmented structure."
                                           "Has one parameter thr (threshold). Only values above it are used "
                                           "in calculation", {"thr": float}),
        "Border Mass": SettingsValue("border_mass", "Calculate mass for elements in radius (in physical units)"
                                                    " from mask", {"radius": int}),
        "Border Volume": SettingsValue("border_volume", "Calculate volumes for elements in radius (in physical units)"
                                                        " from mask", {"radius": int})
    }

    def __init__(self, name, chosen_fields, reversed_brightness, settings):
        self.name = name
        self.chosen_fields = []
        for cf_val in chosen_fields:
            user_name = cf_val[1]
            if isinstance(cf_val[0], str):
                tree = self.parse_statistic(cf_val[0])
            else:
                tree = self.rebuild_tree(cf_val[0])
            self.chosen_fields.append((tree, user_name, None))
        self.settings = settings
        self.reversed_brightness = reversed_brightness

    def rebuild_tree(self, l):
        if len(l) == 2:
            return Leaf(*l)
        else:
            return Node(self.rebuild_tree(l[0]), l[1], self.rebuild_tree(l[2]))

    @staticmethod
    def tokenize(text):
        special = ["(", ")", "[", "]", "/", "+", ","]
        res = []
        temp_str = ""
        for l in text:
            if l in special:
                if temp_str != "":
                    res.append(temp_str)
                    temp_str = ""
                res.append(l)
            else:
                temp_str += l
        if temp_str != "":
            res.append(temp_str)
        return res

    def build_tree(self, tokens):
        res = []
        final_res = res
        pos = 0
        while True:
            if pos == len(tokens):
                break
            if tokens[pos] == ")":
                pos += 1
                break
            if tokens[pos] == "/":
                final_res = [res[:], "/"]
                res = []
                final_res.append(res)
                pos += 1
            if tokens[pos] in "[],":
                pos += 1
                continue
            if tokens[pos] == "(":
                sub_tree, pos_shift = self.build_tree(tokens[pos+1:])
                pos += pos_shift+1
                res.extend(sub_tree)
                continue
            res.append(tokens[pos])
            pos += 1
        return final_res, pos

    def tree_to_dict_tree(self, tree):
        if isinstance(tree[0], list):
            left_tree = self.tree_to_dict_tree(tree[0])
            right_tree = self.tree_to_dict_tree(tree[2])
            return Node(left_tree, tree[1], right_tree)
        else:
            name = tree[0]
            base_stat = self.STATISTIC_DICT[name]
            d = dict()
            for el in tree[1:]:
                sp = el.split("=")
                d[sp[0]] = base_stat.arguments[sp[0]](sp[1])
            return Leaf(name, d)

    def parse_statistic(self, text):
        tokens = self.tokenize(text)

        tree, l = self.build_tree(tokens)
        return self.tree_to_dict_tree(tree)

    def calculate_tree(self, node, help_dict, kwargs):
        """
        :type node: Leaf | Node
        :type help_dict: dict
        :type kwargs: dict
        :return: float
        """
        if isinstance(node, Leaf):
            fun_name = self.STATISTIC_DICT[node.name][0]
            kw = dict(kwargs)
            kw.update(node.dict)
            hash_str = "{}: {}".format(fun_name, kw)
            if hash_str in help_dict:
                return help_dict[hash_str]
            fun = getattr(self, fun_name)
            val = fun(**kw)
            help_dict[hash_str] = val
            return val
        elif isinstance(node, Node):
            left_res = self.calculate_tree(node.left, help_dict, kwargs)
            right_res = self.calculate_tree(node.right, help_dict, kwargs)
            if node.op == "/":
                return left_res/right_res
        logging.error("Wrong statistics: {}".format(node))
        return 1

    def calculate(self, image, mask, full_mask, base_mask):
        result = OrderedDict()
        if self.reversed_brightness:
            noise_mean = np.mean(image[full_mask == 0])
            image = noise_mean - image
        help_dict = dict()
        kw = {"image": image, "mask": mask, "base_mask": base_mask, "full_mask": full_mask}
        for tree, user_name, params in self.chosen_fields:
            try:
                result[user_name] = self.calculate_tree(tree, help_dict, kw)
            except ZeroDivisionError:
                result[user_name] = "Div by zero"
            except TypeError:
                result[user_name] = "None div"
        return result

    @staticmethod
    def pixel_volume(x):
        return x[0] * x[1] * x[2]

    def calculate_volume(self, mask, **_):
        print("Volume {}".format(np.max(mask)))
        return np.count_nonzero(mask) * self.pixel_volume(self.settings.voxel_size)

    def calculate_component_volume(self, mask, **_):
        return np.bincount(mask)[1:] * self.pixel_volume(self.settings.voxel_size)

    @staticmethod
    def calculate_mass(mask, image, **_):
        if np.any(mask):
            return np.sum(image[mask > 0])
        return 0

    @staticmethod
    def calculate_component_mass(mask, image, **_):
        res = []
        for i in range(1, mask.max()+1):
            res.append(np.sum(image[mask == i]))
        return res

    def calculate_border_surface(self, mask, **_):
        return calculate_volume_surface(mask, self.settings.voxel_size)

    @staticmethod
    def maximum_brightness(mask, image, **_):
        if np.any(mask):
            return np.max(image[mask > 0])
        else:
            return None

    @staticmethod
    def minimum_brightness(mask, image, **_):
        if np.any(mask):
            return np.min(image[mask > 0])
        else:
            return None

    @staticmethod
    def median_brightness(mask, image, **_):
        if np.any(mask):
            return np.median(image[mask > 0])
        else:
            return None

    @staticmethod
    def std_brightness(mask, image, **_):
        if np.any(mask):
            return np.std(image[mask > 0])
        else:
            return None

    @staticmethod
    def mean_brightness(mask, image, **_):
        if np.any(mask):
            return np.mean(image[mask > 0])
        else:
            return None

    @staticmethod
    def std_noise(mask, base_mask, image, **_):
        if np.any(mask):
            if base_mask is not None:
                return np.std(image[(mask == 0) * (base_mask > 0)])
            else:
                return np.std(image[mask == 0])
        else:
            return None

    def moment_of_inertia(self, image, mask, **_):
        if image.ndim != 3:
            return None
        img = np.copy(image)
        img[mask == 0] = 0
        return af.calculate_density_momentum(img, self.settings.voxel_size,)

    def border_mask(self, base_mask, radius, **_):
        if base_mask is None:
            return None
        base_mask = np.array(base_mask > 0)
        base_mask = base_mask.astype(np.uint8)
        border = sitk.LabelContour(sitk.GetImageFromArray(base_mask))
        border.SetSpacing(self.settings.voxel_size)
        dilated_border = sitk.GetArrayFromImage(sitk.BinaryDilate(border, radius))
        dilated_border[base_mask == 0] = 0
        return dilated_border

    def border_mass(self, image, mask, **kwargs):
        border_mask = self.border_mask(**kwargs)
        if border_mask is None:
            return None
        final_mask = np.array((border_mask > 0) * (mask > 0))
        if np.any(final_mask):
            return np.sum(image[final_mask])
        return 0

    def border_volume(self, mask, **kwargs):
        border_mask = self.border_mask(**kwargs)
        if border_mask is None:
            return None
        final_mask = np.array((border_mask > 0) * (mask > 0))
        return np.count_nonzero(final_mask) * self.pixel_volume(self.settings.voxel_size)


class Profile(object):
    PARAMETERS = ("threshold", "threshold_list", "threshold_type", "minimum_size", "use_gauss", "gauss_radius",
                  "threshold_layer_separate")

    def __init__(self, name, threshold, threshold_list, threshold_type, minimum_size, use_gauss, gauss_radius,
                 threshold_layer_separate):
        """
        :param name: str,
        :param threshold: int
        :param threshold_list: list[int]
        :param threshold_type: str
        :param minimum_size: int
        :param use_gauss: bool
        """
        self.name = name
        if threshold_layer_separate:
            self.threshold = np.median(threshold_list)
            self.threshold_list = threshold_list
        else:
            self.threshold = threshold
            self.threshold_list = []
        self.threshold_type = threshold_type
        self.minimum_size = minimum_size
        self.use_gauss = use_gauss
        self.gauss_radius = gauss_radius
        self.threshold_layer_separate = threshold_layer_separate

    def __str__(self):
        if self.name != "":
            text = "Name: {}\n".format(self.name)
        else:
            text = ""
        text += "{} threshold: ".format(self.threshold_type)
        if self.threshold_layer_separate:
            text += str(self.threshold_list)
        else:
            text += str(self.threshold)
            text += "\n"
        text += "Minimum object size: {}\n".format(self.minimum_size)
        text += "Use gauss [{}]\n".format("x" if self.use_gauss else " ")
        text += "Gauss radius: {}".format(self.gauss_radius)
        return text

    def get_parameters(self):
        return class_to_dict(self, *self.PARAMETERS)


class Settings(object):
    """
    :type profiles: dict[str, Profile]
    :type threshold: int
    :type threshold_list: list[int]
    :type threshold_type: str
    :type minimum_size: int
    :type image: np.ndarray
    :type image_change_callback: list[(() -> None) | (() -> None, object)]
    """
    def __init__(self, settings_path):
        self.color_map_name = "cubehelix"
        self.color_map = matplotlib.cm.get_cmap(self.color_map_name)
        self.callback_colormap = []
        self.callback_colormap_list = []
        self.callback_change_layer = []
        self.chosen_colormap = pyplot.colormaps()
        self.profiles = dict()
        self.profiles_list_changed_callback = []
        self.use_gauss = False
        self.use_draw_result = False
        self.draw_callback = []
        self.threshold = 33000
        self.threshold_list = []
        self.threshold_type = UPPER
        self.threshold_layer_separate = False
        self.minimum_size = 100
        self.overlay = 0.7
        self.mask_overlay = 0.7
        self.power_norm = 1
        self.image = None
        self.original_image = None
        self.image_clean_profile = None
        self.gauss_image = None
        self.mask = None
        self.gauss_radius = 1
        self.image_change_callback = []
        self.threshold_change_callback = []
        self.threshold_type_change_callback = []
        self.minimum_size_change_callback = []
        self.metadata_changed_callback = []
        self.layer_num = 0
        self.open_directory = None
        self.open_filter = None
        self.save_directory = None
        self.save_filter = None
        self.export_directory = None
        self.export_filter = None
        self.spacing = [5, 5, 30]
        self.voxel_size = [5, 5, 30]
        self.size_unit = "nm"
        self.advanced_menu_geometry = None
        self.file_path = ""
        self.protect = False
        self.prev_segmentation_settings = []
        self.next_segmentation_settings = []
        self.mask_dilate_radius = 0
        self.scale_factor = 0.97
        self.statistics_profile_dict = dict()
        self.statistic_dirs = None
        try:
            self.load(settings_path)
        except ValueError as e:
            logging.error("Saved profile problem: {}".format(e))

    def change_profile(self, name):
        prof = self.profiles[name]
        dict_set_class(self, prof.get_parameters(), *Profile.PARAMETERS)
        for fun in self.threshold_change_callback:
            fun()

    def add_profiles_list_callback(self, callback):
        self.profiles_list_changed_callback.append(callback)

    def get_profile_dict(self):
        return class_to_dict(self, "threshold", "threshold_list", "threshold_type", "minimum_size", "use_gauss",
                             "gauss_radius", "threshold_layer_separate")

    def dump_profiles(self, file_path):
        profiles_list = [x.__dict__ for k, x in self.profiles.items()]
        with open(file_path, "w") as ff:
            json.dump(profiles_list, ff)

    def load_profiles(self, file_path):
        with open(file_path, "r") as ff:
            profiles_list = json.load(ff)
            for prof in profiles_list:
                self.profiles[prof["name"]] = Profile(**prof)
        for fun in self.threshold_change_callback:
            fun()

    def dump_statistics(self, file_path):
        res = [class_to_dict(x, "name", "chosen_fields", "reversed_brightness")
               for x in self.statistics_profile_dict.values()]
        with open(file_path, 'w') as ff:
            json.dump(ff, res)

    def load_statistics(self, file_path):
        with open(file_path, 'r') as ff:
            statistics_list = json.load(ff)
            for stat in statistics_list:
                self.statistics_profile_dict[stat["name"]] = StatisticProfile(settings=self, **stat)

    def dump(self, file_path):
        important_data = \
            class_to_dict(self, "open_directory", "open_filter", "save_directory", "save_filter", "spacing",
                          "voxel_size", "size_unit", "threshold", "color_map_name", "overlay", "minimum_size",
                          "gauss_radius", "export_filter", "export_directory", "scale_factor", "statistic_dirs",
                          "chosen_colormap")
        important_data["profiles"] = [x.__dict__ for k, x in self.profiles.items()]
        important_data["statistics"] = [class_to_dict(x, "name", "chosen_fields", "reversed_brightness")
                                        for x in self.statistics_profile_dict.values()]
        with open(file_path, "w") as ff:
            json.dump(important_data, ff)

    def load(self, file_path):
        try:
            with open(file_path, "r") as ff:
                important_data = json.load(ff)
            dict_set_class(self, important_data, "open_directory", "open_filter", "save_directory", "save_filter",
                           "spacing", "voxel_size", "size_unit", "threshold", "color_map_name", "overlay",
                           "minimum_size", "gauss_radius", "export_filter", "export_directory", "scale_factor",
                           "statistic_dirs", "chosen_colormap")
            chosen_colormap = set(self.chosen_colormap)
            avail_colormap = set(pyplot.colormaps())
            self.chosen_colormap = list(sorted(chosen_colormap & avail_colormap))
            self.color_map = matplotlib.cm.get_cmap(self.color_map_name)
            for prof in important_data["profiles"]:
                self.profiles[prof["name"]] = Profile(**prof)
            for stat in important_data["statistics"]:
                self.statistics_profile_dict[stat["name"]] = StatisticProfile(settings=self, **stat)
        except IOError:
            logging.warning("No configuration file")
            pass
        except KeyError as e:
            logging.warning("Bad configuration: {}".format(e))

    def change_segmentation_mask(self, segment, order, save_draw):
        """
        :type segment: Segment
        :type order: MaskChange
        :type save_draw: bool
        :return:
        """
        save_fields = ["threshold", "threshold_list", "threshold_type", "threshold_layer_separate",
                       "minimum_size", "use_gauss", "use_draw_result", "mask_dilate_radius", "mask", "gauss_radius"]
        if order == MaskChange.prev_seg and len(self.prev_segmentation_settings) == 0:
            return

        current_mask = segment.get_segmentation()
        seg_settings = class_to_dict(self, *save_fields)
        seg_settings["draw_points"] = tuple(map(list, np.nonzero(np.array(segment.draw_canvas == 1))))
        seg_settings["erase_points"] = tuple(map(list, np.nonzero(np.array(segment.draw_canvas == 2))))
        save_draw_bck = np.copy(segment.draw_canvas)
        if order == MaskChange.next_seg:
            self.prev_segmentation_settings.append(seg_settings)
            if self.mask_dilate_radius > 0:
                self.mask = dilate(current_mask, self.mask_dilate_radius)
            else:
                self.mask = current_mask
            if len(self.next_segmentation_settings) > 0:
                new_seg = self.next_segmentation_settings.pop()
                new_seg["mask"] = self.mask
            else:
                new_seg = None
            save_fields = save_fields[:-1]
        else:
            self.next_segmentation_settings.append(seg_settings)
            new_seg = self.prev_segmentation_settings.pop()
        segment.draw_canvas[...] = 0
        if new_seg is not None:
            dict_set_class(self, new_seg, *save_fields)
            segment.draw_canvas[tuple(map(lambda x: np.array(x, dtype=np.uint32), new_seg["draw_points"]))] = 1
            segment.draw_canvas[tuple(map(lambda x: np.array(x, dtype=np.uint32), new_seg["erase_points"]))] = 2
        if save_draw:
            segment.draw_canvas[save_draw_bck > 0] = save_draw_bck[save_draw_bck > 0]
        for fun in self.threshold_change_callback:
            fun()
        for fun in self.callback_colormap:
            fun()
        self.advanced_settings_changed()

    def change_colormap(self, new_color_map=None):
        """
        :type new_color_map: str | none
        :param new_color_map: name of new colormap
        :return:
        """
        if new_color_map is not None:
            self.color_map_name = new_color_map
            self.color_map = matplotlib.cm.get_cmap(new_color_map)
        for fun in self.callback_colormap:
            fun()

    def add_colormap_list_callback(self, callback):
        self.callback_colormap_list.append(callback)

    def add_colormap_callback(self, callback):
        self.callback_colormap.append(callback)

    def remove_colormap_callback(self, callback):
        self.callback_colormap.remove(callback)

    def add_profile(self, profile):
        """
        :type profile: Profile
        :return:
        """
        # if not overwrite and name in self.profiles:
        #    raise ValueError("Profile with this name already exists")
        self.profiles[profile.name] = profile
        for fun in self.profiles_list_changed_callback:
            fun()

    def delete_profile(self, name):
        del self.profiles[name]

    def get_profile(self, name):
        return self.profiles[name]

    @property
    def colormap_list(self):
        return self.chosen_colormap

    @property
    def available_colormap_list(self):
        return pyplot.colormaps()

    def add_image(self, image, file_path, mask=None, new_image=True, original_image=None):
        self.image = image
        if original_image is None:
            self.original_image = image
        else:
            self.original_image = original_image
        self.gauss_image = gaussian(self.image, self.gauss_radius)
        self.mask = mask
        self.file_path = file_path
        if new_image:
            self.threshold_list = []
            self.threshold_layer_separate = False
            self.prev_segmentation_settings = []
            self.next_segmentation_settings = []
            self.image_clean_profile = None
        self.image_changed_fun()

    def image_changed_fun(self):
        for fun in self.image_change_callback:
            if isinstance(fun, tuple) and fun[1] == str:
                fun[0](self.file_path)
                continue
            elif isinstance(fun, tuple) and fun[1] == GAUSS:
                fun[0](self.image, self.gauss_image)
                continue
            fun(self.image)

    def changed_gauss_radius(self):
        self.gauss_image = gaussian(self.image, self.gauss_radius)
        for fun in self.image_change_callback:
            if isinstance(fun, tuple) and fun[1] == GAUSS:
                fun[0](self.image, self.gauss_image, True)
                continue
            elif isinstance(fun, tuple) and fun[1] == str:
                continue
            fun(self.image)

    def add_image_callback(self, callback):
        self.image_change_callback.append(callback)

    def change_threshold(self, new_threshold):
        if self.protect:
            return
        if self.threshold_layer_separate:
            if self.threshold_list[self.layer_num] == new_threshold:
                return
            self.threshold_list[self.layer_num] = new_threshold
        else:
            if self.threshold == new_threshold:
                return
            self.threshold = new_threshold
        for fun in self.threshold_change_callback:
            fun()

    def add_change_layer_callback(self, callback):
        self.callback_change_layer.append(callback)

    def change_layer(self, val):
        self.layer_num = val
        self.protect = True
        if self.threshold_layer_separate:
            for fun in self.callback_change_layer:
                fun(self.threshold_list[val])
        else:
            for fun in self.callback_change_layer:
                fun(self.threshold)
        # for fun in self.threshold_change_callback:
        #     fun()
        self.protect = False

    def change_threshold_type(self, new_type):
        print(new_type)
        if new_type == "Upper threshold:":
            self.threshold_type = UPPER
        else:
            self.threshold_type = "Lower"
        for fun in self.threshold_change_callback:
            fun()
        for fun in self.threshold_type_change_callback:
            fun()

    def change_layer_threshold(self, layer_threshold):
        self.threshold_layer_separate = layer_threshold
        if layer_threshold and self.threshold_list == []:
            self.threshold_list = [self.threshold] * self.image.shape[0]
        for fun in self.threshold_change_callback:
            fun()

    def change_gauss(self, use_gauss):
        self.use_gauss = bool(use_gauss)
        for fun in self.threshold_change_callback:
            fun()

    def add_threshold_callback(self, callback):
        self.threshold_change_callback.append(callback)

    def add_threshold_type_callback(self, callback):
        self.threshold_type_change_callback.append(callback)

    def change_min_size(self, new_min_size):
        self.minimum_size = new_min_size
        for fun in self.minimum_size_change_callback:
            fun()

    def add_min_size_callback(self, callback):
        self.minimum_size_change_callback.append(callback)

    def get_profile_list(self):
        return self.profiles.keys()

    def set_available_colormap(self, cmap_list):
        self.chosen_colormap = cmap_list
        for fun in self.callback_colormap_list:
            fun()

    def change_draw_use(self, use_draw):
        self.use_draw_result = use_draw
        for fun in self.draw_callback:
            fun()

    def add_draw_callback(self, callback):
        self.draw_callback.append(callback)

    def add_metadata_changed_callback(self, callback):
        self.metadata_changed_callback.append(callback)

    def advanced_settings_changed(self):
        for fun in self.threshold_type_change_callback:
            fun()
        for fun in self.metadata_changed_callback:
            fun()

    def metadata_changed(self):
        for fun in self.metadata_changed_callback:
            fun()


class Segment(object):
    """
    :type _segmented_image: np.ndarray
    :type segmentation_change_callback: list[() -> None | (list[int] -> None]
    """

    def __init__(self, settings):
        """
        :type settings: Settings
        """
        self._settings = settings
        self._image = None
        self.draw_canvas = None
        self.draw_counter = 0
        self.gauss_image = None
        self._threshold_image = None
        self._segmented_image = None
        self._finally_segment = None
        self._sizes_array = []
        self.segmentation_change_callback = []
        self._segmentation_changed = True
        self.protect = False
        self._settings.add_threshold_callback(self.threshold_updated)
        self._settings.add_min_size_callback(self.min_size_updated)
        self._settings.add_draw_callback(self.draw_update)

    def set_image(self, image):
        self._image = image
        self.gauss_image = gaussian(self._image, self._settings.gauss_radius)
        self._segmentation_changed = True
        self._finally_segment = np.zeros(image.shape, dtype=np.uint8)
        self.threshold_updated()

    def threshold_updated(self):
        if self.protect:
            return
        if self._image is None:
            return
        self._threshold_image = np.zeros(self._image.shape, dtype=np.uint8)
        if self._settings.use_gauss:
            image_to_threshold = self.gauss_image
        else:
            image_to_threshold = self._image
        # Define which threshold use
        if self._settings.threshold_type == UPPER:
            def get_mask(image, threshold):
                return image <= threshold
        else:
            def get_mask(image, threshold):
                return image >= threshold

        if self._settings.threshold_layer_separate:
            # print("Layer separate")
            for i in range(self._image.shape[0]):
                self._threshold_image[i][get_mask(image_to_threshold[i], self._settings.threshold_list[i])] = 1
        else:
            # print("normal")
            self._threshold_image[get_mask(image_to_threshold, self._settings.threshold)] = 1
        if self._settings.mask is not None:
            self._threshold_image *= (self._settings.mask > 0)
        self.draw_update()

    def draw_update(self, canvas=None):
        if self.protect:
            return
        if canvas is not None:
            self.draw_canvas[...] = canvas[...]
            return
        if self._settings.use_draw_result:
            threshold_image = np.copy(self._threshold_image)
            threshold_image[self.draw_canvas == 1] = 1
            threshold_image[self.draw_canvas == 2] = 0
        else:
            threshold_image = self._threshold_image
        connect = sitk.ConnectedComponent(sitk.GetImageFromArray(threshold_image))
        self._segmented_image = sitk.GetArrayFromImage(sitk.RelabelComponent(connect))
        self._sizes_array = np.bincount(self._segmented_image.flat)
        self.min_size_updated()

    def min_size_updated(self):
        if self.protect:
            return
        ind = bisect(self._sizes_array[1:], self._settings.minimum_size, lambda x, y: x > y)
        # print(ind, self._sizes_array, self._settings.minimum_size)
        self._finally_segment = np.copy(self._segmented_image)
        self._finally_segment[self._finally_segment > ind] = 0
        self._segmentation_changed = True
        for fun in self.segmentation_change_callback:
            if isinstance(fun, tuple):
                fun[0](self._sizes_array[1:ind+1])
                continue
            if callable(fun):
                fun()

    @property
    def segmentation_changed(self):
        """:rtype: bool"""
        return self._segmentation_changed

    def get_segmentation(self):
        self._segmentation_changed = False
        return self._finally_segment

    def get_size_array(self):
        return self._sizes_array

    def get_full_segmentation(self):
        return self._segmented_image

    def add_segmentation_callback(self, callback):
        self.segmentation_change_callback.append(callback)


def calculate_volume_surface(volume_mask, voxel_size):
    border_surface = 0
    surf_im = np.array(volume_mask).astype(np.uint8)
    border_surface += np.count_nonzero(np.logical_xor(surf_im[1:], surf_im[:-1])) * voxel_size[1] * voxel_size[2]
    border_surface += np.count_nonzero(np.logical_xor(surf_im[:, 1:], surf_im[:, :-1])) * voxel_size[0] * voxel_size[2]
    if len(surf_im.shape) == 3:
        border_surface += np.count_nonzero(np.logical_xor(surf_im[:, :, 1:], surf_im[:, :, :-1])) * voxel_size[0] * \
                          voxel_size[1]
    return border_surface


def opening_smooth(volume_mask, radius=1):
    volume_mask = volume_mask.astype(np.uint8)
    sitk_image = sitk.GetImageFromArray(volume_mask)
    opening_image = sitk.BinaryMorphologicalOpening(sitk_image, radius)
    return sitk.GetArrayFromImage(opening_image)


def closing_smooth(volume_mask, radius=1):
    volume_mask = volume_mask.astype(np.uint8)
    sitk_image = sitk.GetImageFromArray(volume_mask)
    closing_image = sitk.BinaryMorphologicalClosing(sitk_image, radius)
    return sitk.GetArrayFromImage(closing_image)


def calculate_statistic_from_image(img, mask, settings):
    """
    :type img: np.ndarray
    :type mask: np.ndarray
    :type settings: Settings
    :return: dict[str,object]
    """
    def pixel_volume(x):
        return x[0] * x[1] * x[2]
    res = dict()
    voxel_size = settings.voxel_size
    res["Volume"] = np.count_nonzero(mask) * pixel_volume(settings.voxel_size)
    res["Mass"] = np.sum(img)
    border_im = sitk.GetArrayFromImage(sitk.LabelContour(sitk.GetImageFromArray((mask > 0).astype(np.uint8))))
    res["Border Volume"] = np.count_nonzero(border_im)

    res["Border Surface"] = calculate_volume_surface(mask, voxel_size)
    # res["Border Surface Opening"] = calculate_volume_surface(opening_smooth(mask), voxel_size)
    # res["Border Surface Closing"] = calculate_volume_surface(closing_smooth(mask), voxel_size)
    img_mask = img > 0
    res["Pixel max"] = np.max(img)
    if np.any(img_mask):
        res["Pixel min"] = np.min(img[img_mask])
        res["Pixel mean"] = np.mean(img[img_mask])
        res["Pixel median"] = np.median(img[img_mask])
        res["Pixel std"] = np.std(img[img_mask])
    else:
        res["Pixel min"] = 0
        res["Pixel mean"] = 0
        res["Pixel median"] = 0
        res["Pixel std"] = 0
    try:
        res["Mass to Volume"] = res["Mass"] / res["Volume"]
        res["Volume to Border Surface"] = res["Volume"] / res["Border Surface"]
        # res["Volume to Border Surface Opening"] = res["Volume"] / res["Border Surface Opening"]
        # res["Volume to Border Surface Closing"] = res["Volume"] / res["Border Surface Closing"]
    except ZeroDivisionError:
        pass
    if len(img.shape) == 3:
        res["Moment of inertia"] = af.calculate_density_momentum(img, voxel_size)
    return res


def get_segmented_data(image, settings, segment, with_std=False, mask_morph=None, div_scale=1):
    """
    :param image: image from witch data should be catted
    :param settings: program settings
    :param segment: segment backend for program
    :param with_std: bool switch that enable returning information about noise outside segmented data
    :param mask_morph: function that do morphological operation on mask
    :type image: np.ndarray
    :type settings: Settings
    :type segment: Segment
    :type with_std: bool
    :type mask_morph: None | (np.ndarray) -> np.ndarray
    :type div_scale: float
    :return:
    """
    segmentation = segment.get_segmentation()
    if mask_morph is not None:
        logging.debug("No None morph_fun")
        segmentation = mask_morph(segmentation)
    else:
        logging.debug("None morph_fun")
    full_segmentation = segment.get_full_segmentation()
    image = image.astype(np.float)
    if settings.threshold_type == UPPER:
        noise_mean = np.mean(image[full_segmentation == 0])
        image = noise_mean - image
    image /= div_scale
    noise_std = np.std(image[full_segmentation == 0])
    image[segmentation == 0] = 0  # min(image[segmentation > 0].min(), 0)
    image[image < 0] = 0
    if with_std:
        return image, segmentation, noise_std
    return image, segmentation

ROTATION_MATRIX_DICT = {"x": np.diag([1, -1, -1]), "y": np.diag([-1, 1, -1]), "z": np.diag([-1, -1, 1])}


def save_to_cmap(file_path, settings, segment, gauss_type, with_statistics=True,
                 centered_data=True, morph_op=MorphChange.no_morph, scale_mass=(1,), rotate=None):
    """
    :type file_path: str
    :type settings: Settings
    :type segment: Segment
    :type gauss_type: GaussUse
    :type with_statistics: bool
    :type centered_data: bool
    :type morph_op: MorphChange
    :type scale_mass: (int)|list[int]
    :type rotate: str | None
    :return:
    """
    image = np.copy(settings.image)

    if gauss_type == GaussUse.gauss_2d or gauss_type == GaussUse.gauss_3d:
        image = segment.gauss_image
        logging.info("Gauss 2d")

    radius = 1
    if isinstance(morph_op, tuple) or isinstance(morph_op, list):
        radius = morph_op[1]
        morph_op = morph_op[0]
    if morph_op == MorphChange.no_morph:
        morph_fun = None
    elif morph_op == MorphChange.opening_morph:
        def morph_fun(img):
            logging.debug("Opening op radius {}".format(radius))
            return opening_smooth(img, radius)
    elif morph_op == MorphChange.closing_morph:
        def morph_fun(img):
            logging.debug("Closing op radius {}".format(radius))
            return closing_smooth(img, radius)
    else:
        logging.warning("Unknown morphological operation")
        morph_fun = None
    image, mask, noise_std = get_segmented_data(image, settings, segment, True, morph_fun, scale_mass[0])
    if gauss_type == GaussUse.gauss_3d:
        voxel = settings.spacing
        sitk_image = sitk.GetImageFromArray(image)
        sitk_image.SetSpacing(settings.spacing)
        image = sitk.GetArrayFromImage(sitk.DiscreteGaussian(sitk_image, max(voxel)))
        logging.info("Gauss 3d")

    points = np.nonzero(image)
    try:
        lower_bound = np.min(points, axis=1)
        upper_bound = np.max(points, axis=1)
    except ValueError:
        logging.error("No output")
        return
    f = h5py.File(file_path, "w")
    grp = f.create_group('Chimera/image1')

    cut_img = np.zeros(upper_bound - lower_bound + [3, 11, 11], dtype=image.dtype)
    coord = []
    for l, u in zip(lower_bound, upper_bound):
        coord.append(slice(l, u))
    pos = tuple(coord)
    cut_img[1:-2, 5:-6, 5:-6] = image[pos]
    z, y, x = cut_img.shape
    data_set = grp.create_dataset("data_zyx", (z, y, x), dtype='f')
    data_set[...] = cut_img

    if with_statistics:
        grp = f.create_group('Chimera/image1/Statistics')
        stat = calculate_statistic_from_image(image, mask, settings)
        for key, val in stat.items():
            grp.attrs[key] = val
        grp.attrs["Noise_std"] = noise_std

    # Just to satisfy file format
    grp = f['Chimera']
    grp.attrs['CLASS'] = np.string_('GROUP')
    grp.attrs['TITLE'] = np.string_('')
    grp.attrs['VERSION'] = np.string_('1.0')

    grp = f['Chimera/image1']
    grp.attrs['CLASS'] = np.string_('GROUP')
    grp.attrs['TITLE'] = np.string_('')
    grp.attrs['VERSION'] = np.string_('1.0')
    grp.attrs['step'] = np.array(settings.spacing, dtype=np.float32)

    if centered_data:
        swap_cut_img = np.swapaxes(cut_img, 0, 2)
        center_of_mass = af.density_mass_center(swap_cut_img, settings.spacing)
        model_orientation, eigen_values = af.find_density_orientation(swap_cut_img, settings.spacing, cutoff=2000)
        if rotate is not None:
            rotation_matrix, rotation_axis, angel = \
                af.get_rotation_parameters(np.dot(ROTATION_MATRIX_DICT[rotate], model_orientation.T))
        else:
            rotation_matrix, rotation_axis, angel = af.get_rotation_parameters(model_orientation.T)
        grp.attrs['rotation_axis'] = rotation_axis
        grp.attrs['rotation_angle'] = angel
        grp.attrs['origin'] = - np.dot(rotation_matrix, center_of_mass)

    data_set.attrs['CLASS'] = np.string_('CARRY')
    data_set.attrs['TITLE'] = np.string_('')
    data_set.attrs['VERSION'] = np.string_('1.0')

    f.close()


def save_to_project(file_path, settings, segment):
    """
    :type file_path: str
    :type settings: Settings
    :type segment: Segment
    :return:
    """
    folder_path = tempfile.mkdtemp()
    np.save(os.path.join(folder_path, "image.npy"), settings.image)
    np.save(os.path.join(folder_path, "draw.npy"), segment.draw_canvas)
    np.save(os.path.join(folder_path, "res_mask.npy"), segment.get_segmentation())
    if settings.image_clean_profile is not None:
        np.save(os.path.join(folder_path, "original_image.npy"), settings.original_image)
    if settings.mask is not None:
        np.save(os.path.join(folder_path, "mask.npy"), settings.mask)
    important_data = class_to_dict(settings, 'threshold_type', 'threshold_layer_separate', "threshold",
                                   "threshold_list", 'use_gauss', 'spacing', 'minimum_size', 'use_draw_result',
                                   "gauss_radius", "prev_segmentation_settings")
    if settings.image_clean_profile is not None:
        important_data["image_clean_profile"] = settings.image_clean_profile.__dict__
    else:
        important_data["image_clean_profile"] = None
    important_data["prev_segmentation_settings"] = deepcopy(important_data["prev_segmentation_settings"])
    for c, mem in enumerate(important_data["prev_segmentation_settings"]):
        np.save(os.path.join(folder_path, "mask_{}.npy".format(c)), mem["mask"])
        del mem["mask"]
    # image, segment_mask = get_segmented_data(settings.image, settings, segment)
    # important_data["statistics"] = calculate_statistic_from_image(image, segment_mask, settings)
    print(important_data)
    with open(os.path.join(folder_path, "data.json"), 'w') as ff:
        json.dump(important_data, ff)
    """if file_path[-3:] != ".gz":
        file_path += ".gz" """
    ext = os.path.splitext(file_path)[1]
    if ext.lower() in ['.bz2', ".tbz2"]:
        tar = tarfile.open(file_path, 'w:bz2')
    else:
        tar = tarfile.open(file_path, 'w:gz')
    for name in os.listdir(folder_path):
        tar.add(os.path.join(folder_path, name), name)
    tar.close()


def load_project(file_path, settings, segment):
    """
    :type file_path: str
    :type settings: Settings
    :type segment: Segment
    :return:
    """
    if sys.version_info.major == 2:
        def extract_numpy_file(name):
            return np.load(tar.extractfile(name))
    else:
        folder_path = tempfile.mkdtemp()

        def extract_numpy_file(name):
            tar.extract(name, folder_path)
            return np.load(os.path.join(folder_path, name))

    ext = os.path.splitext(file_path)[1]
    logging.debug("load_project extension: {}".format(ext))
    if ext.lower() in ['.bz2', ".tbz2"]:
        try:
            tar = tarfile.open(file_path, 'r:bz2')
        except tarfile.ReadError:
            tar = tarfile.open(file_path, 'r:gz')
    else:
        try:
            tar = tarfile.open(file_path, 'r:gz')
        except tarfile.ReadError:
            tar = tarfile.open(file_path, 'r:bz2')
    members = tar.getnames()
    json_val = tar.extractfile("data.json").read().decode("utf8")
    important_data = json.loads(json_val)
    image = extract_numpy_file("image.npy")
    draw = extract_numpy_file("draw.npy")
    if "mask.npy" in members:
        mask = extract_numpy_file("mask.npy")
    else:
        mask = None
    if "original_image.npy" in members:
        original_image = extract_numpy_file("original_image.npy")
        settings.image_clean_profile = Profile(**important_data["image_clean_profile"])
    else:
        original_image = None
        settings.image_clean_profile = None
    settings.threshold = int(important_data["threshold"])

    settings.threshold_type = important_data["threshold_type"]
    settings.use_gauss = bool(important_data["use_gauss"])
    settings.spacing = \
        tuple(map(int, important_data["spacing"]))
    settings.voxel_size = settings.spacing
    settings.minimum_size = int(important_data["minimum_size"])
    try:
        if "use_draw_result" in important_data:
            settings.use_draw_result = int(important_data["use_draw_result"])
        else:
            settings.use_draw_result = int(important_data["use_draw"])
    except KeyError:
        settings.use_draw_result = False
    segment.protect = True
    settings.add_image(image, file_path, mask, new_image=False, original_image=original_image)
    segment.protect = False
    if important_data["threshold_list"] is not None:
        settings.threshold_list = map(int, important_data["threshold_list"])
    else:
        settings.threshold_list = []
    if "threshold_layer_separate" in important_data:
        settings.threshold_layer_separate = \
            bool(important_data["threshold_layer_separate"])
    else:
        settings.threshold_layer_separate = \
            bool(important_data["threshold_layer"])
    if "gauss_radius" in important_data:
        settings.gauss_radius = important_data["gauss_radius"]
    else:
        settings.gauss_radius = 1

    if "prev_segmentation_settings" in important_data:
        for c, mem in enumerate(important_data["prev_segmentation_settings"]):
            mem["mask"] = extract_numpy_file("mask_{}.npy".format(c))
        settings.prev_segmentation_settings = important_data["prev_segmentation_settings"]
    else:
        settings.prev_segmentation_settings = []
    settings.next_segmentation_settings = []
    segment.draw_update(draw)
    segment.threshold_updated()
