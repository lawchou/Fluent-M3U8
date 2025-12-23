# coding:utf-8
from typing import Dict, List
from PySide6.QtCore import Qt, Signal, Property, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QStackedWidget, QVBoxLayout, QGraphicsDropShadowEffect, QHBoxLayout

from qfluentwidgets import (Action, FluentIcon, SegmentedWidget, InfoBar, InfoBarPosition,
                            PushButton, Flyout, CommandBarView, isDarkTheme)

from ..common.icon import Logo, Icon
from ..common.database import sqlRequest
from ..common.database.entity import TaskStatus
from ..common.signal_bus import signalBus
from ..service.download_task_service import downloadTaskService
from ..service.speed_service import speedService
from ..service.m3u8dl_service import m3u8Service, VODDownloadProgressInfo, LiveDownloadProgressInfo
from ..components.interface import Interface
from ..components.task_card import (VODDownloadingTaskCard, Task, SuccessTaskCard, TaskCardBase, FailedTaskCard,
                                    LiveDownloadingTaskCard, DeleteTaskDialog)
from ..components.empty_status_widget import EmptyStatusWidget
from ..common.speed_badge import SpeedBadge
from ..components.add_download_dialog import AddDownloadDialog


class TaskInterface(Interface):
    """ Task Interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setTitle(self.tr("Task"))

        self.pivot = SegmentedWidget()
        self.stackedWidget = TaskStackedWidget()
        self.downloadingTaskView = DownloadingTaskView(self)
        self.successTaskView = SuccessTaskView(self)
        self.failedTaskView = FailedTaskView(self)
        self.emptyStatusWidget = EmptyStatusWidget(Logo.SMILEFACE, self.tr("Currently no download tasks"), self)
        self.speedBadge = SpeedBadge(self)

        # button to open AddDownloadDialog
        self.addDownloadButton = PushButton(self.tr("新增下载任务"), self)
        self.addDownloadButton.setToolTip(self.tr("Add a new download task"))
        self.addDownloadButton.clicked.connect(self._onAddDownloadButtonClicked)

        self._initWidgets()

    def _initWidgets(self):
        self.setViewportMargins(0, 140, 0, 10)
        self.pivot.addItem("downloading", self.tr("Downloading"), icon=FluentIcon.SYNC)
        self.pivot.addItem("finished", self.tr("Finished"), icon=FluentIcon.COMPLETED)
        self.pivot.addItem("failed", self.tr("Failed"), icon=FluentIcon.INFO)
        self.pivot.setCurrentItem("downloading")

        self.emptyStatusWidget.setMinimumWidth(200)

        self.stackedWidget.addWidget(self.downloadingTaskView)
        self.stackedWidget.addWidget(self.successTaskView)
        self.stackedWidget.addWidget(self.failedTaskView)

        self._initLayout()
        self._connectSignalToSlot()

    def _initLayout(self):
        # place pivot and add button on same row
        topHBox = QHBoxLayout()
        topHBox.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        topHBox.addStretch(1)
        topHBox.addWidget(self.addDownloadButton, 0, Qt.AlignmentFlag.AlignRight)

        self.vBoxLayout.addLayout(topHBox)
        self.viewLayout.addWidget(self.stackedWidget)

    def _onAddDownloadButtonClicked(self):
        dialog = AddDownloadDialog(self.window())
        dialog.exec()

    def _onTaskCreated(self, task: Task):
        self.downloadingTaskView.addTask(task)
        if self.stackedWidget.currentIndex() == 0:
            self.emptyStatusWidget.hide()

    def _onDownloadFinished(self, task: Task, isSuccess, errorMsg):
        self.downloadingTaskView.removeTask(task)

        if isSuccess:
            self.successTaskView.addTask(task)
        else:
            self.failedTaskView.addTask(task)

        self._updateEmptyStatus()

    def _onDownloadProgressChanged(self, task: Task, info):
        card = self.downloadingTaskView.findCard(task)
        if card:
            card.setInfo(info)

        speedService.update(task, info.speed)
        self.speedBadge.setSpeed(speedService.totalSpeed())

    def _onCoverSaved(self, task: Task):
        card = self.successTaskView.findCard(task)
        if card:
            card.updateCover()

    def _onCurrentWidgetChanged(self):
        for i in range(self.stackedWidget.count()):
            self.stackedWidget.widget(i).setSelectionMode(False)

        view = self.stackedWidget.currentWidget()   # type: TaskCardView
        self.pivot.setCurrentItem(view.objectName())
        self.emptyStatusWidget.setVisible(view.count() == 0)

    def _connectSignalToSlot(self):
        self.pivot.currentItemChanged.connect(
            lambda k: self.stackedWidget.setCurrentWidget(self.findChild(QWidget, k)))
        self.stackedWidget.currentChanged.connect(self._onCurrentWidgetChanged)
        self.downloadingTaskView.cardCountChanged.connect(self._updateEmptyStatus)
        self.successTaskView.cardCountChanged.connect(self._updateEmptyStatus)
        self.failedTaskView.cardCountChanged.connect(self._updateEmptyStatus)

        signalBus.redownloadTask.connect(self._redownload)

        m3u8Service.downloadCreated.connect(self._onTaskCreated)
        m3u8Service.downloadProgressChanged[Task, VODDownloadProgressInfo].connect(self._onDownloadProgressChanged)
        m3u8Service.downloadProgressChanged[Task, LiveDownloadProgressInfo].connect(self._onDownloadProgressChanged)
        m3u8Service.downloadFinished.connect(self._onDownloadFinished)
        m3u8Service.coverSaved.connect(self._onCoverSaved)

    def _updateEmptyStatus(self):
        visible = self.stackedWidget.currentWidget().count() == 0
        self.emptyStatusWidget.setVisible(visible)

        if self.downloadingTaskView.count() == 0:
            self.speedBadge.hide()

    def _redownload(self, task: Task):
        if not m3u8Service.isAvailable():
            InfoBar.error(
                self.tr("Task failed"),
                self.tr("Please choose N_m3u8DL-RE binary file in setting interface"),
                duration=-1,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            return

        success = downloadTaskService.redownload(task)
        button = PushButton(self.tr('Check'))

        if success:
            w = InfoBar.success(
                self.tr("Task created"),
                self.tr("Please check the download task"),
                duration=3000,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            button.clicked.connect(signalBus.switchToTaskInterfaceSig)
        else:
            w = InfoBar.error(
                self.tr("Task failed"),
                self.tr("Please check the error log"),
                duration=-1,
                position=InfoBarPosition.BOTTOM,
                parent=self
            )
            button.clicked.connect(m3u8Service.showDownloadLog)

        w.widgetLayout.insertSpacing(0, 10)
        w.addWidget(button)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.emptyStatusWidget.adjustSize()
        w, h = self.emptyStatusWidget.width(), self.emptyStatusWidget.height()
        y = self.height() // 2 - h //2
        self.emptyStatusWidget.move(int(self.width()/2 - w/2), y)


class TaskCardView(QWidget):
    """ Download task view """

    cardCountChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.cards = []     # type: List[TaskCardBase]
        self.selectionCount = 0
        self.isSelectionMode = False
        self.commandView = TaskCommandBarView(self.window())

        # id ---> task card
        self.cardMap = {}  # type: Dict[str, TaskCardBase]

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setSpacing(5)
        self.vBoxLayout.setContentsMargins(30, 0, 30, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.commandView.hide()
        self._connectSignalToSlot()

    def createCard(self, task: Task) -> TaskCardBase:
        raise NotImplementedError

    def addTask(self, task: Task) -> TaskCardBase:
        card = self.createCard(task)
        card.deleted.connect(self.removeTask)
        card.checkedChanged.connect(self._onCardCheckedChanged)

        if self.isSelectionMode:
            card.setSelectionMode(True)

        self.vBoxLayout.insertWidget(0, card, 0, Qt.AlignmentFlag.AlignTop)
        self.cards.insert(0, card)
        self.cardMap[task.id] = card

    def removeTask(self, task: Task):
        if task.id not in self.cardMap:
            return

        card = self.cardMap.pop(task.id)
        self.cards.remove(card)
        self.vBoxLayout.removeWidget(card)

        if card.isSelectionMode:
            self._onCardCheckedChanged(False)

        card.hide()
        card.deleteLater()

        self.cardCountChanged.emit(self.count())

    def findCard(self, task: Task):
        return self.cardMap.get(task.id)

    def count(self):
        return len(self.cards)

    def _onCardCheckedChanged(self, checked: bool):
        if checked:
            self.selectionCount += 1
            self.setSelectionMode(True)
        else:
            self.selectionCount -= 1
            if self.selectionCount == 0:
                self.setSelectionMode(False)

    def setSelectionMode(self, enter: bool):
        if self.isSelectionMode == enter:
            return

        self.isSelectionMode = enter

        for card in self.cards:
            card.setSelectionMode(enter)

        if enter:
            self.commandView.setVisible(True)
            self.commandView.raise_()
        else:
            self.commandView.setVisible(False)
            self.selectionCount = 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        x = self.window().width() // 2 - self.commandView.width() // 2
        y = self.window().height() - self.commandView.sizeHint().height() - 20
        self.commandView.move(x, y)

    def selectAll(self):
        for card in self.cards:
            card.setChecked(True)

    def _removeSelectedTasks(self):
        w = DeleteTaskDialog(self.window(), deleteOnClose=False)
        w.contentLabel.setText(self.tr("Are you sure to delete these selected tasks?"))
        w.deleteFileCheckBox.setChecked(False)

        if w.exec():
            for card in self.cards.copy():
                if card.isChecked():
                    card.removeTask(w.deleteFileCheckBox.isChecked())

        w.deleteLater()

    def _restartSelectedTasks(self):
        for card in self.cards.copy():
            if card.isChecked():
                card.redownload()

    def _connectSignalToSlot(self):
        self.commandView.redownloadAction.triggered.connect(self._restartSelectedTasks)
        self.commandView.deleteAction.triggered.connect(self._removeSelectedTasks)
        self.commandView.selectAllAction.triggered.connect(self.selectAll)
        self.commandView.cancelAction.triggered.connect(lambda: self.setSelectionMode(False))


class DownloadingTaskView(TaskCardView):
    """ Downloading task view """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("downloading")
        self.commandView.bar.commandButtons[0].hide()

    def createCard(self, task: Task):
        return LiveDownloadingTaskCard(task) if task.isLive else VODDownloadingTaskCard(task)


class SuccessTaskView(TaskCardView):
    """ Success task view """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("finished")

        # load cards
        sqlRequest(
            "taskService",
            "listBy",
            self._loadTasks,
            status=TaskStatus.SUCCESS,
            orderBy="createTime",
            asc=True
        )

    def _loadTasks(self, tasks: List[Task]):
        if not tasks:
            return

        for task in tasks:
            self.addTask(task)

        self.cardCountChanged.emit(self.count())

    def createCard(self, task: Task):
        return SuccessTaskCard(task, self)


class FailedTaskView(TaskCardView):
    """ Failed task view """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("failed")

        # load cards
        sqlRequest(
            "taskService",
            "listBy",
            self._loadTasks,
            status=TaskStatus.FAILED,
            orderBy="createTime",
            asc=True
        )

    def _loadTasks(self, tasks: List[Task]):
        if not tasks:
            return

        for task in tasks:
            self.addTask(task)

        self.cardCountChanged.emit(self.count())

    def createCard(self, task: Task):
        return FailedTaskCard(task, self)


class TaskStackedWidget(QStackedWidget):

    def sizeHint(self):
        return self.currentWidget().sizeHint()

    def minimumSizeHint(self):
        return self.currentWidget().minimumSizeHint()


class TaskCommandBarView(CommandBarView):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.redownloadAction = Action(FluentIcon.UPDATE, self.tr("Restart"), self)
        self.deleteAction = Action(FluentIcon.DELETE, self.tr("Delete"), self)
        self.selectAllAction = Action(Icon.SELECT, self.tr("Select All"), self)
        self.cancelAction = Action(FluentIcon.CLEAR_SELECTION, self.tr("Cancel"), self)

        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(18, 18))
        self.addActions([self.redownloadAction, self.deleteAction])
        self.addSeparator()
        self.addActions([self.selectAllAction, self.cancelAction])
        self.resizeToSuitableWidth()
        self.setShadowEffect()

    def setShadowEffect(self, blurRadius=35, offset=(0, 8)):
        """ add shadow to dialog """
        color = QColor(0, 0, 0, 80 if isDarkTheme() else 30)
        self.shadowEffect = QGraphicsDropShadowEffect(self)
        self.shadowEffect.setBlurRadius(blurRadius)
        self.shadowEffect.setOffset(*offset)
        self.shadowEffect.setColor(color)
        self.setGraphicsEffect(None)
        self.setGraphicsEffect(self.shadowEffect)
