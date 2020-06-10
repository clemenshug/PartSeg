from typing import NamedTuple, Dict, Optional, List

import numpy as np


class BoundInfo(NamedTuple):
    """
    Information about bounding box
    """

    lower: np.ndarray
    upper: np.ndarray

    def box_size(self) -> np.ndarray:
        """Size of bounding box"""
        return self.upper - self.lower + 1

    def get_slices(self) -> List[slice]:
        return [slice(x, y + 1) for x, y in zip(self.lower, self.upper)]


class SegmentationInfo:
    """
    Object to storage meta information about given segmentation.
    Segmentation array is only referenced, not copied.

    :ivar numpy.ndarray ~.segmentation: reference to segmentation
    :ivar Dict[int,BoundInfo] bound_info: mapping from component number to bounding box
    :ivar numpy.ndarray sizes: array with sizes of components
    """

    def __init__(self, segmentation: Optional[np.ndarray]):
        self.segmentation = segmentation
        self.bound_info = self.calc_bounds(segmentation) if segmentation is not None else {}
        self.sizes = np.bincount(segmentation.flat) if segmentation is not None else []

    @staticmethod
    def calc_bounds(segmentation: np.ndarray) -> Dict[int, BoundInfo]:
        """
        Calculate bounding boxes components

        :param np.ndarray segmentation: array for which bounds boxes should be calculated
        :return: mapping component number to bounding box
        :rtype: Dict[int, BoundInfo]
        """
        bound_info = {}
        count = np.max(segmentation)
        for i in range(1, count + 1):
            component = np.array(segmentation == i)
            if np.any(component):
                points = np.nonzero(component)
                lower = np.min(points, 1)
                upper = np.max(points, 1)
                bound_info[i] = BoundInfo(lower=lower, upper=upper)
        return bound_info