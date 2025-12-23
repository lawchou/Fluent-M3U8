# coding:utf-8
from pathlib import Path
from typing import List
from PySide6.QtCore import Qt, QFileInfo
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets import ScrollArea, InfoBar, InfoBarPosition, PushButton

from ..components.info_card import M3U8DLInfoCard
from ..components.config_card import AdvanceConfigCard, ProxyConfigCard, LiveConfigCard, DecryptionConfigCard, MuxConfigCard
from ..components.add_download_dialog import AddDownloadDialog

from ..service.m3u8dl_service import m3u8Service
from ..common.config import cfg
from ..common.signal_bus import signalBus


class HomeInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget(self)
        self.loadProgressInfoBar = None
        self.installProgressInfoBar = None

        self.m3u8dlInfoCard = M3U8DLInfoCard()
        self.muxSettingCard = MuxConfigCard()
        self.advanceSettingCard = AdvanceConfigCard()
        self.proxySettingCard = ProxyConfigCard()
        self.liveSettingCard = LiveConfigCard()
        self.decryptionCard = DecryptionConfigCard()

        self.vBoxLayout = QVBoxLayout(self.view)

        self._initWidget()

    def _initWidget(self):
        self.setWidget(self.view)
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.setContentsMargins(0, 0, 10, 10)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(
            self.m3u8dlInfoCard, 0, Qt.AlignmentFlag.AlignTop)
        # basic setting removed from home interface; use task page dialog instead
        self.vBoxLayout.addWidget(
            self.liveSettingCard, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(
            self.decryptionCard, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(
            self.muxSettingCard, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(
            self.proxySettingCard, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(
            self.advanceSettingCard, 0, Qt.AlignmentFlag.AlignTop)

        self.resize(780, 800)
        self.setObjectName("packageInterface")
        self.enableTransparentBackground()

        self._connectSignalToSlot()

    def dragEnterEvent(self, e):
        if not e.mimeData().hasUrls():
            return e.ignore()

        e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        if not e.mimeData().urls():
            return

        fileInfo = QFileInfo(e.mimeData().urls()[0].toLocalFile())
        path = fileInfo.absoluteFilePath()

        if fileInfo.isFile() and path.lower().endswith('.txt'):
            # open AddDownloadDialog on home when user drops a txt file
            try:
                dialog = AddDownloadDialog(self.window())
                dialog.setDownloadLink(path)
                dialog.exec()
            except Exception:
                # fallback: try to set as text to any existing handler
                pass

    def _connectSignalToSlot(self):
        # Home no longer has download button; nothing to connect here
        pass
