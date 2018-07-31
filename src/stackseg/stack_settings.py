from typing import List

import numpy as np
from os import path
from partseg.io_functions import save_stack_segmentation, load_stack_segmentation
from project_utils.settings import BaseSettings
from stackseg.stack_algorithm.segment import cut_with_mask, save_catted_list

default_colors = ['BlackRed', 'BlackGreen', 'BlackBlue', 'BlackMagenta']


class StackSettings(BaseSettings):
    def __init__(self):
        super().__init__()
        self.chosen_components_widget = None

    @property
    def batch_directory(self):
        # TODO update batch widget to use new style settings
        return self.get("io.batch_directory", self.get("io.load_image_directory", ""))

    @batch_directory.setter
    def batch_directory(self, val):
        self.set("io.batch_directory", val)

    def save_result(self, dir_path: str):
        res_img = cut_with_mask(self.segmentation, self._image, only=self.chosen_components())
        res_mask = cut_with_mask(self.segmentation, self.segmentation, only=self.chosen_components())
        file_name = path.splitext(path.basename(self.image_path))[0]
        save_catted_list(res_img, dir_path, prefix=f"{file_name}_component")
        save_catted_list(res_mask, dir_path, prefix=f"{file_name}_component", suffix="_mask")

    def save_segmentation(self, file_path: str):
        save_stack_segmentation(file_path, self.segmentation, self.chosen_components(), self._image_path)

    def load_segmentation(self, file_path: str):
        self.segmentation, metadata = load_stack_segmentation(file_path)
        num = self.segmentation.max()
        self.chosen_components_widget.set_chose(range(1, num + 1), metadata["components"])

    def chosen_components(self) -> List[int]:
        if self.chosen_components_widget is not None:
            return sorted(self.chosen_components_widget.get_chosen())
        else:
            raise RuntimeError("chosen_components_widget do not initialized")

    def component_is_chosen(self, val: int) -> bool:
        if self.chosen_components_widget is not None:
            return self.chosen_components_widget.get_state(val)
        else:
            raise RuntimeError("chosen_components_widget do not idealized")

    def components_mask(self) -> np.ndarray:
        if self.chosen_components_widget is not None:
            return self.chosen_components_widget.get_mask()
        else:
            raise RuntimeError("chosen_components_widget do not initialized")