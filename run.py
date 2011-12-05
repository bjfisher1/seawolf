
import resource
import pty
import select
import os
import signal

import wx

class AppRunnerFrame(wx.Frame):

    def __init__(self, parent, id, title, size):
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, size)

        self.app_panels = []
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.sizer = wx.GridSizer(1,1,0,0)
        self.SetSizer(self.sizer)

        self.main_split = wx.SplitterWindow(self, -1)
        self.main_split.SetMinimumPaneSize(120)

        self.panel_left = wx.Panel(self.main_split, -1)
        self.panel_left_sizer = wx.GridSizer(1,1,0,0)
        self.panel_left.SetSizer(self.panel_left_sizer)

        self.panel_right = wx.Panel(self.main_split, -1)
        self.panel_right_sizer = wx.GridSizer(1,1,0,0)
        self.panel_right.SetSizer(self.panel_right_sizer)

        self.current_app_panel = None
        self.app_tree = wx.TreeCtrl(self.panel_left, -1, wx.DefaultPosition, (-1,-1), wx.TR_FULL_ROW_HIGHLIGHT|wx.TR_HAS_BUTTONS|wx.TR_HIDE_ROOT)
        self.read_apps()
        self.app_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_app_select, id=self.app_tree.GetId())
        self.app_tree.SetFocus()
        self.app_tree.SelectItem(self.app_tree.GetFirstVisibleItem())
        self.panel_left_sizer.Add(self.app_tree, 1, wx.EXPAND)

        self.main_split.SplitVertically(self.panel_left, self.panel_right, 250)
        self.sizer.Add(self.main_split, 1, wx.EXPAND)

        # Timer to update stdout display of the current app
        self.timer = wx.PyTimer(lambda: self.update())
        self.timer.Start(200)

    def update(self):
        for app in self.app_panels:
            app.update()

    def read_apps(self):
        '''Populates the application tree.'''
        applications = {
            "Misc": {
                "Hub": AppPanel(self.panel_right, ["seawolf-hub","-c","../conf/hub.conf"], "db/"),
                "Serial App": AppPanel(self.panel_right, ["./bin/serialapp"], "serial/"),
                "Simulator": AppPanel(self.panel_right, ["python","run.py"], "simulator/"),
                "SVR Watch": AppPanel(self.panel_right, ["python","svr_watch_all.py"], "misc/"),
                "SVR": AppPanel(self.panel_right, ["svrd"], ""),
            },
            "PID": {
                "Yaw PID": AppPanel(self.panel_right, ["./bin/yawpid"], "applications/"),
                "Depth PID": AppPanel(self.panel_right, ["./bin/depthpid"], "applications/"),
                "Pitch PID": AppPanel(self.panel_right, ["./bin/pitchpid"], "applications/"),
                "Mixer": AppPanel(self.panel_right, ["./bin/mixer"], "applications/"),
            },
            "Control": {
                "Joystick Controller": AppPanel(self.panel_right, ["./bin/joystick_controller"], "applications/"),
                "Steering Wheel Controller": AppPanel(self.panel_right, ["./bin/steering_controller"], "applications/"),
                "Zero Thrusters": AppPanel(self.panel_right, ["./bin/zerothrusters"], "applications/"),
            }
        }
        tree_root = self.app_tree.AddRoot("Applications")
        for group_name, app_dict in applications.iteritems():
            group_root = self.app_tree.AppendItem(tree_root, group_name)
            for app_name, panel in app_dict.iteritems():

                # Add the app
                app_item = self.app_tree.AppendItem(group_root, app_name)
                self.app_tree.SetPyData(app_item, panel)
                self.app_tree.Bind(wx.EVT_TREE_ITEM_MIDDLE_CLICK, self.on_app_middle_click)
                self.app_tree.Bind(wx.EVT_TREE_KEY_DOWN, self.on_app_key_press)
                panel.Show(False)
                panel.register(self.app_tree, app_item)
                self.app_panels.append(panel)

            self.app_tree.ExpandAll()

    def on_app_key_press(self, event):
        key_event = event.GetKeyEvent()
        key = key_event.GetKeyCode()
        if key == wx.WXK_NUMPAD_ENTER or key == wx.WXK_RETURN:
            selected_app = self.app_tree.GetSelection()
            app_panel = self.app_tree.GetPyData(selected_app)
            if app_panel:
                app_panel.on_run_toggle(None)
        else:
            event.Skip()

    def on_app_middle_click(self, event):
        app_panel = self.app_tree.GetPyData(event.GetItem())
        app_panel.on_run_toggle(None)

    def on_app_select(self, event):
        '''Called when an app is selected from the app tree.'''
        app_panel = self.app_tree.GetPyData(event.GetItem())
        self.display_app(app_panel)

    def display_app(self, app_panel):
        '''Displays the given panel in the right frame.'''
        if self.current_app_panel:
            self.current_app_panel.Show(False)
        self.panel_right_sizer.Clear(False)
        if app_panel:
            self.panel_right_sizer.Add(app_panel, 1, wx.EXPAND)
            app_panel.Show(True)
            app_panel.Layout()
        self.panel_right_sizer.Layout()
        self.current_app_panel = app_panel

    def on_close(self, event):
        for app in self.app_panels:
            app.stop()
        self.Destroy()

class AppPanel(wx.Panel):
    '''A self contained panel that represents a subprocess.

    :param parent_window:
    :param command:
    :param directory:
    :param default_args: TODO
    :param help_text: TODO
    :param single: TODO

    '''

    def __init__(self, parent_window, command, directory="", default_args="",
                 help_text=""):
        '''Initialize the panel and its children in this hierarchy:

        AppPanel
          |
          +- horizontal_box
              |
              +- vertical_box
                   |
                   +- control_box
                   |    |
                   |    +- run_button
                   |    |
                   |    +- argument_box
                   |    |
                   |    +- [other controls]
                   |
                   +- output_box

        '''
        wx.Panel.__init__(self, parent_window, -1)

        self.command = command
        self.pid = None
        self.stdout = None

        head, tail = os.path.split(__file__)
        self.directory = os.path.abspath(os.path.join(head, directory))

        # control_box
        # Contains run_button and any other controls
        self.control_box = wx.BoxSizer(wx.HORIZONTAL)
        self.run_button = wx.ToggleButton(self, -1, "Run")
        self.run_button.Bind(wx.EVT_TOGGLEBUTTON, self.on_run_toggle)
        self.control_box.Add(self.run_button, 0, wx.ALIGN_LEFT)

        # output_box to display app's stdout
        self.output_box = wx.TextCtrl(self, -1, '', style=
                wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH |
                wx.TE_NOHIDESEL | wx.TE_LEFT)
        self.output_box.SetDefaultStyle(
                wx.TextAttr("black", "white", wx.Font(8, wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL), False)
        )
        self.output_box.Fit()

        self.vertical_box = wx.BoxSizer(wx.VERTICAL)
        self.horizontal_box = wx.BoxSizer(wx.HORIZONTAL)
        self.horizontal_box.Add(self.vertical_box, 1, wx.EXPAND)
        self.SetSizer(self.horizontal_box)

        self.vertical_box.Add(self.output_box, 1, wx.EXPAND)
        self.vertical_box.Add(self.control_box, 0, wx.SHRINK)

    def register(self, app_tree, tree_item):
        self.app_tree = app_tree
        self.tree_item = tree_item

    def on_run_toggle(self, event):
        if self.pid is None:
            self.run()
        else:
            self.stop()

    def run(self):

        # Start Process
        self.pid, self.stdout = pty.fork()

        if self.pid == 0:  # Child

            # Close open file descriptors
            # This tidbit taken from pexpect
            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            for i in xrange(3, max_fd):
                try:
                    os.close(i)
                except OSError:
                    pass

            os.chdir(self.directory)
            os.execvp(self.command[0], self.command)
            raise OSError("os.exec failed!")

        self.app_tree.SetItemBold(self.tree_item, True)
        self.output_box.SetValue("")
        self.run_button.SetLabel("Stop")

    def stop(self):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGINT)
            except OSError:  # Process doesn't exist
                pass

    def update(self):

        if self.pid:

            # Get stdout
            text = None
            if select.select([self.stdout], [], [], 0)[0]:
                try:
                    text = os.read(self.stdout, 65535)

                except OSError:
                    # Process exited
                    self.pid = None
                    self.stdout = None
                    self.app_tree.SetItemBold(self.tree_item, False)
                    self.run_button.SetValue(False)
                    self.run_button.SetLabel("Run")

                if text:
                    self.output_box.AppendText(text)

if __name__ == "__main__":
    app = wx.App(0)
    frame = AppRunnerFrame(None, -1, "Application Runner", size=wx.Size(800, 400))
    frame.Show(True)
    app.SetTopWindow(frame)
    app.MainLoop()
