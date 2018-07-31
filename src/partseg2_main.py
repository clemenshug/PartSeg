if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    import argparse
    import sys
    import multiprocessing 
    multiprocessing.freeze_support()
    # import warnings
    # warnings.filterwarnings('error')
    from project_utils.global_settings import set_qt4, set_qt5, set_develop
    parser = argparse.ArgumentParser("Program for segment of connected components")
    parser.add_argument("file", nargs="?", help="file to open")
    parser.add_argument("-d", "--develop", dest="develop", default=False, const=True, action="store_const",
                        help=argparse.SUPPRESS)
    parser.add_argument("--multiprocessing-fork", dest="mf", nargs=1,
                        help=argparse.SUPPRESS) # Windows bugfix
    args = parser.parse_args()
    if args.qt4 and args.qt5:
        parser.print_help()
        parser.exit(-1)
    if args.qt4:
        set_qt4()

    if args.qt5:
        set_qt5()

    set_develop(args.develop)
    from PyQt5.QtWidgets import QApplication
    from partseg.main_window import MainWindow
    import sys
    myApp = QApplication(sys.argv)
    wind = MainWindow("PartSeg", args.file)
    wind.show()
    myApp.exec_()
    sys.exit()