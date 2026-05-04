import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: root
    property var backend: null
    width: 980
    height: 560
    minimumWidth: 760
    minimumHeight: 460
    visible: true
    title: "xxdz_上一个桌面背景"
    color: "#f7f8fa"
    onClosing: function(close) {
        if (!forceQuit && backend.value("run_in_background") === true) {
            close.accepted = false
            root.hide()
        }
    }

    readonly property color bg: "#f7f8fa"
    readonly property color panel: "#ffffff"
    readonly property color surface: "#f2f4f7"
    readonly property color textColor: "#111827"
    readonly property color muted: "#667085"
    readonly property color border: "#d0d5dd"
    readonly property color borderSoft: "#eaecf0"
    readonly property color accent: "#0d99ff"
    readonly property color accentSoft: "#e5f4ff"
    readonly property url appIcon: Qt.resolvedUrl("../img/LOGO.ico")
    readonly property url aboutSprite: Qt.resolvedUrl("../img/about.png")
    readonly property url aboutWindowImage: Qt.resolvedUrl("../img/about-window.png")
    property var modes: ["幻灯片放映", "图片", "视频", "纯色", "渐变"]
    property var fitModes: ["填充", "适应", "拉伸", "平铺", "居中"]
    property var freqLabels: ["自定义时间", "5秒", "10秒", "30秒", "1分钟", "5分钟", "30分钟", "1小时", "6小时", "12小时", "1天", "2天", "1周", "1个月", "6个月", "1年", "50年", "666年"]
    property var freqSeconds: [0, 5, 10, 30, 60, 300, 1800, 3600, 21600, 43200, 86400, 172800, 604800, 2592000, 15552000, 31536000, 1576800000, 210000000]
    property bool forceQuit: false

    function value(key, fallback) {
        if (!backend)
            return fallback
        var v = backend.value(key)
        return v === undefined || v === null || v === "" ? fallback : v
    }

    function selectedIndex(model, current) {
        var idx = model.indexOf(current)
        return idx < 0 ? 0 : idx
    }

    function frequencyIndex() {
        var seconds = Number(value("slide_seconds", 300))
        var idx = freqSeconds.indexOf(seconds)
        return idx < 0 ? 0 : idx
    }

    function trayActionLabel(action) {
        if (!backend)
            return action
        var idx = backend.trayActionKeys.indexOf(action)
        return idx >= 0 ? backend.trayActionLabels[idx] : action
    }

    function canSwitchWallpaper() {
        return backend && backend.mode === "幻灯片放映"
    }

    function parseJson(text) {
        try {
            return JSON.parse(text)
        } catch (e) {
            return ({})
        }
    }

    Connections {
        target: backend
        function onRequestShow() {
            root.show()
            root.raise()
            root.requestActivate()
        }
        function onRequestAbout() {
            aboutWindow.openWindow()
        }
        function onChanged() {
            refreshFields()
        }
        function onRecentFoldersChanged() {
            refreshFields()
        }
        function onModeChanged() {
            modeCombo.currentIndex = selectedIndex(modes, backend.mode)
        }
    }

    FolderDialog {
        id: folderDialog
        title: "选择幻灯片文件夹"
        onAccepted: backend.setSlideFolder(selectedFolder)
    }

    FileDialog {
        id: imageDialog
        title: "选择图片"
        nameFilters: ["Images (*.jpg *.jpeg *.png *.bmp *.gif)"]
        onAccepted: backend.setImageFile(selectedFile)
    }

    FileDialog {
        id: videoDialog
        title: "选择视频"
        nameFilters: ["Videos (*.mp4 *.mov *.m4v *.avi *.mkv)"]
        onAccepted: backend.setVideoFile(selectedFile)
    }

    component Panel: Rectangle {
        color: panel
        border.color: borderSoft
        border.width: 1
        radius: 18
    }

    component FieldLabel: Label {
        color: textColor
        font.pixelSize: 13
        font.weight: Font.Medium
        Layout.preferredWidth: 82
        verticalAlignment: Text.AlignVCenter
    }

    component FButton: Button {
        id: control
        font.pixelSize: 13
        implicitHeight: 38
        background: Rectangle {
            radius: 12
            color: control.down ? "#e4e7ec" : (control.hovered ? surface : panel)
            border.color: border
            border.width: 1
        }
        contentItem: Text {
            text: control.text
            color: textColor
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    component PrimaryButton: FButton {
        background: Rectangle {
            radius: 12
            color: parent.down ? "#007be5" : accent
            border.color: accent
        }
        contentItem: Text {
            text: parent.text
            color: "white"
            font.weight: Font.Bold
            font.pixelSize: parent.font.pixelSize
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    component FTextField: TextField {
        color: textColor
        selectedTextColor: textColor
        selectionColor: accentSoft
        font.pixelSize: 13
        implicitHeight: 38
        background: Rectangle {
            radius: 12
            color: panel
            border.color: parent.activeFocus ? accent : border
            border.width: 1
        }
    }

    component FCombo: ComboBox {
        id: control
        font.pixelSize: 13
        implicitHeight: 38
        delegate: ItemDelegate {
            width: control.width
            height: 34
            highlighted: control.highlightedIndex === index
            contentItem: Text {
                text: modelData
                color: textColor
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                leftPadding: 10
            }
            background: Rectangle {
                radius: 10
                color: highlighted || hovered ? accentSoft : "transparent"
            }
        }
        contentItem: Text {
            text: control.displayText
            color: textColor
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            leftPadding: 12
            rightPadding: 28
        }
        background: Rectangle {
            radius: 12
            color: panel
            border.color: control.activeFocus ? accent : border
            border.width: 1
        }
        popup: Popup {
            y: control.height + 6
            width: control.width
            implicitHeight: Math.min(contentItem.implicitHeight + 16, 260)
            padding: 8
            background: Rectangle {
                radius: 16
                color: panel
                border.color: border
                border.width: 1
            }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
                boundsBehavior: Flickable.StopAtBounds
            }
        }
    }

    component FCheckBox: CheckBox {
        id: control
        spacing: 7
        implicitHeight: Math.max(24, label.implicitHeight)
        indicator: Rectangle {
            implicitWidth: 14
            implicitHeight: 14
            x: 1
            y: (control.height - height) / 2
            radius: 4
            color: control.checked ? accent : panel
            border.color: control.checked ? accent : border
            border.width: 1

            Rectangle {
                visible: control.checked
                width: 6
                height: 6
                radius: 2
                anchors.centerIn: parent
                color: "white"
            }
        }
        contentItem: Text {
            id: label
            text: control.text
            color: control.enabled ? textColor : "#98a2b3"
            font.pixelSize: 13
            verticalAlignment: Text.AlignVCenter
            leftPadding: control.indicator.width + control.spacing + 2
            wrapMode: Text.Wrap
        }
    }

    function refreshFields() {
        imagePath.text = value("single_image", "")
        videoPath.text = value("video_file", "")
        color1.text = value("solid_color", "#4facfe")
        color2.text = value("gradient_color2", "#00f2fe")
        gradientAngle.value = Number(value("gradient_angle", 60))
        transitionToggle.checked = value("transition_animation", true) === true
        trayToggle.checked = value("tray_icon", true) === true
        backgroundToggle.checked = value("run_in_background", true) === true
        autoStartToggle.checked = value("auto_start", false) === true
        shuffleToggle.checked = value("shuffle", false) === true
        manualToggle.checked = value("manual_mode", false) === true
        fitCombo.currentIndex = selectedIndex(fitModes, value("fit_mode", "填充"))
        imageFitCombo.currentIndex = fitCombo.currentIndex
        frequencyCombo.currentIndex = frequencyIndex()
        albumCombo.currentIndex = backend.currentSlideFolderIndex
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: Math.max(10, Math.min(16, root.width * 0.016))
        radius: 24
        color: panel
        border.color: borderSoft

        RowLayout {
            anchors.fill: parent
            anchors.margins: Math.max(10, Math.min(16, root.width * 0.016))
            spacing: Math.max(10, Math.min(18, root.width * 0.018))

            Panel {
                Layout.preferredWidth: Math.max(280, Math.min(430, root.width * 0.41))
                Layout.minimumWidth: 280
                Layout.maximumWidth: 460
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Math.max(7, Math.min(10, root.width * 0.01))
                    spacing: Math.max(4, Math.min(7, root.height * 0.012))

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(145, Math.min(230, root.height * 0.38))
                        Layout.minimumHeight: 135
                        radius: 16
                        color: surface
                        border.color: borderSoft
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: backend.previewSource
                            fillMode: Image.PreserveAspectFit
                            visible: source !== ""
                        }
                        Label {
                            anchors.centerIn: parent
                            text: "暂无预览"
                            color: muted
                            visible: backend.previewSource === ""
                        }
                    }

                    RowLayout {
                        Layout.topMargin: 4
                        spacing: 6
                        FButton { text: "上一张"; implicitHeight: 32; Layout.fillWidth: true; enabled: canSwitchWallpaper(); onClicked: backend.previous() }
                        FButton { text: "下一张"; implicitHeight: 32; Layout.fillWidth: true; enabled: canSwitchWallpaper(); onClicked: backend.next() }
                        FButton { text: "随机"; implicitHeight: 32; Layout.fillWidth: true; enabled: canSwitchWallpaper(); onClicked: backend.randomWallpaper() }
                    }

                    Label {
                        text: backend.status
                        color: muted
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Label {
                        text: "实用设置"
                        color: textColor
                        font.pixelSize: 14
                        font.bold: true
                        Layout.topMargin: 5
                    }
                    FCheckBox { id: autoStartToggle; text: "开机自启动"; onToggled: backend.setBool("auto_start", checked) }
                    FCheckBox { id: backgroundToggle; text: "能后台运行"; onToggled: backend.setBool("run_in_background", checked) }
                    RowLayout {
                        spacing: 6
                        FCheckBox { id: trayToggle; text: "菜单栏/托盘常驻"; Layout.fillWidth: true; onToggled: backend.setBool("tray_icon", checked) }
                        FButton { text: "功能设置"; implicitHeight: 28; Layout.preferredWidth: 78; onClicked: trayDialog.openDialog() }
                    }
                    RowLayout {
                        spacing: 6
                        FCheckBox { id: transitionToggle; text: "壁纸切换过渡动画"; Layout.fillWidth: true; onToggled: backend.setBool("transition_animation", checked) }
                        FButton { text: "动画设置"; implicitHeight: 28; Layout.preferredWidth: 78; onClicked: transitionDialog.openDialog() }
                    }
                    RowLayout {
                        spacing: 6
                        FButton { text: "设置全局快捷键"; implicitHeight: 32; Layout.fillWidth: true; onClicked: hotkeyDialog.openDialog() }
                        FButton { text: "退出"; implicitHeight: 32; Layout.preferredWidth: 70; onClicked: { root.forceQuit = true; Qt.quit() } }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.minimumWidth: 360
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Math.max(8, Math.min(12, root.width * 0.012))
                    spacing: Math.max(6, Math.min(10, root.height * 0.018))

                    Label { text: "背景模式"; color: textColor; font.pixelSize: 16 }
                    FCombo {
                        id: modeCombo
                        model: modes
                        Layout.preferredWidth: 220
                        Component.onCompleted: currentIndex = selectedIndex(modes, backend.mode)
                        onActivated: backend.setMode(currentText)
                    }

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 120
                        clip: true
                        ColumnLayout {
                            width: parent.width
                            spacing: 12

                            ColumnLayout {
                                visible: backend.mode === "幻灯片放映"
                                Layout.fillWidth: true
                                Label { text: "幻灯片设置"; color: textColor; font.bold: true }
                                RowLayout {
                                    FieldLabel { text: "壁纸相册:" }
                                    FCombo {
                                        id: albumCombo
                                        model: backend.recentFolderLabels
                                        Layout.fillWidth: true
                                        onActivated: {
                                            var paths = backend.recentFolderPaths
                                            if (currentIndex >= 0 && currentIndex < paths.length && paths[currentIndex] !== "")
                                                backend.setSlideFolderPath(paths[currentIndex])
                                        }
                                    }
                                    FButton { text: "浏览"; onClicked: folderDialog.open() }
                                    FButton { text: "打开文件夹"; onClicked: backend.openSlideFolder() }
                                }
                                RowLayout {
                                    Repeater {
                                        model: backend.miniPreviews
                                        Rectangle {
                                            Layout.preferredWidth: Math.max(64, Math.min(86, root.width * 0.088))
                                            Layout.preferredHeight: Math.max(42, Math.min(54, root.height * 0.096))
                                            radius: 10; color: surface; border.color: borderSoft; clip: true
                                            Image { anchors.fill: parent; source: modelData; fillMode: Image.PreserveAspectCrop }
                                        }
                                    }
                                }
                                RowLayout {
                                    FieldLabel { text: "切换间隔:" }
                                    FCombo {
                                        id: frequencyCombo
                                        model: freqLabels
                                        Layout.preferredWidth: 150
                                        onActivated: {
                                            if (freqSeconds[currentIndex] > 0)
                                                backend.setInt("slide_seconds", freqSeconds[currentIndex])
                                        }
                                    }
                                    FCheckBox { id: manualToggle; text: "手动档"; onToggled: backend.setBool("manual_mode", checked) }
                                }
                                RowLayout {
                                    FCheckBox { id: shuffleToggle; text: "随机顺序"; onToggled: backend.setBool("shuffle", checked) }
                                    FButton { text: "设置随机概率"; implicitHeight: 30; enabled: backend.mode === "幻灯片放映"; onClicked: randomProbabilityWindow.openWindow() }
                                }
                                RowLayout {
                                    FieldLabel { text: "适应模式:" }
                                    FCombo { id: fitCombo; model: fitModes; Layout.preferredWidth: 140; onActivated: backend.setValue("fit_mode", currentText) }
                                }
                            }

                            ColumnLayout {
                                visible: backend.mode === "图片"
                                Layout.fillWidth: true
                                Label { text: "图片设置"; color: textColor; font.bold: true }
                                RowLayout {
                                    FieldLabel { text: "图片文件:" }
                                    FTextField { id: imagePath; Layout.fillWidth: true; onEditingFinished: backend.setValue("single_image", text) }
                                    FButton { text: "浏览"; onClicked: imageDialog.open() }
                                }
                                RowLayout {
                                    FieldLabel { text: "适应模式:" }
                                    FCombo { id: imageFitCombo; model: fitModes; Layout.preferredWidth: 140; onActivated: backend.setValue("fit_mode", currentText) }
                                }
                            }

                            ColumnLayout {
                                visible: backend.mode === "视频"
                                Layout.fillWidth: true
                                Label { text: "视频壁纸设置"; color: textColor; font.bold: true }
                                RowLayout {
                                    FieldLabel { text: "视频文件:" }
                                    FTextField { id: videoPath; Layout.fillWidth: true; onEditingFinished: backend.setValue("video_file", text) }
                                    FButton { text: "浏览"; onClicked: videoDialog.open() }
                                }
                                FCheckBox { text: "静音播放"; checked: value("video_muted", true) === true; onToggled: backend.setBool("video_muted", checked) }
                                RowLayout {
                                    FButton { text: "播放视频壁纸"; onClicked: backend.applyCurrentMode() }
                                    FButton { text: "停止视频壁纸"; onClicked: backend.stopVideo() }
                                }
                                Label { text: "视频壁纸会使用独立播放器，窗口不接收鼠标事件。"; color: muted }
                            }

                            ColumnLayout {
                                visible: backend.mode === "纯色" || backend.mode === "渐变"
                                Layout.fillWidth: true
                                Label { text: "颜色设置"; color: textColor; font.bold: true }
                                RowLayout {
                                    FieldLabel { text: "起始颜色:" }
                                    FTextField { id: color1; Layout.preferredWidth: 120; onEditingFinished: backend.setValue("solid_color", text) }
                                    Rectangle { width: 34; height: 28; radius: 8; color: color1.text; border.color: border }
                                }
                                RowLayout {
                                    FieldLabel { text: "结束颜色:" }
                                    FTextField { id: color2; Layout.preferredWidth: 120; onEditingFinished: backend.setValue("gradient_color2", text) }
                                    Rectangle { width: 34; height: 28; radius: 8; color: color2.text; border.color: border }
                                }
                                RowLayout {
                                    FieldLabel { text: "渐变角度:" }
                                    Slider { id: gradientAngle; from: 0; to: 180; Layout.fillWidth: true; onMoved: backend.setInt("gradient_angle", value) }
                                    Label { text: Math.round(gradientAngle.value) + " 度"; color: muted; Layout.preferredWidth: 52 }
                                }
                            }

                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.maximumHeight: 170
                        spacing: 2
                        Label { text: "右键菜单设置"; color: textColor; font.bold: true }
                        FCheckBox { text: "添加【Finder右键服务 → 上一张壁纸】"; checked: value("ctx_last_wallpaper", false) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_last_wallpaper", checked) }
                        FCheckBox { text: "添加【Finder右键服务 → 下一张壁纸】"; checked: value("ctx_next_wallpaper", true) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_next_wallpaper", checked) }
                        FCheckBox { text: "添加【Finder右键服务 → 随机壁纸】"; checked: value("ctx_random_wallpaper", false) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_random_wallpaper", checked) }
                        FCheckBox { text: "添加【Finder右键服务 → 跳转到壁纸】"; checked: value("ctx_jump_to_wallpaper", true) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_jump_to_wallpaper", checked) }
                        FCheckBox { text: "添加【Finder文件右键 → 设为壁纸】"; checked: value("ctx_set_wallpaper", false) === true; onToggled: backend.setBool("ctx_set_wallpaper", checked) }
                        FCheckBox { text: "添加【Finder右键服务 → 显示主界面】"; checked: value("ctx_personalize", true) === true; onToggled: backend.setBool("ctx_personalize", checked) }
                    }

                    PrimaryButton {
                        text: "应用当前设置"
                        Layout.preferredWidth: 140
                        onClicked: backend.applyCurrentMode()
                    }
                }
            }
        }
    }

    Item {
        id: aboutButton
        width: Math.max(42, Math.min(54, root.width * 0.052))
        height: width
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: Math.max(12, Math.min(22, root.width * 0.02))
        anchors.bottomMargin: Math.max(10, Math.min(18, root.height * 0.028))
        property int frameIndex: aboutMouse.pressed ? 2 : (aboutMouse.containsMouse ? 1 : 0)
        z: 20

        Image {
            anchors.fill: parent
            source: aboutSprite
            sourceClipRect: Qt.rect(0, aboutButton.frameIndex * 216, 216, 216)
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
        }

        MouseArea {
            id: aboutMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: aboutWindow.openWindow()
        }
    }

    Window {
        id: aboutWindow
        title: "关于 上一个桌面背景"
        width: Math.min(root.width - 80, 760)
        height: Math.min(root.height - 80, 560)
        minimumWidth: 420
        minimumHeight: 320
        visible: false
        color: "transparent"
        flags: Qt.Window

        function openWindow() {
            width = Math.min(root.width - 80, 760)
            height = Math.min(root.height - 80, 560)
            x = root.x + Math.max(20, (root.width - width) / 2)
            y = root.y + Math.max(20, (root.height - height) / 2)
            show()
            raise()
            requestActivate()
        }

        Rectangle {
            anchors.fill: parent
            color: panel
            radius: 18
            border.color: borderSoft
            border.width: 1
            clip: true

            Image {
                anchors.fill: parent
                anchors.margins: 10
                source: aboutWindowImage
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }
    }

    Window {
        id: hotkeyDialog
        title: "设置快捷键"
        width: Math.min(620, root.width - 80)
        height: Math.min(390, root.height - 80)
        minimumWidth: 480
        minimumHeight: 300
        visible: false
        color: panel
        flags: Qt.Window
        property var fields: ({})
        function openDialog() {
            width = Math.min(620, root.width - 80)
            height = Math.min(390, root.height - 80)
            x = root.x + Math.max(20, (root.width - width) / 2)
            y = root.y + Math.max(20, (root.height - height) / 2)
            var pairs = backend.hotkeyPairs()
            for (var i = 0; i < pairs.length; i++) {
                var p = String(pairs[i]).split("=")
                fields[p[0]] = p.slice(1).join("=")
            }
            previousHotkey.text = fields.previous || ""
            nextHotkey.text = fields.next || ""
            randomHotkey.text = fields.random || ""
            showHotkey.text = fields.show || ""
            jumpHotkey.text = fields.jump || ""
            show()
            raise()
            requestActivate()
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12
            GridLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                columns: 2
                rowSpacing: 10
                columnSpacing: 10
                FieldLabel { text: "上一张:" } FTextField { id: previousHotkey; Layout.fillWidth: true; placeholderText: "u / ctrl+alt+u" }
                FieldLabel { text: "下一张:" } FTextField { id: nextHotkey; Layout.fillWidth: true; placeholderText: "n" }
                FieldLabel { text: "随机:" } FTextField { id: randomHotkey; Layout.fillWidth: true; placeholderText: "3" }
                FieldLabel { text: "显示主界面:" } FTextField { id: showHotkey; Layout.fillWidth: true; placeholderText: "x" }
                FieldLabel { text: "跳转壁纸:" } FTextField { id: jumpHotkey; Layout.fillWidth: true; placeholderText: "v" }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FButton { text: "取消"; Layout.preferredWidth: 90; onClicked: hotkeyDialog.close() }
                PrimaryButton { text: "保存"; Layout.preferredWidth: 90; onClicked: { saveHotkeys(); hotkeyDialog.close() } }
            }
        }
    }

    Window {
        id: trayDialog
        title: "菜单栏/托盘功能设置"
        width: Math.min(620, root.width - 80)
        height: Math.min(460, root.height - 80)
        minimumWidth: 460
        minimumHeight: 340
        visible: false
        color: panel
        flags: Qt.Window
        ListModel { id: trayModel }
        function openDialog() {
            width = Math.min(620, root.width - 80)
            height = Math.min(460, root.height - 80)
            x = root.x + Math.max(20, (root.width - width) / 2)
            y = root.y + Math.max(20, (root.height - height) / 2)
            fillTrayModel()
            show()
            raise()
            requestActivate()
        }
        function fillTrayModel() {
            trayModel.clear()
            var enabledItems = backend.trayMenuItems()
            var added = ({})
            for (var i = 0; i < enabledItems.length; i++) {
                var action = String(enabledItems[i])
                if (backend.trayActionKeys.indexOf(action) >= 0 && !added[action]) {
                    trayModel.append({ "actionKey": action, "label": trayActionLabel(action), "checked": true })
                    added[action] = true
                }
            }
            for (var j = 0; j < backend.trayActionKeys.length; j++) {
                var rest = String(backend.trayActionKeys[j])
                if (!added[rest])
                    trayModel.append({ "actionKey": rest, "label": trayActionLabel(rest), "checked": false })
            }
        }
        function moveItem(from, to) {
            if (from < 0 || to < 0 || from >= trayModel.count || to >= trayModel.count || from === to)
                return
            trayModel.move(from, to, 1)
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10
            Label { text: "勾选要显示的功能项，可用右侧按钮调整菜单顺序"; color: muted }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: trayModel
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 42
                    radius: 12
                    color: hovered ? surface : panel
                    border.color: borderSoft
                    border.width: 1
                    property bool hovered: false

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 8
                        FCheckBox {
                            Layout.fillWidth: true
                            text: model.label
                            checked: model.checked
                            onToggled: trayModel.setProperty(index, "checked", checked)
                        }
                        FButton {
                            text: "↑"
                            implicitHeight: 28
                            Layout.preferredWidth: 34
                            enabled: index > 0
                            onClicked: trayDialog.moveItem(index, index - 1)
                        }
                        FButton {
                            text: "↓"
                            implicitHeight: 28
                            Layout.preferredWidth: 34
                            enabled: index < trayModel.count - 1
                            onClicked: trayDialog.moveItem(index, index + 1)
                        }
                    }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FButton { text: "取消"; Layout.preferredWidth: 90; onClicked: trayDialog.close() }
                PrimaryButton { text: "保存"; Layout.preferredWidth: 90; onClicked: { saveTray(); trayDialog.close() } }
            }
        }
    }

    Window {
        id: transitionDialog
        title: "过渡动画设置"
        width: Math.min(560, root.width - 80)
        height: Math.min(420, root.height - 80)
        minimumWidth: 430
        minimumHeight: 300
        visible: false
        color: panel
        flags: Qt.Window
        function openDialog() {
            width = Math.min(560, root.width - 80)
            height = Math.min(420, root.height - 80)
            x = root.x + Math.max(20, (root.width - width) / 2)
            y = root.y + Math.max(20, (root.height - height) / 2)
            effectCombo.currentIndex = value("transition_effect", "smooth") === "frame" ? 1 : 0
            smoothCombo.currentIndex = ["fade", "scan", "slide", "random"].indexOf(value("smooth_effect", "fade"))
            if (smoothCombo.currentIndex < 0) smoothCombo.currentIndex = 0
            directionCombo.currentIndex = ["left", "right", "up", "down", "random"].indexOf(value("slide_direction", "right"))
            if (directionCombo.currentIndex < 0) directionCombo.currentIndex = 1
            durationField.value = Math.round(Number(value("transition_duration", 1.0)) * 10)
            framesField.value = Number(value("transition_frames", 18))
            show()
            raise()
            requestActivate()
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                RowLayout { FieldLabel { text: "转场原理:" } FCombo { id: effectCombo; model: ["丝滑转场", "帧动画"]; Layout.preferredWidth: 160 } }
                RowLayout { visible: effectCombo.currentIndex === 0; FieldLabel { text: "转场效果:" } FCombo { id: smoothCombo; model: ["渐显混合", "放映机", "滑入", "随机转场"]; Layout.preferredWidth: 160 } }
                RowLayout { visible: effectCombo.currentIndex === 0 && (smoothCombo.currentIndex === 1 || smoothCombo.currentIndex === 2); FieldLabel { text: "动画方向:" } FCombo { id: directionCombo; model: ["← 向左", "向右 →", "↑ 向上", "向下 ↓", "随机方向"]; Layout.preferredWidth: 160 } }
                RowLayout { FieldLabel { text: "持续时间:" } SpinBox { id: durationField; from: 1; to: 100; editable: true; value: 10; textFromValue: function(v) { return (v / 10).toFixed(1) + " 秒" }; valueFromText: function(t) { return Math.round(parseFloat(t) * 10) } } }
                RowLayout { visible: effectCombo.currentIndex === 1; FieldLabel { text: "帧数:" } SpinBox { id: framesField; from: 8; to: 60; editable: true; value: 18 } }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                FButton { text: "取消"; Layout.preferredWidth: 90; onClicked: transitionDialog.close() }
                PrimaryButton { text: "保存"; Layout.preferredWidth: 90; onClicked: { saveTransition(); transitionDialog.close() } }
            }
        }
    }

    Window {
        id: randomProbabilityWindow
        title: "随机概率设置"
        width: Math.min(760, root.width - 60)
        height: Math.min(560, root.height - 60)
        minimumWidth: 520
        minimumHeight: 360
        visible: false
        color: panel
        flags: Qt.Window
        ListModel { id: randomProbabilityModel }

        function openWindow() {
            width = Math.min(760, root.width - 60)
            height = Math.min(560, root.height - 60)
            x = root.x + Math.max(20, (root.width - width) / 2)
            y = root.y + Math.max(20, (root.height - height) / 2)
            loadItems()
            show()
            raise()
            requestActivate()
        }

        function loadItems() {
            randomProbabilityModel.clear()
            var items = backend.randomProbabilityItems()
            for (var i = 0; i < items.length; i++) {
                var item = parseJson(items[i])
                if (item.filename !== undefined) {
                    randomProbabilityModel.append({
                        "filename": item.filename,
                        "count": Number(item.count || 0),
                        "preview": item.preview || ""
                    })
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10

            Label {
                text: "数值越高，被随机到的概率越高；0 表示普通概率"
                color: muted
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 8
                model: randomProbabilityModel
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 74
                    radius: 14
                    color: hovered ? surface : panel
                    border.color: borderSoft
                    border.width: 1
                    property bool hovered: false

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 10

                        Rectangle {
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 56
                            radius: 10
                            color: surface
                            border.color: borderSoft
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: model.preview
                                fillMode: Image.PreserveAspectCrop
                            }
                        }

                        Label {
                            text: model.filename
                            color: textColor
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                            verticalAlignment: Text.AlignVCenter
                        }

                        Label {
                            text: "附加值"
                            color: muted
                            font.pixelSize: 12
                        }

                        RowLayout {
                            Layout.preferredWidth: 106
                            spacing: 4
                            FButton {
                                text: "-"
                                implicitHeight: 24
                                Layout.preferredWidth: 26
                                enabled: model.count > 0
                                onClicked: randomProbabilityModel.setProperty(index, "count", Math.max(0, model.count - 1))
                            }
                            Rectangle {
                                Layout.preferredWidth: 38
                                Layout.preferredHeight: 24
                                radius: 8
                                color: panel
                                border.color: border
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: model.count
                                    color: textColor
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                }
                            }
                            FButton {
                                text: "+"
                                implicitHeight: 24
                                Layout.preferredWidth: 26
                                enabled: model.count < 20
                                onClicked: randomProbabilityModel.setProperty(index, "count", Math.min(20, model.count + 1))
                            }
                        }
                    }
                }
            }

            Label {
                visible: randomProbabilityModel.count === 0
                text: "当前相册中没有可设置的图片"
                color: muted
                Layout.alignment: Qt.AlignHCenter
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                FButton { text: "取消"; Layout.preferredWidth: 90; onClicked: randomProbabilityWindow.close() }
                PrimaryButton {
                    text: "保存"
                    Layout.preferredWidth: 90
                    onClicked: {
                        var pairs = []
                        for (var i = 0; i < randomProbabilityModel.count; i++) {
                            var item = randomProbabilityModel.get(i)
                            pairs.push(item.filename + "=" + item.count)
                        }
                        backend.saveRandomProbability(pairs)
                        randomProbabilityWindow.close()
                    }
                }
            }
        }
    }

    function saveTray() {
        var tray = []
        for (var i = 0; i < trayModel.count; i++) {
            var item = trayModel.get(i)
            if (item.checked)
                tray.push(item.actionKey)
        }
        backend.saveTraySettings(tray)
    }

    function saveHotkeys() {
        var hotkeys = [
            "previous=" + previousHotkey.text,
            "next=" + nextHotkey.text,
            "random=" + randomHotkey.text,
            "show=" + showHotkey.text,
            "jump=" + jumpHotkey.text
        ]
        backend.saveHotkeySettings(hotkeys)
    }

    function saveTransition() {
        var effect = effectCombo.currentIndex === 1 ? "frame" : "smooth"
        var smooth = ["fade", "scan", "slide", "random"][smoothCombo.currentIndex]
        var direction = ["left", "right", "up", "down", "random"][directionCombo.currentIndex]
        backend.saveTransitionSettings(effect, durationField.value / 10.0, framesField.value, smooth, direction, transitionToggle.checked)
    }

    Component.onCompleted: refreshFields()
}
