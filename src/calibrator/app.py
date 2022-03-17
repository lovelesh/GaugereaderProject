import cv2
import os
import numpy as np
import tkinter.ttk as ttk
import tkinter as tk
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import tkinter.simpledialog as sd
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageTk as ImageTk
import time
import typer

from copy import copy
from pathlib import Path

import src.utils.image_editing as ie
import src.utils.point_math as point_math
import src.utils.circle_dectection as cd
import src.utils.envconfig as env
import src.utils.convert_xml as xmlr


class Calibrator:
    def __init__(self,
                 calibration_image: str,
                 index: str,
                 camera_id: str = None):
        """
        A class that creates a GUI for the calibration process. This is the main class of the calibrator,
        Alone it does not do anything, uses as an archi-class for the AnalogCalibrator and the DigitalCalibrator.
        :param calibration_image:
        :param index:
        :param camera_id:
        """

        # Outer variables
        self.camera_id = camera_id
        self.index = index
        self.calibration_image = calibration_image

        # Inner variables
        # Paths
        self.directory, self.xml_file = env.dir_file_from_camera_gauge(camera_id, index)
        if self.calibration_image is None:
            self.calibration_image_path = None
        else:
            self.calibration_image_path = os.path.join(self.directory, self.calibration_image)
        self.train_image_path = Path(self.directory).joinpath(env.TRAIN_IMAGE_NAME).as_posix()
        self.current_image_path = None

        # Images
        self.backup_cv = None
        self.img_cv = None
        self.img_im = None

        # Calibration data and parameters
        self.draw_params = {}  # placeholder for params of image editing
        self.calibration = {}
        self.current_reading = 0

        # Specific Buttons and top frames containers
        self.step_buttons = {}
        self.buttons = {}
        self.top_frames = {}

        # BOOL variables for error checking
        self.error_flags = {'cropped': False,
                            'perspective': False,
                            'parameters': False}

        # Image variables
        self.w, self.h = None, None

        # Root Window settings
        self.window = tk.Tk()
        self.create_main_window()
        self.canvas = None
        self.canvas_image = None
        self.grid_size = 50
        self.button_width = 18

        # Menubar Frame
        self.menubar = tk.Menu(self.window)
        self.create_menu_bar_frame()

        # Main toolbar Frame # TODO: add editor functions
        self.toolbar_frame = tk.Frame(self.window)
        self.brush_size_bar = None
        self.brush_size = 8  # default brush size
        self.create_toolbar_frame()

        # Image Frame settings
        self.image_frame = tk.Frame(master=self.window, width=env.WINDOW_SIZE[0], height=env.WINDOW_SIZE[1])
        self.image_frame.configure(background='gray')

        # Image editing frame
        self.image_edit_controls = {}

        # Gauge specific steps
        self.gauge_steps_frame = None
        self.create_gauge_steps_frame()

        # Image editing variables
        self.active_button = None
        self.active_shape = None
        self.perspective_bars = {}

        # Calibration specific toolbar
        self.calibration_toolbar = None
        self.create_calibration_toolbar()

        # Location Variables for drawing and locating items
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.drawn = None
        self.color = 'red'
        self.draw = None

        # Perspective transform variables
        self.perspective = ie.Perspective()
        self.perspective_bars = dict.fromkeys(self.perspective.point_names)
        self.perspective_im = None

    def create_main_window(self):
        """
        Creates the main window of the calibrator.
        :return:
        """
        self.window.title("Calibrator App")
        self.window.resizable(width=True, height=True)
        self.window.configure(background='#ffffff')

    def create_menu_bar_frame(self):
        """
        Creates the menubar frame of the calibrator. Each subclass of the calibrator will have its
        own menubar changes done later
        :return:
        """
        file = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label='File', menu=file)
        file.add_command(label='Change Calibration Image', command=self.change_calibration_image)
        file.add_command(label='Save to XML', command=self.save_calibration_data)
        file.add_command(label='Exit', command=self.window.destroy)
        self.menubar.add_cascade(label='Help', command=lambda: None)  # TODO: add help menu images for workflows
        self.window.config(menu=self.menubar)

    def create_toolbar_frame(self):
        """
        Creates the toolbar frame of the calibrator. Each subclass of the calibrator will have its
        :return:
        """
        self.toolbar_frame = tk.Frame(self.window)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.BOTH)
        tk.Button(self.toolbar_frame, text='Reset', command=self.load_image_from_file).pack(side=tk.LEFT)
        tk.Button(self.toolbar_frame, text='Edit', command=self.create_image_edit_frame).pack(side=tk.LEFT)
        self.brush_size_bar = tk.Scale(self.toolbar_frame, from_=1, to=50, orient=tk.HORIZONTAL, label='Line width')
        self.brush_size_bar.set(self.brush_size)
        self.brush_size_bar.pack(side=tk.RIGHT)

    def create_image_edit_frame(self):  # TODO: implement color options, perspective correction, etc.
        """
        Creates the image editing frame of the calibrator. Save calibration data to calibration data
        :return:
        """
        self.backup_cv = self.img_cv.copy()
        self.top_frames['edit'] = tk.Toplevel(self.window,
                                              width=300,
                                              height=300,
                                              background='gray')
        self.top_frames['edit'].resizable(width=True, height=True)
        self.image_edit_controls['rotate'] = tk.Scale(self.top_frames['edit'],
                                                      from_=-180,
                                                      to=180,
                                                      command=self.rotate_image,
                                                      orient=tk.HORIZONTAL,
                                                      label='Rotate')

        for element in self.image_edit_controls:
            self.image_edit_controls[element].pack(side=tk.TOP)

    def create_gauge_steps_frame(self):
        """
        Create the generic frame for gauge calibration steps
        :return:
        """
        self.gauge_steps_frame = tk.Frame(self.window)
        self.gauge_steps_frame.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(self.gauge_steps_frame, text='Steps').pack(side=tk.TOP)
        self.step_buttons['crop'] = tk.Button(self.gauge_steps_frame,
                                              text="Crop",
                                              width=self.button_width,
                                              bg='red',
                                              command=self.use_crop)
        self.step_buttons['set_perspective'] = tk.Button(self.gauge_steps_frame,
                                                         text='Set Perspective',
                                                         width=self.button_width,
                                                         bg='red',
                                                         command=self.create_perspective_frame)

    def create_perspective_frame(self):
        """
        Create the perspective frame for gauge calibration steps
        :return:
        """
        if not self.error_flags['cropped']:
            message = 'Please crop the image before setting the perspective'
            mb.showerror('Error', message)
            return
        self.step_buttons['set_perspective'].config(bg='green')
        self.error_flags['perspective'] = True
        self.backup_cv = self.img_cv.copy()
        self.top_frames['perspective'] = tk.Toplevel(self.window,
                                                     name='perspective',
                                                     width=200,
                                                     height=200)
        self.top_frames['perspective'].title('Set Perspective')
        self.perspective.reset(self.w)
        tk.Button(self.top_frames['perspective'],
                  text='Set Points',
                  command=self.use_set_perspective_points).pack(side=tk.TOP)
        for bar in self.perspective_bars.keys():
            self.perspective_bars[bar] = tk.Scale(self.top_frames['perspective'],
                                                  from_=-self.w,
                                                  to=self.w,
                                                  command=self.bar_change_perspective,
                                                  orient=tk.HORIZONTAL,
                                                  label=bar)
            if bar in ['tl_x', 'tl_y', 'tr_y', 'bl_x']:
                self.perspective_bars[bar].set(0)
            elif bar in ['tr_x', 'br_x']:
                self.perspective_bars[bar].set(self.w)
            else:
                self.perspective_bars[bar].set(self.h)
            self.perspective_bars[bar].pack(side=tk.TOP)
        tk.Button(self.top_frames['perspective'],
                  text='Reset Perspective',
                  command=self.reset_perspective).pack(side=tk.TOP)

    def create_calibration_toolbar(self):
        """
        Create the generic toolbar for gauge calibration
        :return:
        """
        self.calibration_toolbar = tk.Frame(self.window,
                                            width=env.WINDOW_SIZE[0],
                                            height=env.WINDOW_SIZE[1])
        self.calibration_toolbar.pack(side=tk.BOTTOM, fill=tk.BOTH)

    def create_canvas(self,
                      file: str = 'img.ppm'):
        """
        Creates the canvas of the calibrator.
        :return:
        """
        if self.canvas is not None:
            self.canvas.destroy()
            self.canvas = None
        self.canvas = tk.Canvas(self.image_frame,
                                bg='black',
                                width=self.w,
                                height=self.h,
                                cursor="cross")
        self.canvas_image = self.canvas.create_image(0, 0, image=self.img_im, anchor=tk.NW)
        self.canvas.place(anchor=tk.CENTER, relx=0.5, rely=0.5)
        self.canvas.pack(anchor=tk.CENTER, padx=10, pady=10)
        self.image_frame.place(anchor=tk.CENTER, relx=0.5, rely=0.5)
        self.image_frame.pack(side=tk.TOP, anchor=tk.CENTER, padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.add_grid_to_canvas()

    def add_grid_to_canvas(self):
        """
                Add a grid to the canvas
                :return:
                """
        for line in range(0, self.w, self.grid_size):
            self.canvas.create_line(line, 0, line, self.h, fill='#ffffff', tag='grid')
        for line in range(0, self.h, self.grid_size):
            self.canvas.create_line(0, line, self.w, line, fill='#ffffff', tag='grid')

    # Image loading methods
    def load_image_from_file(self,
                             image_name: str = None,
                             prompt: bool = False):
        """
        Load an image from a file
        :param image_name:
        :param prompt: If true, prompt the user a warning for resetting the image
        :return:
        """
        if image_name is None:
            image_name = self.calibration_image
        self.reset_to_start(prompt=prompt)
        path = Path(self.directory).joinpath(image_name).as_posix()
        self.current_image_path = path
        self.img_cv = cv2.imread(self.current_image_path)
        if self.img_cv is None:
            raise Exception("Image not found / not readable")
        self.update_main_image(self.img_cv)

    def update_main_image(self,
                          image=None,
                          keep_window: bool = False,
                          resize: bool = True):
        """
        Updates the main image of the calibrator. This will also update the canvas and the image frame,
        and the relevant size variables.
        :param image:
        :param keep_window:
        :param resize:
        :return:
        """
        if image is None:
            image = self.img_cv
        if isinstance(image, Image.Image):
            image.convert('RGB')
            self.img_cv = np.array(image)
            self.img_im = ImageTk.PhotoImage(image)
        elif isinstance(image, ImageTk.PhotoImage):
            self.img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            self.img_im = image
        else:
            self.img_cv = image
            self.img_im = ie.cv_to_imagetk(self.img_cv)
        if resize:
            self.img_cv = self.resize_cv(self.img_cv)
            self.img_im = ie.cv_to_imagetk(self.img_cv)
        else:
            self.h = self.img_cv.shape[0]
            self.w = self.img_cv.shape[1]
        self.create_canvas()
        w_w, w_h = int(self.w * 1.5), int(self.h * 1.2)
        if not keep_window:
            self.window.geometry(f'{w_w}x{w_h}')
        self.show_image()

    def change_calibration_image(self,
                                 prompt: bool = True):
        """
        Opens the image from the file dialog. This will change the original calibration image.
        :param prompt: If true, prompt the user a warning for resetting the image
        :return: calibration image path
        """
        if prompt and self.calibration_image is not None:
            tk.messagebox.showwarning('Warning',
                                      'This will reset all calibration data and replace calibration image path')
        try:
            self.calibration_image_path = fd.askopenfilename(initialdir=env.CALIBRATION_PATH,
                                                             title="Select Calibration Image",
                                                             filetypes=(("jpeg files", "*.jpg"), ("all files", "*.*")))
        except TypeError:
            return
        if isinstance(self.calibration_image_path, tuple):
            return None
        self.directory = Path(self.calibration_image_path).parent.as_posix()
        self.calibration_image = os.path.basename(self.calibration_image_path)
        self.load_image_from_file(self.calibration_image)
        return self.calibration_image_path

    def resize_cv(self,
                  image: np.ndarray):
        """
        Resizes the image to the size of the window.
        :param image: cv2 image (ndarray)
        :return: resized cv2 image (ndarray)
        """
        h = image.shape[0]
        w = image.shape[1]
        self.w = int(w * env.WINDOW_SIZE[0] / w)
        self.h = int(h * env.WINDOW_SIZE[1] / w)
        image = cv2.resize(image, (self.w, self.h), interpolation=cv2.INTER_AREA)
        return image

    def rotate_image(self, event):
        """
        Rotates the image according to the 'Rotate' scale in the image edit frame
        :param event:
        :return:
        """
        self.update_main_image(self.backup_cv)
        angle = self.image_edit_controls['rotate'].get()
        rotated = ie.rotate_image(self.img_cv, angle)
        self.update_main_image(rotated)

    def draw_shape(self):
        """
        Draws the shape on the canvas. This is used to make the drawing "flexible" and allow less
        duplicated code for different shapes drawing.
        :return: None
        """
        self.canvas.bind('<ButtonPress-1>', self.on_start)
        self.canvas.bind("<ButtonRelease-1>", self.on_stop)
        self.canvas.bind("<Double-1>", self.on_clear)
        if self.draw_params['tag'] is not 'perspective':
            self.canvas.bind("<ButtonRelease-3>", self.on_move)
            self.canvas.bind("<B1-Motion>", self.on_grow)

    def draw_point(self, event):
        """
        Draws a point on the canvas.
        :return:
        """
        x = event.x
        y = event.y
        self.canvas.create_oval(x, y, x, y,
                                fill=self.draw_params['fill'],
                                width=self.draw_params['width'],
                                tag=self.draw_params['tag'])

    def on_start(self, event):
        """
        This function is called when the user clicks on the canvas.
        :param event: tkinter event
        :return: None
        """
        self.start_x, self.start_y = event.x, event.y
        if self.draw_params['tag'] is 'crop':
            self.draw_params['width'] = 3
        else:
            self.draw_params['width'] = self.brush_size_bar.get()
        self.drawn = None

    def on_grow(self, event):
        """
        This function is called when the user moves the mouse on the canvas.
        :param event:
        :return:
        """
        canvas = event.widget
        if self.drawn:
            canvas.delete(self.drawn)
        if 'tag' in self.draw_params.keys():
            self.canvas.delete(self.draw_params['tag'])
        shape = self.active_shape
        line = shape(self.start_x,
                     self.start_y,
                     event.x,
                     event.y,
                     **self.draw_params)
        self.drawn = line

    def on_clear(self, event):
        """
        This function is called when the user double-clicks on the canvas.
        :param event: tkinter event
        :return: None
        """
        event.widget.delete(self.draw_params['tag'])

    def on_move(self, event):
        """
        This function is called when the user releases the right mouse button on the canvas.
        :param event: tkinter event
        :return: None
        """
        if self.drawn:
            canvas = event.widget
            diff_x, diff_y = event.x - self.start_x, event.y - self.start_y
            canvas.move(self.drawn, diff_x, diff_y)
            self.start_x, self.start_y = event.x, event.y

    def on_stop(self, event):
        """
        This function is called when the user releases the left mouse button on the canvas.
        :param event: tkinter event
        :return: None
        """
        self.end_x, self.end_y = event.x, event.y
        if self.draw_params['tag'] == 'crop':
            self.crop_image()
        elif self.draw_params['tag'] is 'perspective':
            self.draw_change_perspective(event)
        self.stop_actions()

    def stop_actions(self):
        """
        This function is called when the user stops drawing on the canvas. Specific implementation
        is needed for subclasses
        :return: None
        """
        pass

    def use_set_perspective_points(self):
        """
        This function is called when the user clicks on the "Set Perspective Points" button.
        :return: None
        """
        self.draw_params = dict(tag='perspective',
                                width=20,
                                outline='yellow',
                                fill='yellow')
        self.active_shape = self.canvas.create_oval
        self.draw_shape()

    def four_points_perspective_transform(self):
        """
        Transforms the image according to the set points
        :return:
        """
        self.img_cv = ie.four_point_transform(self.img_cv, self.perspective.points)
        self.apply_crop(0, 0, self.img_cv.shape[1], self.img_cv.shape[0], resize=False)
        self.canvas.delete('perspective')

    def bar_change_perspective(self,
                               event: object = None):
        """
        Change the perspective transform points when the user moves the slider
        :return: None
        """
        self.img_cv = self.backup_cv.copy()
        scales = [bar.get() for bar in self.perspective_bars.values()]
        self.perspective.set_points(scales, order=False)
        self.four_points_perspective_transform()

    def draw_change_perspective(self, event):
        """
        Draw the perspective transform points when the user moves the mouse
        :return: None
        """
        if len(self.perspective.draw) < 4:
            self.perspective.draw.append((event.x, event.y))
            self.canvas.delete('perspective_polygon')
            self.canvas.create_polygon(self.perspective.draw,
                                       fill='',
                                       outline='red',
                                       width=2,
                                       tag='perspective_polygon')
            self.draw_point(event)
        elif len(self.perspective.draw) == 4:
            self.perspective.set_points()
            for bar in self.perspective_bars.keys():
                self.perspective_bars[bar].set(self.perspective[bar])
            self.perspective.delete_draw()

    def reset_perspective(self):
        """
        Reset the perspective transform points
        :return: None
        """
        self.img_cv = self.backup_cv.copy()
        self.perspective.reset(self.w)
        for bar in self.perspective_bars.keys():
            self.perspective_bars[bar].set(self.perspective[bar])

    def use_crop(self):
        """
        This function is called when the user clicks on the crop button.
        :return:
        """
        self.load_image_from_file()
        self.canvas.delete('crop')
        self.draw_params = dict(tag='crop', outline='black')
        self.step_buttons['crop'].config(relief='sunken')
        self.active_shape = self.canvas.create_rectangle
        self.draw_shape()

    def crop_image(self):
        """
        Crop the image to the rectangle defined by the start and end points, force square size for training
        :return:
        """
        diff_x, diff_y = self.end_x - self.start_x, self.end_y - self.start_y
        diff = max(diff_x, diff_y)
        x, y = self.start_x, self.start_y
        x_diff, y_diff = self.start_x + diff, self.start_y + diff
        self.step_buttons['crop'].config(bg='green')
        self.calibration['crop'] = (y, y_diff, x, x_diff)
        self.apply_crop(x, y, x_diff, y_diff, resize=False)

    def apply_crop(self,
                   x: int,
                   y: int,
                   x_diff: int,
                   y_diff: int,
                   resize: bool = False):
        """
        Crop the image to the rectangle defined by the start and end points, force square size for training,
        save the image and update the image frame
        :param x: int x coordinate of the top left corner of the rectangle
        :param y: int y coordinate of the top left corner of the rectangle
        :param x_diff: int x distance of the bottom right corner of the rectangle
        :param y_diff: int y distance of the bottom right corner of the rectangle
        :param resize: bool whether to resize the image to a square
        :return: None
        """
        cropped_image = self.img_cv[y:y_diff, x:x_diff]
        cropped_image = cv2.resize(cropped_image, env.EDIT_IMAGE_SIZE)
        self.img_cv = cropped_image
        self.update_main_image(keep_window=True,
                               resize=resize)
        self.step_buttons['crop'].config(relief='raised')
        self.error_flags['cropped'] = True

    def show_image(self,
                   image: ImageTk.PhotoImage or np.ndarray = None):
        """
        Show the image in the main image frame. If image is None, show the image in self.proc_im
        :param image:
        :return: None
        """
        if image is None:
            self.canvas.itemconfig(self.canvas_image, image=self.img_im, tag='canvas_image')
            return
        elif isinstance(image, np.ndarray):
            image = ie.cv_to_imagetk(image)
        self.canvas.itemconfig(self.canvas_image, image=image, tag='canvas_image')

    def reset_error_flags(self,
                          except_for: list or str = None):
        """
        Reset all the parameters to their default values - view original image
        :return:
        """
        if except_for is None:
            except_for = []
        elif isinstance(except_for, str):
            except_for = [except_for]
        for item in self.error_flags.keys():
            if item not in except_for:
                self.error_flags[item] = False

    def reset_to_start(self,
                       prompt: bool = True):
        """
        Reset all the parameters to their default values - view original image
        :return:
        """
        msg = "Are you sure you want to reset the image? This will delete all edits and reset parameters."
        if prompt:
            check = tk.messagebox.askokcancel("Reset", msg)
        else:
            check = True
        if check:
            self.reset_error_flags()
            for button in self.step_buttons.keys():
                self.step_buttons[button].config(bg='red')
            for top in self.top_frames.values():
                if top is not None:
                    top.destroy()
        return

    def set_calibration_parameters(self):
        """
        Set the calibration parameters for the current image, specific method for Digital/Analog
        :return:
        """
        pass

    def save_calibration_data(self):
        """
        Save to XML the calibration data
        :return:
        """
        pass

    def run(self):
        """
        Runs the main loop.
        :return:
        """
        self.window.mainloop()
        return self.calibration


class AnalogCalibrator(Calibrator):
    def __init__(self,
                 calibration_image: str,
                 index: str,
                 camera_id: str = None):
        super().__init__(calibration_image=calibration_image,
                         index=index,
                         camera_id=camera_id)

        # Paths
        self.needle_image_path = Path(self.directory).joinpath(env.NEEDLE_IMAGE_NAME).as_posix()

        # Images
        self.train_image = None
        self.needle_image = None
        self.centered_needle_image = None
        self.rotated_im = None
        self.mask = None

        # Calibration Data Parameters
        self.tags = ['crop',
                     'needle',
                     'max_line',
                     'min_line',
                     'center',
                     'gauge',
                     'no_circles']
        self.x = 0  # Gauge center x
        self.y = 0  # Gauge center y
        self.r = 0  # Gauge radius
        self.crop_detection = {'min_r': 0,  # parameters for auto crop detection
                               'max_r': 0,
                               'min_d': 0}
        self.zero_angle = 0
        self.angle_deviation = 0
        self.value_diff = 0
        self.angle_diff = 0
        self.value_step = 0

        # add error flags
        flags = ['zero_needle_rotation',
                 'circles',
                 'needle_found',
                 'min_found',
                 'max_found',
                 'reading_tested']
        for flag in flags:
            self.error_flags[flag] = False

        # Crop Control Tools - GUI
        self.crop_mode = tk.StringVar(self.window)

        # Find Needle Frame (finding the needle and the calibration circle)
        self.find_needle_frame = None
        self.text_params = {'min_value': 0,
                            'max_value': 0,
                            'units': ''}

        # Circle Detection and gauge text parameters Frame
        self.circle_frame = None
        self.circle_detection_scales = {key: None for key in ['min_r', 'max_r', 'min_d']}

        # Needle rotation frame
        self.needle_rotation_scale = None
        self.add_calibration_toolbar_frame()

        # Add gauge steps
        self.add_toolbar_buttons()
        self.add_gauge_steps_frame()

        # Open Image and run
        if self.calibration_image is not None:
            self.load_image_from_file(image_name=calibration_image)

    # Specific Frames and Widgets for Analog Calibration
    def add_toolbar_buttons(self):
        """
        Add the buttons to the toolbar specific to the analog calibrator
        :return:
        """
        crop_options = ['Auto Crop', 'Manual Crop']
        self.crop_mode.set(crop_options[0])
        self.buttons['crop_options'] = tk.OptionMenu(self.toolbar_frame,
                                                     self.crop_mode,
                                                     *crop_options)
        self.buttons['crop_options'].pack(side=tk.LEFT)

    def add_gauge_steps_frame(self):
        """
        Add the gauge steps frame to the calibrator
        :return:
        """
        self.button_width = 18
        self.step_buttons['crop'].config(command=self.set_crop_mode)
        self.step_buttons['circle_detection'] = tk.Button(self.gauge_steps_frame,
                                                          text='Circle Detection',
                                                          width=self.button_width,
                                                          bg='red',
                                                          command=self.create_circle_detection_frame)
        self.step_buttons['needle_detection'] = tk.Button(self.gauge_steps_frame,
                                                          text='Needle Detection',
                                                          width=self.button_width,
                                                          bg='red',
                                                          command=self.create_find_needle_frame)
        self.step_buttons['set_zero'] = tk.Button(self.gauge_steps_frame,
                                                  text='Set Zero Angle',
                                                  width=self.button_width,
                                                  bg='red',
                                                  command=self.set_zero_needle_rotation)
        self.step_buttons['set_min'] = tk.Button(self.gauge_steps_frame,
                                                 text='Set Min Angle',
                                                 width=self.button_width,
                                                 bg='red',
                                                 command=self.set_min_needle_rotation,
                                                 name='set')
        self.step_buttons['set_max'] = tk.Button(self.gauge_steps_frame,
                                                 text='Set Max Angle',
                                                 width=self.button_width,
                                                 bg='red',
                                                 command=self.set_max_needle_rotation,
                                                 name='max')
        self.step_buttons['test_reading'] = tk.Button(self.gauge_steps_frame,
                                                      text='Test Reading',
                                                      width=self.button_width,
                                                      bg='red',
                                                      command=self.test_reading)
        self.buttons['show_masked'] = tk.Button(self.gauge_steps_frame,
                                                text='Show Masked Needle',
                                                width=self.button_width,
                                                command=self.show_masked_needle)
        self.buttons['re_config'] = tk.Button(self.gauge_steps_frame,
                                              text='Re-Config Reading',
                                              width=self.button_width,
                                              command=self.re_config_reading)

        for button in self.step_buttons.values():
            button.pack(side=tk.TOP)
        for button in ['show_masked', 're_config']:
            self.buttons[button].pack(side=tk.BOTTOM)

    def add_calibration_toolbar_frame(self):
        """
        Create the needle rotation frame - specific gauge calibration toolbar
        :return:
        """
        reading_text = f'Value: {self.current_reading}'
        self.needle_rotation_scale = tk.Scale(self.calibration_toolbar,
                                              from_=360,
                                              to=-360,
                                              orient=tk.HORIZONTAL,
                                              label='Rotate Needle',
                                              resolution=0.0001,
                                              command=self.rotate_needle,
                                              length=360,
                                              state=tk.DISABLED,
                                              width=25)
        self.buttons['current_value'] = tk.Button(self.calibration_toolbar,
                                                  text=reading_text)
        self.needle_rotation_scale.pack(side=tk.RIGHT)
        self.buttons['current_value'].pack(side=tk.TOP)

    def create_find_needle_frame(self):
        """
        Creates the frame for the needle finding and calibration the gauge text parameters
        :return:
        """  # TODO: check how to not allow 2 frames to be created at the same time
        if self.flag_error_check('perspective'):
            return
        self.find_needle_frame = tk.Toplevel(master=self.window,
                                             width=200,
                                             height=300)
        dense = tk.TOP
        self.step_buttons['find_needle'] = tk.Button(self.find_needle_frame, text='Find Needle',
                                                     command=self.use_mark_needle)
        self.step_buttons['find_needle'].pack(side=dense)
        for key in self.text_params:
            self.text_params[key] = tk.Entry(self.find_needle_frame,
                                             width=10,
                                             name=key,
                                             bd=5)
            temp = tk.Label(self.find_needle_frame,
                            text=key)
            temp.pack(side=tk.TOP)
            self.text_params[key].pack(side=tk.TOP)
        ttk.Button(self.find_needle_frame, text='Set', command=self.set_text_parameters).pack(side=tk.TOP)
        self.use_mark_needle()

    def create_circle_detection_frame(self):
        """
        Creates a frame with a button to detect circles and set parameters.
        :return:
        """
        self.circle_frame = tk.Toplevel(self.window)
        self.circle_frame.title("Circle Detection")
        self.circle_frame.geometry('500x300')
        tk.Label(self.circle_frame, text="Circle Detection").pack(side=tk.TOP)
        tk.Button(self.circle_frame, text="Auto Detect", command=self.auto_find_circles).pack(side=tk.TOP)
        tk.Label(self.circle_frame, text='Auto detect tweaks minimum radius and max radius \n'
                                         'If not found, try tweaking other parameters.').pack(side=tk.TOP)
        for key in self.circle_detection_scales.keys():
            self.circle_detection_scales[key] = tk.Scale(self.circle_frame,
                                                         from_=1,
                                                         to=self.img_cv.shape[0],
                                                         orient=tk.VERTICAL,
                                                         label=key,
                                                         command=self.man_find_circles)
            self.circle_detection_scales[key].pack(side=tk.LEFT, anchor=tk.CENTER)
        self.circle_detection_scales['min_r'].set(self.w / 3)
        self.circle_detection_scales['max_r'].set(1)
        self.circle_detection_scales['min_d'].set(1)

    # Specific stop_actions method for Analog Calibration
    def stop_actions(self):
        """
        Analog class specific stop method
        :return:
        """
        # Gather the needle coordinates (from the drawn line) to mask the train image (inpainting)
        self.calibration[self.draw_params['tag']] = {'point1': (self.start_x, self.start_y),
                                                     'point2': (self.end_x, self.end_y)}
        if self.draw_params['tag'] == 'needle':
            self.error_flags['needle_found'] = True
            self.calibration['needle']['width'] = self.draw_params['width']
            self.mask_needle()

    # Find needle methods
    def use_mark_needle(self):
        """
        Use the mark needle button to mark the needle
        :return: None
        """
        self.step_buttons['find_needle'].config(relief=tk.SUNKEN)
        self.draw_params = dict(tag='needle', fill='white')
        self.active_shape = self.canvas.create_line
        self.draw_shape()

    # Specific crop methods for Analog Calibration
    def set_crop_mode(self):
        """
        Change auto/manual crop
        :return:
        """
        if self.crop_mode.get() == 'Auto Crop':
            self.auto_circle_crop()
        elif self.crop_mode.get() == 'Manual Crop':
            self.use_crop()

    def auto_circle_crop(self):
        """
        Automatically crop the image from a circle
        :return:
        """
        self.reset_crop_detection()
        self.auto_find_circles(auto_crop=True)
        r_param = 1.5  # arbitrary value that by trial and error seems to work
        square_side = int(self.r * 2.2)
        x_origin, y_origin = point_math.point_pos(self.x, self.y, self.r * r_param, 225)
        x, y = x_origin, y_origin
        x_diff, y_diff = x_origin + square_side, y_origin + square_side
        self.apply_crop(x, y, x_diff, y_diff)
        self.step_buttons['crop'].config(bg='green')

    def reset_crop_detection(self,
                             min_r: int = 3,
                             max_r: int = 2,
                             min_d: int = 3):
        """
        Reset the crop detection parameters
        :param min_r: minimum radius
        :param max_r: maximum radius
        :param min_d: minimum distance
        :return: None
        """
        self.crop_detection['min_r'] = self.w // min_r
        self.crop_detection['max_r'] = self.w // 3
        self.crop_detection['min_d'] = self.w // min_d

    # Circle Detection Methods
    def man_find_circles(self,
                         tweak: bool = False,
                         auto_crop: bool = False):
        """
        Manually detect circles with the current parameters
        :param auto_crop:
        :param tweak:
        :return:
        """
        tk.Canvas.create_circle = ie.create_circle
        for tag in ['center', 'gauge', 'no_circles']:
            self.canvas.delete(tag)
        if auto_crop:
            min_r = self.crop_detection['min_r']
            max_r = self.crop_detection['max_r']
            min_d = self.crop_detection['min_d']
        else:
            min_r = self.circle_detection_scales['min_r'].get()
            max_r = self.circle_detection_scales['max_r'].get()
            min_d = self.circle_detection_scales['min_d'].get()

        circles = cd.find_circles(self.img_cv,
                                  min_r,
                                  max_r,
                                  min_d)
        if not circles:
            self.canvas.create_text(150, 150,
                                    text='No circles found',
                                    font=('Arial', 20),
                                    fill='red',
                                    tag='no_circles')
            self.step_buttons['circle_detection'].config(bg='red')
            if tweak:
                self.tweak_circle_params(min_r, max_r, auto_crop)
            return False
        else:
            x, y, r = circles
            self.x, self.y, self.r = x, y, r
            self.error_flags['circles'] = True
            if tweak:
                self.tweak_circle_params(min_r, max_r, auto_crop)
            self.canvas.create_circle(x, y, r, tag='gauge', width=3, outline='green')
            self.canvas.create_circle(x, y, 5, fill='red', tag='center')
            self.img_im = ie.cv_to_imagetk(self.img_cv)
            self.show_image()
            if not auto_crop:
                self.step_buttons['circle_detection'].config(bg='green')
            return x, y, r

    def tweak_circle_params(self,
                            min_r,
                            max_r,
                            auto_crop: bool = False):
        if min_r < self.img_cv.shape[0] / 2:
            if auto_crop:
                self.crop_detection['min_r'] = min_r + 1
            else:
                if self.circle_detection_scales['min_r'] is not None:
                    self.circle_detection_scales['min_r'].set(min_r + 1)
        if max_r > 1:
            if auto_crop:
                self.crop_detection['max_r'] = max_r - 1
            else:
                if self.circle_detection_scales['max_r'] is not None:
                    self.circle_detection_scales['max_r'].set(max_r + 1)

    def auto_find_circles(self,
                          auto_crop: bool = False):
        """
        Apply circle detection Automatically
        :param auto_crop:
        :return: None
        """
        circles = False
        self.canvas.delete('circles')
        timeout = time.time() + 10
        while not circles:
            if time.time() > timeout:
                break
            circles = self.man_find_circles(auto_crop=auto_crop,
                                            tweak=True)
        if circles:
            self.x, self.y, self.r = circles

    def set_text_parameters(self):
        """
        Set the text parameters, gathered in circle detection frame.
        :return:  None
        """
        if self.flag_error_check('needle_found'):
            return
        for key in self.text_params.keys():
            try:
                if key is not 'units':
                    self.calibration[key] = float(self.text_params[key].get())
                else:  # units
                    units = self.text_params[key].get()
                    units = units[0].upper() + units[1:].lower()
                    self.calibration[key] = units
            except ValueError:
                message = "Please set the parameters first."
                mb.showerror('Error', message)
                return
        self.error_flags['parameters_set'] = True
        self.canvas.unbind('<Button-1>')
        self.canvas.unbind('<Button-3>')
        self.step_buttons['find_needle'].config(relief=tk.RAISED)
        self.step_buttons['needle_detection'].config(bg='green')
        self.needle_rotation_scale.config(state=tk.NORMAL)
        self.find_needle_frame.destroy()

    def mask_needle(self):
        """
        Creates two separate images: one with the needle and one without. The images
        are saved in the gauge's directory in a 'jpeg' format.
        :return: None
        """
        self.mask = np.zeros(self.img_cv.shape[:2], dtype=np.uint8)
        cv2.line(self.mask,
                 self.calibration['needle']['point1'],
                 self.calibration['needle']['point2'],
                 (255, 0, 0),
                 thickness=self.calibration['needle']['width'])
        self.needle_image = cv2.bitwise_and(self.img_cv, self.img_cv, mask=self.mask)
        self.train_image = cv2.inpaint(self.img_cv, self.mask, 3, cv2.INPAINT_TELEA)

    def show_masked_needle(self):
        """
        Show the masked needle image and the train image in a separate window.
        :return: None
        """
        if self.mask_needle is None or self.train_image is None:
            message = "Please Find the needle and set parameters first"
            mb.showerror('Error', message)
            return
        ie.cv_to_image(self.needle_image, show=True)
        ie.cv_to_image(self.train_image, show=True)

    def rotate_needle(self,
                      event=None,
                      show: bool = True,
                      angle=None):
        """
        Rotate the needle image and show it in the canvas.
        :param show:
        :param event: tkinter event (not used, but required)
        :param angle: angle relative to the needle's center
        :return: rotated needle image
        """
        self.canvas.itemconfig('needle', state=tk.HIDDEN)
        if angle is None:
            angle = self.needle_rotation_scale.get()
        angle += self.angle_deviation
        rotated, needle = ie.rotate_needle(train_image=self.train_image,
                                           needle_image=self.needle_image,
                                           needle_center=(self.x, self.y),
                                           needle_angle=angle)

        if show:
            self.rotated_im = ie.cv_to_imagetk(rotated)
            self.show_image(self.rotated_im)
            if self.error_flags['reading_tested']:
                self.update_reading_button()
        return needle

    def set_zero_needle_rotation(self):
        """
        Set the needle rotation angle to zero.
        :return:
        """
        if self.flag_error_check('needle_found'):
            return
        self.error_flags['zero_needle_rotation'] = True
        self.angle_deviation = self.needle_rotation_scale.get()
        self.calibration['needle']['angle_deviation'] = self.angle_deviation
        self.step_buttons['set_zero'].config(bg='green')

    def set_min_needle_rotation(self):
        """
        Set the min angle for needle rotation.
        :return: None
        """
        if self.flag_error_check('zero_needle_rotation'):
            return
        self.error_flags['min_found'] = True
        self.calibration['needle']['min_angle'] = self.needle_rotation_scale.get()
        self.step_buttons['set_min'].config(bg='green')

    def set_max_needle_rotation(self):
        """
        Set the max angle for needle rotation.
        :return: None
        """
        if self.flag_error_check('zero_needle_rotation'):
            return
        self.error_flags['max_found'] = True
        self.calibration['needle']['max_angle'] = self.needle_rotation_scale.get()
        self.step_buttons['set_max'].config(bg='green')

    def test_reading(self):
        """
        Use the parameters and needle location to get the reading.
        The following angles are from now on relative to the true center and not the calibration image's
        current value
        :return: None
        """
        if self.flag_error_check('needle_found'):
            return
        if self.flag_error_check('min_found'):
            return
        if self.flag_error_check('max_found'):
            return
        if self.flag_error_check('zero_needle_rotation'):
            return
        self.error_flags['reading_tested'] = True
        min_angle, max_angle = self.calibration['needle']['min_angle'], self.calibration['needle']['max_angle']
        self.angle_diff = abs(max_angle) + abs(min_angle)
        self.value_diff = abs(self.calibration['max_value']) + abs(self.calibration['min_value'])
        self.needle_rotation_scale.set(0)
        self.needle_rotation_scale.config(from_=min_angle, to=max_angle)
        self.value_step = self.value_diff / self.angle_diff
        self.step_buttons['test_reading'].config(bg='green')

    def re_config_reading(self):
        """
        In case that min/max was already set and the "Test Reading" button was pressed, in order to re-configure the
        limits this function is called
        :return: None
        """
        if self.flag_error_check('reading_tested'):
            return
        self.angle_deviation = 0
        self.needle_rotation_scale.set(0)
        self.error_flags['reading_tested'] = False
        self.needle_rotation_scale.config(from_=360, to=-360)
        for button in ['set_min', 'set_max', 'set_zero']:
            self.step_buttons[button].config(bg='red')
        for flag in ['min_found', 'max_found', 'zero_needle_rotation']:
            self.error_flags[flag] = False

    def get_current_reading(self):
        """
        Get the current reading from the needle rotation scale.
        :return: None
        """
        angle = self.needle_rotation_scale.get()
        min_angle = self.calibration['needle']['min_angle']
        if angle > 0:
            min_rel_angle = min_angle - angle
        else:
            min_rel_angle = min_angle + abs(angle)
        value = min_rel_angle * self.value_step
        self.current_reading = self.calibration['min_value'] + value

    def update_reading_button(self):
        """
        Update the reading label with the current reading.
        :return: None
        """
        self.get_current_reading()
        text = 'Value: {:.2f} {}'.format(self.current_reading, self.calibration['units'])
        self.buttons['current_value'].config(text=text)
        self.buttons['current_value'].pack(side=tk.LEFT)

    def set_calibration_parameters(self):
        """
        Set the calibration parameters, gathered in calibration frame. Specific for Analog gauge calibrator.
        :return:
        """
        self.calibration['center'] = (self.x, self.y)
        self.calibration['radius'] = self.r
        self.calibration['width'] = self.w
        self.calibration['height'] = self.h
        self.calibration['perspective'] = self.perspective.points

    def flag_error_check(self,
                         flag_name: str):
        """
        Check if flag value is True, else prompt warning and return False.
        :return: True if error, False if no error
        """
        if flag_name == 'cropped':
            message = 'Please crop the image first.'
        elif flag_name == 'perspective':
            message = 'Please set the perspective first.'
        elif flag_name == 'needle_found':
            message = "Please find the needle first and set gauge text parameters."
        elif flag_name == 'min_found':
            message = "Please set the minimum needle rotation angle."
        elif flag_name == 'zero_needle_rotation':
            message = "Please set the zero needle rotation angle."
        elif flag_name == 'reading_tested':
            message = "Please test the reading first."
        else:
            message = "Some error occurred."
        if not self.error_flags[flag_name]:
            final_message = message
            mb.showerror('Error', final_message)
            return True
        return False

    def save_calibration_data(self):
        """
        Save to XML the calibration data, write train and needle images
        :return:
        """
        cv2.imwrite(self.train_image_path, self.train_image)
        needle = self.rotate_needle(angle=0,
                                    show=False)
        cv2.imwrite(self.needle_image_path, needle)
        self.set_calibration_parameters()
        xmlr.dict_to_xml(self.calibration, self.xml_file, gauge=True)
        typer.secho('Saved parameters to {}'.format(self.xml_file), fg='green')


class DigitalCalibrator(Calibrator):
    def __init__(self,
                 calibration_image: str,
                 index: str,
                 camera_id: str = None):
        super().__init__(calibration_image=calibration_image,
                         index=index,
                         camera_id=camera_id)
