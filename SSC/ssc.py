"""
Simple Serial Console in Python & Tkinter.
"""

import re

import time
import datetime

import tkinter as tk
from tkinter import ttk

import queue

import threading

import serial
from serial.tools import list_ports


class ToolTip:
    """
    Displays tooltip for a given widget.

    Pieced together from stack overflov:

    https://stackoverflow.com/questions/3221956/how-do-i-display-tooltips-in-tkinter
    """

    def __init__(
            self,
            widget,
            text=None,
            delay=250,
            follow_pointer=True,
            background="#FFFFE0"):

        self.widget = widget
        self.text = text
        self.delay = delay
        # show tooltip next to pointer (true) or abowe the widget (false)
        self.follow_pointer = follow_pointer
        self.background = background

        self.tooltip = None
        self.event_id = None

        self.widget.bind('<Enter>', self.on_enter)
        self.widget.bind('<Leave>', self.on_leave)

    def on_enter(self, _event=None):
        """
        Wrapper for ENTER event
        """

        self.schedule()

    def on_leave(self, _event=None):
        """
        Wrapper for LEAVE event
        """

        self.unschedule()
        self.hide()

    def schedule(self):
        """
        Schedule tooltip event
        """

        self.unschedule()
        self.event_id = self.widget.after(self.delay, self.show)

    def unschedule(self):
        """
        Unschedule tooltip event
        """

        if self.event_id:
            self.widget.after_cancel(self.event_id)
            self.event_id = None

    def show(self):
        """
        Display and format the actuall toltip
        """

        self.tooltip = tk.Toplevel(self.widget)
        label = tk.Label(
            self.tooltip,
            text=self.text,
            justify=tk.CENTER,
            background=self.background)

        self.tooltip.overrideredirect(True)

        geo_x = 0
        geo_y = 0

        if self.follow_pointer:
            # if tooltip next to pointer calculate position out of widget
            geo_x = self.widget.winfo_pointerx() + 5
            geo_y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        else:
            # if tooltip above widget calculate position at the widget center
            geo_x = self.widget.winfo_rootx() + int((self.widget.winfo_width() / 2) -
                                                    (label.winfo_reqwidth() / 2))
            geo_y = self.widget.winfo_rooty() - self.widget.winfo_height() - 5

        self.tooltip.geometry(f'+{geo_x}+{geo_y}')

        label.pack()

    def hide(self):
        """
        Destroy the displayed tooltip
        """

        if self.tooltip:
            self.tooltip.destroy()


class SSC(tk.Frame):
    """
    Main program GUI and logic class.
    """

    # pylint: disable=too-many-ancestors
    # pylint: disable=too-many-instance-attributes

    def __init__(self, root):
        super().__init__(root)
        # self.pack()

        # initialize queue elements for threading purpuses
        self.queue_comm_in = queue.Queue()
        self.queue_comm_out = queue.Queue()

        # initialize element for serial communication
        self.serial_connection = serial.Serial()

        # initialize the main window
        root.title("SimpleSerialConsole")
        root.minsize(720, 480)
        root.geometry("720x480")

        # insert themed frame on root window for consistent appearance
        self.frame_root = ttk.Frame(root)
        self.frame_root.pack(fill=tk.BOTH, expand=True)

        # compose window GUI
        self.compose_gui()

        # init worker thread events
        self.thread_processing_event = threading.Event()
        self.thread_communication_event = threading.Event()
        # prepare thread for processing
        self.thread_processing = threading.Thread(
            target=self.worker_processing, args=(
                self.thread_processing_event,))
        # prepare object for creating communication threads on connect
        self.thread_communication = threading.Thread(target=None)

    # def __del__(self):
    #     pass

    def start_threads(self):
        """
        Program life cycle method - start threads
        """

        self.thread_processing.start()

    def stop_threads(self):
        """
        Program life cycle method - stop threads
        """

        # if communication thread is up
        if self.serial_connection.is_open:
            # connection is open, close it &
            self.thread_communication_event.set()
            self.thread_communication.join()

            self.serial_connection.close()

        # handle UI changes
        self.thread_processing_event.set()
        self.thread_processing.join()

    def worker_processing(self, thread_event):
        """
        Thread for processing and handling UI updates
        """

        ui_update = False
        msg_data, msg_time = None, None

        while not thread_event.is_set():
            try:
                msg_data, msg_time = self.queue_comm_in.get(timeout=0.1)

                ui_update = True
            except queue.Empty:
                ui_update = False

            if ui_update:
                # save scrollbar state to handle autoscroll
                scrollbar_state_y_previous = self.scrollbar_display_text.get()[
                    1]

                # handle timestamp display
                if self.check_receive_timestamp_varible.get():
                    self.text_display_content.insert(
                        tk.END, "[" + msg_time.strftime("%H:%M:%S.%f")[:-3] + "] ")

                # handle control character display
                if self.check_receive_ctrl_char_varible.get():
                    # get byte string, remove b'' tags,
                    # add new line for tkinter text
                    msg_data = str(msg_data)
                    msg_data = msg_data[2:-1]
                    msg_data = re.sub(
                        r"(\\n\\r|\\r\\n|\n|\r)", r"\1\n", msg_data)
                else:
                    # get ascii string without special characters, replace any
                    # new line combination with tkinter text newline
                    msg_data = str(msg_data, "ascii", errors='replace')
                    msg_data = re.sub(r"(\n\r|\r\n|\n|\r)", "\n", msg_data)

                # remove if more lines then desired hostory
                try:
                    tmp_hist_size = int(
                        self.entry_transmit_history_size_variable.get())
                    tmp_text_size = int(self.text_display_content.index(
                        'end-1c').split('.', maxsplit=1)[0])

                    if tmp_text_size > tmp_hist_size:
                        while tmp_text_size > tmp_hist_size:
                            # delete access lines
                            self.text_display_content.delete("1.0", "2.0")
                            tmp_text_size = int(self.text_display_content.index(
                                'end-1c').split('.', maxsplit=1)[0])
                except tk.TclError:
                    # not a valid history size - ignore
                    pass

                # add text to display
                self.text_display_content.insert(tk.END, msg_data)

                # handle scrool bar
                if scrollbar_state_y_previous == 1.0:
                    # only scroll text to botom if already showing bottom
                    self.text_display_content.see(tk.END)

    def worker_communication(self, thread_event, serial_reference):
        """
        Thread for handling serial communication
        """

        # pylint: disable=no-self-use

        while not thread_event.is_set():
            if serial_reference.in_waiting > 0:
                read = serial_reference.read(serial_reference.in_waiting)
                try:
                    self.queue_comm_in.put_nowait(
                        (read, datetime.datetime.now()))
                except queue.Full:
                    pass
            else:
                time.sleep(0.01)    # nothing to read, take a break

            try:
                msg = self.queue_comm_out.get_nowait()
                serial_reference.write(msg)
                # serial_reference.flush()
            except queue.Empty:
                pass

    def compose_gui(self):
        """
        Compose GUI elemnts of the application.
        """

        # compose frames for individual segments
        self.frame_control = ttk.Frame(self.frame_root)
        self.frame_display = ttk.Frame(self.frame_root)
        self.frame_receive = ttk.Frame(self.frame_root)
        self.frame_transmit = ttk.Frame(self.frame_root)
        self.frame_history = ttk.Frame(self.frame_root)

        # control - open/close, settings, ...
        self.button_control_connection = ttk.Button(
            self.frame_control, command=self.button_control_connection_handle,
            text="open")
        self.button_control_connection.pack(side=tk.LEFT)

        # port selection
        self.combo_control_port_variable = tk.StringVar()
        self.combo_control_port = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_port_variable,
            postcommand=self.combo_control_port_update,
            width=21)
        self.combo_control_port.bind(
            '<<ComboboxSelected>>',
            self.combo_control_port_bind_select)
        self.combo_control_port.pack(side=tk.LEFT)

        # baudrate selection
        self.combo_control_baudrate_variable = tk.StringVar()
        self.combo_control_baudrate = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_baudrate_variable,
            postcommand=self.combo_control_baudrate_update,
            width=9)
        self.combo_control_baudrate.bind(
            '<<ComboboxSelected>>',
            self.combo_control_baudrate_bind_select)
        self.combo_control_baudrate.pack(side=tk.LEFT)

        # bytesize selection
        self.combo_control_bytesize_variable = tk.StringVar()
        self.combo_control_bytesize = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_bytesize_variable,
            postcommand=self.combo_control_bytesize_update,
            width=3)
        self.combo_control_bytesize.bind(
            '<<ComboboxSelected>>',
            self.combo_control_bytesize_bind_select)
        self.combo_control_bytesize.pack(side=tk.LEFT)

        # parity selection
        self.combo_control_parity_variable = tk.StringVar()
        self.combo_control_parity = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_parity_variable,
            postcommand=self.combo_control_parity_update,
            width=7)
        self.combo_control_parity.bind(
            '<<ComboboxSelected>>',
            self.combo_control_parity_bind_select)
        self.combo_control_parity.pack(side=tk.LEFT)

        # stopbit selection
        self.combo_control_stopbit_variable = tk.StringVar()
        self.combo_control_stopbit = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_stopbit_variable,
            postcommand=self.combo_control_stopbit_update,
            width=3)
        self.combo_control_stopbit.bind(
            '<<ComboboxSelected>>',
            self.combo_control_stopbit_bind_select)
        self.combo_control_stopbit.pack(side=tk.LEFT)

        # flow selection
        self.combo_control_flow_variable = tk.StringVar()
        self.combo_control_flow = ttk.Combobox(
            self.frame_control,
            textvariable=self.combo_control_flow_variable,
            postcommand=self.combo_control_flow_update,
            width=21)
        self.combo_control_flow.bind(
            '<<ComboboxSelected>>',
            self.combo_control_flow_bind_select)
        self.combo_control_flow.pack(side=tk.LEFT)

        # display - display serial output ...
        self.text_display_content = tk.Text(self.frame_display, height=19)
        self.text_display_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar_display_text = ttk.Scrollbar(
            self.frame_display, command=self.text_display_content.yview)
        self.scrollbar_display_text.pack(side=tk.LEFT, fill=tk.Y)
        self.text_display_content['yscrollcommand'] = self.scrollbar_display_text.set

        # receive - receive control, formatting, ...
        self.button_receive_clear = ttk.Button(
            self.frame_receive, command=self.button_receive_clear_handle,
            text="clear")
        self.button_receive_clear.pack(side=tk.LEFT)

        self.check_receive_timestamp_varible = tk.BooleanVar()
        self.check_receive_timestamp = ttk.Checkbutton(
            self.frame_receive,
            variable=self.check_receive_timestamp_varible, text='timestamp')
        self.check_receive_timestamp.pack(side=tk.LEFT)

        self.check_receive_ctrl_char_varible = tk.BooleanVar()
        self.check_receive_ctrl_char = ttk.Checkbutton(
            self.frame_receive,
            variable=self.check_receive_ctrl_char_varible,
            text='byte string')
        self.check_receive_ctrl_char.pack(side=tk.LEFT)

        self.entry_transmit_history_size_variable = tk.IntVar()
        self.entry_transmit_history_size = ttk.Entry(
            self.frame_receive,
            validate="key",
            validatecommand=(
                self.frame_receive.register(
                    self.entry_transmit_history_size_validate),
                '%d',
                '%i',
                '%P',
                '%s',
                '%S',
                '%v',
                '%V',
                '%W'),
            textvariable=self.entry_transmit_history_size_variable)
        self.entry_transmit_history_size.pack(side=tk.LEFT)

        self.entry_receive_label_history = ttk.Label(
            self.frame_receive, text="history size")
        self.entry_receive_label_history.pack(side=tk.LEFT)

        # tansmit - transit control, data ...
        self.entry_transmit_data_variable = tk.StringVar()
        self.entry_transmit_data = ttk.Entry(
            self.frame_transmit,
            textvariable=self.entry_transmit_data_variable)
        self.entry_transmit_data.pack(side=tk.LEFT)

        option_transmit_ending_list = ('NONE', ' CR ', ' LF ', 'CRLF')
        self.option_transmit_ending_variable = tk.StringVar()
        self.option_transmit_ending = ttk.OptionMenu(
            self.frame_transmit,
            self.option_transmit_ending_variable,
            option_transmit_ending_list[0],
            *option_transmit_ending_list)
        self.option_transmit_ending.pack(side=tk.LEFT)

        self.button_transmit_data = ttk.Button(
            self.frame_transmit, command=self.transmit_data_handle,
            text="send")
        self.button_transmit_data.pack(side=tk.RIGHT)

        # history - show and use previous data in transmission
        self.listbox_history_variable = tk.StringVar()
        self.listbox_history = tk.Listbox(
            self.frame_history,
            listvariable=self.listbox_history_variable)
        self.listbox_history.bind(
            '<<ListboxSelect>>',
            self.listbox_history_bind_select)
        self.listbox_history.bind(
            '<Double-Button-1>',
            self.listbox_history_bind_double_button)
        self.listbox_history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # self.text_display_content.pack(side=tk.LEFT, fill=tk.BOTH,
        # expand=True)

        self.scrollbar_history_text = ttk.Scrollbar(
            self.frame_history, command=self.listbox_history.yview)
        self.scrollbar_history_text.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox_history['yscrollcommand'] = self.scrollbar_history_text.set

        # assemble frames into main window
        self.frame_control.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.frame_display.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.frame_receive.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.frame_transmit.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.frame_history.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # populate menus
        self.combo_control_port_update()
        self.combo_control_baudrate_update()
        self.combo_control_bytesize_update()
        self.combo_control_parity_update()
        self.combo_control_stopbit_update()
        self.combo_control_flow_update()

        self.entry_transmit_history_size_update()

        # set states
        self.button_transmit_data['state'] = 'disable'

        # add tooltips
        ToolTip(
            self.combo_control_port,
            text="DEVICE PORT",
            follow_pointer=False)
        ToolTip(
            self.combo_control_baudrate,
            text="BAUDRATE",
            follow_pointer=False)
        ToolTip(
            self.combo_control_bytesize,
            text="BYTE SIZE",
            follow_pointer=False)
        ToolTip(self.combo_control_parity, text="PARITY", follow_pointer=False)
        ToolTip(
            self.combo_control_stopbit,
            text="STOP BITS",
            follow_pointer=False)
        ToolTip(
            self.combo_control_flow,
            text="FLOW CONTROL",
            follow_pointer=False)

    def button_control_connection_handle(self):
        """
        Handle connect/disconnect button
        """

        # button is dependant on serial connection state

        # change connection/program state
        if self.serial_connection.is_open:
            # connection is open, close it & handle UI changes
            self.thread_communication_event.set()
            self.thread_communication.join()

            self.serial_connection.close()
        else:
            # connection is closed, open it & handle UI changes
            self.serial_connection.port = self.combo_control_port_variable.get()

            self.serial_connection.baudrate = self.combo_control_baudrate_variable.get()

            if self.combo_control_bytesize_variable.get() == "5":
                self.serial_connection.bytesize = serial.FIVEBITS
            elif self.combo_control_bytesize_variable.get() == "6":
                self.serial_connection.bytesize = serial.SIXBITS
            elif self.combo_control_bytesize_variable.get() == "7":
                self.serial_connection.bytesize = serial.SEVENBITS
            else:
                self.serial_connection.bytesize = serial.EIGHTBITS

            if self.combo_control_parity_variable.get() == "SPACE":
                self.serial_connection.parity = serial.PARITY_SPACE
            elif self.combo_control_parity_variable.get() == "MARK":
                self.serial_connection.parity = serial.PARITY_MARK
            elif self.combo_control_parity_variable.get() == "ODD":
                self.serial_connection.parity = serial.PARITY_ODD
            elif self.combo_control_parity_variable.get() == "EVEN":
                self.serial_connection.parity = serial.PARITY_EVEN
            else:
                self.serial_connection.parity = serial.PARITY_NONE

            if self.combo_control_stopbit_variable.get() == "2":
                self.serial_connection.stopbit = serial.STOPBITS_TWO
            else:
                self.serial_connection.stopbit = serial.STOPBITS_ONE

            if self.combo_control_flow_variable.get() == "SOFTWARE (XON / XOFF)":
                self.serial_connection.xonxoff = True
                self.serial_connection.rtscts = False
                self.serial_connection.dsrdtr = False
            elif self.combo_control_flow_variable.get() == "HARDWARE (RTS / CTS)":
                self.serial_connection.xonxoff = False
                self.serial_connection.rtscts = True
                self.serial_connection.dsrdtr = False
            elif self.combo_control_flow_variable.get() == "HARDWARE (DSR / DTR)":
                self.serial_connection.xonxoff = False
                self.serial_connection.rtscts = False
                self.serial_connection.dsrdtr = True
            else:
                self.serial_connection.xonxoff = False
                self.serial_connection.rtscts = False
                self.serial_connection.dsrdtr = False

            try:
                self.serial_connection.open()

                self.thread_communication_event.clear()
                self.thread_communication = threading.Thread(
                    target=self.worker_communication, args=(
                        self.thread_communication_event, self.serial_connection,))
                self.thread_communication.start()

            except serial.SerialException as exception_error:
                # catch serial comminucation exceptions
                # TODO - print error in GUI
                print(exception_error)
            except Exception:
                # catch the rest of (thread) exceptions
                if self.serial_connection.is_open:
                    # clese serial connection if anything else goes wrong
                    self.serial_connection.close()

        # change GUI to match changed state
        if self.serial_connection.is_open:
            # connection is open

            self.button_control_connection['text'] = "close"

            self.button_transmit_data['state'] = 'normal'

            self.combo_control_port['state'] = 'disable'
            self.combo_control_baudrate['state'] = 'disable'
            self.combo_control_bytesize['state'] = 'disable'
            self.combo_control_parity['state'] = 'disable'
            self.combo_control_stopbit['state'] = 'disable'
            self.combo_control_flow['state'] = 'disable'

            self.entry_transmit_data.bind(
                '<Return>', self.transmit_data_handle)

            self.entry_transmit_data.focus()
        else:
            # connection is closed

            self.button_control_connection['text'] = "open"

            self.button_transmit_data['state'] = 'disable'

            self.combo_control_port['state'] = 'readonly'
            self.combo_control_baudrate['state'] = 'readonly'
            self.combo_control_bytesize['state'] = 'readonly'
            self.combo_control_parity['state'] = 'readonly'
            self.combo_control_stopbit['state'] = 'readonly'
            self.combo_control_flow['state'] = 'readonly'

            self.entry_transmit_data.unbind('<Return>')

    def combo_control_port_update(self):
        """
        Detect vailable serial ports and list them in the menu.
        """

        prev_selection = self.combo_control_port_variable.get()

        # find available serial ports
        comport_list = []
        for port in list_ports.comports():
            comport_list.append(port.device)
        comport_list.append("CUSTOM")

        self.combo_control_port['values'] = comport_list

        if prev_selection not in comport_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            if len(comport_list) > 1:
                # select last detected port before CUSTOM selction
                self.combo_control_port.current(len(comport_list) - 2)
                self.combo_control_port['state'] = 'readonly'
            else:
                # no ports found, select CUSTOM selection and set editable
                self.combo_control_port.current(len(comport_list) - 1)
                self.combo_control_port['state'] = 'normal'

    def combo_control_port_bind_select(self, _event=None):
        """
        Handle selection of port from combobox.
        """

        prev_selection = self.combo_control_port_variable.get()
        comport_list = self.combo_control_port['values']

        # toggle widget state - disable editing for non CUSTOM selections
        if comport_list.index(prev_selection) == len(comport_list) - 1:
            self.combo_control_port['state'] = 'normal'
        else:
            self.combo_control_port['state'] = 'readonly'
            self.combo_control_port.selection_clear()

    def combo_control_baudrate_update(self):
        """
        Handle baudrate menu
        """

        prev_selection = self.combo_control_baudrate_variable.get()

        # find available serial ports
        baudrate_list = []
        baudrate_list.append("1200")
        baudrate_list.append("4800")
        baudrate_list.append("9600")
        baudrate_list.append("19200")
        baudrate_list.append("38400")
        baudrate_list.append("57600")
        baudrate_list.append("115200")
        baudrate_list.append("CUSTOM")

        self.combo_control_baudrate['values'] = baudrate_list

        if prev_selection not in baudrate_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            if len(baudrate_list) > 1:
                # select last default baudrate
                self.combo_control_baudrate.current(len(baudrate_list) - 6)
                self.combo_control_baudrate['state'] = 'readonly'
            else:
                # no baudrate found, select CUSTOM selection and set editable
                self.combo_control_baudrate.current(len(baudrate_list) - 1)
                self.combo_control_baudrate['state'] = 'normal'

    def combo_control_baudrate_bind_select(self, _event=None):
        """
        Handle selection of baudrate from combobox.
        """

        prev_selection = self.combo_control_baudrate_variable.get()
        comport_list = self.combo_control_baudrate['values']

        # toggle widget state - disable editing for non CUSTOM selections
        if comport_list.index(prev_selection) == len(comport_list) - 1:
            self.combo_control_baudrate['state'] = 'normal'
        else:
            self.combo_control_baudrate['state'] = 'readonly'
            self.combo_control_baudrate.selection_clear()

    def combo_control_bytesize_update(self):
        """
        Handle bytesize menu
        """

        prev_selection = self.combo_control_bytesize_variable.get()

        # find available serial ports
        bytesize_list = []
        bytesize_list.append("5")
        bytesize_list.append("6")
        bytesize_list.append("7")
        bytesize_list.append("8")

        self.combo_control_bytesize['values'] = bytesize_list

        if prev_selection not in bytesize_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            self.combo_control_bytesize.current(len(bytesize_list) - 1)
            self.combo_control_bytesize['state'] = 'readonly'

    def combo_control_bytesize_bind_select(self, _event=None):
        """
        Handle selection of port from combobox.
        """

        self.combo_control_bytesize.selection_clear()

    def combo_control_parity_update(self):
        """
        Handle parity menu
        """

        prev_selection = self.combo_control_parity_variable.get()

        # find available serial ports
        parity_list = []
        parity_list.append("NONE")
        parity_list.append("EVEN")
        parity_list.append("ODD")
        parity_list.append("MARK")
        parity_list.append("SPACE")

        self.combo_control_parity['values'] = parity_list

        if prev_selection not in parity_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            self.combo_control_parity.current(0)
            self.combo_control_parity['state'] = 'readonly'

    def combo_control_parity_bind_select(self, _event=None):
        """
        Handle selection of parity from combobox.
        """

        self.combo_control_parity.selection_clear()

    def combo_control_stopbit_update(self):
        """
        Handle stopbit menu
        """

        prev_selection = self.combo_control_stopbit_variable.get()

        # find available serial ports
        stopbit_list = []
        stopbit_list.append("1")
        stopbit_list.append("2")

        self.combo_control_stopbit['values'] = stopbit_list

        if prev_selection not in stopbit_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            self.combo_control_stopbit.current(0)
            self.combo_control_stopbit['state'] = 'readonly'

    def combo_control_stopbit_bind_select(self, _event=None):
        """
        Handle selection of stopbit from combobox.
        """

        self.combo_control_stopbit.selection_clear()

    def combo_control_flow_update(self):
        """
        Handle flow menu
        """

        prev_selection = self.combo_control_flow_variable.get()

        # find available serial ports
        flow_list = []
        flow_list.append("NONE")
        flow_list.append("SOFTWARE (XON / XOFF)")
        flow_list.append("HARDWARE (RTS / CTS)")
        flow_list.append("HARDWARE (DSR / DTR)")

        self.combo_control_flow['values'] = flow_list

        if prev_selection not in flow_list:
            prev_selection = ""

        if not prev_selection:
            # no previous selection
            self.combo_control_flow.current(0)
            self.combo_control_flow['state'] = 'readonly'

    def button_receive_clear_handle(self):
        self.text_display_content.delete("1.0", tk.END)

    def entry_transmit_history_size_update(self):
        """
        Handle history size value
        """

        self.entry_transmit_history_size_variable.set(1024)

    def entry_transmit_history_size_validate(
            self,
            _action,
            _index,
            _value_if_allowed,
            _prior_value,
            _text,
            _validation_type,
            _trigger_type,
            _widget_name):
        """
        Handle history size value validation
        """

        if _value_if_allowed:
            # if entry value is not empty
            try:
                int(_value_if_allowed)
                return True
            except ValueError:
                return False
        else:
            # if entry is empty only
            if _value_if_allowed == "":
                return True
            else:
                return False

    def combo_control_flow_bind_select(self, _event=None):
        """
        Handle selection of flow from combobox.
        """

        self.combo_control_flow.selection_clear()

    def transmit_data_handle(self, _event=None):
        """
        Handle send event
        """

        input_data = self.entry_transmit_data_variable.get()
        input_ending = self.option_transmit_ending_variable.get()

        transmit_data = input_data.encode()

        if input_ending == " LF ":
            transmit_data = transmit_data + str.encode("\n")
        elif input_ending == " CR ":
            transmit_data = transmit_data + str.encode("\r")
        elif input_ending == "CRLF":
            transmit_data = transmit_data + str.encode("\r\n")
        else:
            pass

        if len(transmit_data) > 0:
            self.queue_comm_out.put(transmit_data)

        if len(input_data) > 0:
            # if value already in history, remove from list
            lb_hist_tuple = self.listbox_history.get(0, tk.END)
            if input_data in lb_hist_tuple:
                self.listbox_history.delete(lb_hist_tuple.index(input_data))

            # add value to top of the list
            self.listbox_history.insert(0, input_data)

        # clear input field and set focus on input field
        self.entry_transmit_data.delete(0, tk.END)
        self.entry_transmit_data.focus()

    def listbox_history_bind_select(self, _event=None):
        """
        Handle single click on history list box
        """

        self.entry_transmit_data.delete(0, tk.END)
        self.entry_transmit_data.insert(
            0, self.listbox_history.get(
                self.listbox_history.curselection()))

        # set focus on input field after
        self.entry_transmit_data.focus()

    def listbox_history_bind_double_button(self, _event=None):
        """
        Handle double click on history list box
        """

        self.transmit_data_handle()


def main():
    """
    Run as a program.
    """

    root = tk.Tk()

    myapp = SSC(root)

    myapp.start_threads()   # start UI independant processing background thread
    myapp.mainloop()
    myapp.stop_threads()    # stop UI independant processing background thread


if __name__ == '__main__':
    main()
