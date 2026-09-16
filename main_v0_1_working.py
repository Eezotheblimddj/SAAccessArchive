import wx

APP_TITLE = "SA Access Archive - by Raeez Kuhn, Eezo the Blind DJ"


class MainWindow(wx.Frame):

    def __init__(self):
        super().__init__(parent=None, title=APP_TITLE, size=(900, 600))

        self.build_menu_bar()
        self.build_body()

        self.Centre()
        self.Show()

        # Give the window a moment to fully draw, then push focus
        # onto the list. This is what makes NVDA read the items.
        self.focus_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_focus_timer, self.focus_timer)
        self.focus_timer.Start(200, oneShot=True)

    def on_focus_timer(self, event):
        self.list_box.SetFocus()
        self.list_box.SetSelection(0)

    def build_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        file_menu.Append(4001, "Refresh\tF5")
        file_menu.AppendSeparator()
        file_menu.Append(4002, "Quit\tCtrl+Q")
        menu_bar.Append(file_menu, "File")

        nav_menu = wx.Menu()
        nav_menu.Append(3001, "Up One Level\tBackspace")
        nav_menu.Append(3002, "Home\tHome")
        nav_menu.Append(3003, "End\tEnd")
        nav_menu.AppendSeparator()
        nav_menu.Append(3004, "Search\tCtrl+F")
        menu_bar.Append(nav_menu, "Navigate")

        settings_menu = wx.Menu()
        settings_menu.Append(5001, "Server Settings")
        settings_menu.Append(5002, "Download Folder")
        settings_menu.Append(5003, "Sounds On or Off")
        settings_menu.Append(5004, "Speech Verbosity")
        menu_bar.Append(settings_menu, "Settings")

        help_menu = wx.Menu()
        help_menu.Append(6001, "Keyboard Shortcuts\tF1")
        menu_bar.Append(help_menu, "Help")

        about_menu = wx.Menu()
        about_menu.Append(7001, "About SA Access Archive")
        menu_bar.Append(about_menu, "About")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self.on_placeholder, id=4001)
        self.Bind(wx.EVT_MENU, self.on_quit, id=4002)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=3001)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=3002)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=3003)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=3004)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=5001)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=5002)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=5003)
        self.Bind(wx.EVT_MENU, self.on_placeholder, id=5004)
        self.Bind(wx.EVT_MENU, self.on_help, id=6001)
        self.Bind(wx.EVT_MENU, self.on_about, id=7001)

    def build_body(self):
        panel = wx.Panel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_box = wx.ListBox(panel, style=wx.LB_SINGLE)

        self.list_box.Append("Welcome to SA Access Archive")
        self.list_box.Append("By Raeez Kuhn, Eezo the Blind DJ")
        self.list_box.Append("Version 0.1 - Interface test")
        self.list_box.Append("Press Escape to close")

        sizer.Add(self.list_box, 1, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(sizer)

        self.panel = panel
        self.list_box.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def on_quit(self, event):
        self.Close()

    def on_placeholder(self, event):
        wx.MessageBox(
            "This feature will be added in a later build.",
            "Not yet available",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_help(self, event):
        wx.MessageBox(
            "Keyboard shortcuts:\n\n"
            "Up and Down - move through the list\n"
            "Escape - close the application\n"
            "F5 - refresh\n"
            "Ctrl+Q - quit\n"
            "F1 - this help screen",
            "Keyboard Shortcuts",
            wx.OK | wx.ICON_INFORMATION,
            self
        )

    def on_about(self, event):
        wx.MessageBox(
            "SA Access Archive\n"
            "Version 0.1\n\n"
            "Developed by Raeez Kuhn, Eezo the Blind DJ\n"
            "Based in South Africa\n\n"
            "A South African accessible archive for blind and\n"
            "visually impaired users.",
            "About SA Access Archive",
            wx.OK | wx.ICON_INFORMATION,
            self
        )


def main():
    app = wx.App(False)
    MainWindow()
    app.MainLoop()


if __name__ == "__main__":
    main()