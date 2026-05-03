import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 980
    height: 560
    minimumWidth: 920
    minimumHeight: 520
    visible: true
    title: "xxdz_上一个桌面背景"
    color: "#f7f8fa"

    readonly property color bg: "#f7f8fa"
    readonly property color panel: "#ffffff"
    readonly property color surface: "#f2f4f7"
    readonly property color textColor: "#111827"
    readonly property color muted: "#667085"
    readonly property color border: "#d0d5dd"
    readonly property color borderSoft: "#eaecf0"
    readonly property color accent: "#0d99ff"
    readonly property color accentSoft: "#e5f4ff"
    property var modes: ["幻灯片放映", "图片", "视频", "纯色", "渐变"]
    property var fitModes: ["填充", "适应", "拉伸", "平铺", "居中"]
    property var freqLabels: ["自定义时间", "5秒", "10秒", "30秒", "1分钟", "5分钟", "30分钟", "1小时", "6小时", "12小时", "1天", "2天", "1周", "1个月", "6个月", "1年", "50年", "666年"]
    property var freqSeconds: [0, 5, 10, 30, 60, 300, 1800, 3600, 21600, 43200, 86400, 172800, 604800, 2592000, 15552000, 31536000, 1576800000, 210000000]

    function value(key, fallback) {
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

    Connections {
        target: backend
        function onRequestShow() {
            root.show()
            root.raise()
            root.requestActivate()
        }
        function onChanged() {
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
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 16
        radius: 24
        color: panel
        border.color: borderSoft

        RowLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 18

            Panel {
                Layout.preferredWidth: 400
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 250
                        radius: 18
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
                        Layout.topMargin: 10
                        FButton { text: "上一张"; Layout.fillWidth: true; onClicked: backend.previous() }
                        FButton { text: "下一张"; Layout.fillWidth: true; onClicked: backend.next() }
                        FButton { text: "随机"; Layout.fillWidth: true; onClicked: backend.randomWallpaper() }
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
                        font.pixelSize: 15
                        font.bold: true
                        Layout.topMargin: 12
                    }
                    CheckBox { id: autoStartToggle; text: "开机自启动"; onToggled: backend.setBool("auto_start", checked) }
                    CheckBox { id: backgroundToggle; text: "能后台运行"; onToggled: backend.setBool("run_in_background", checked) }
                    RowLayout {
                        CheckBox { id: trayToggle; text: "菜单栏/托盘常驻"; Layout.fillWidth: true; onToggled: backend.setBool("tray_icon", checked) }
                        FButton { text: "功能设置"; onClicked: trayDialog.openDialog() }
                    }
                    RowLayout {
                        CheckBox { id: transitionToggle; text: "壁纸切换过渡动画"; Layout.fillWidth: true; onToggled: backend.setBool("transition_animation", checked) }
                        FButton { text: "动画设置"; onClicked: transitionDialog.openDialog() }
                    }
                    RowLayout {
                        FButton { text: "设置全局快捷键"; Layout.fillWidth: true; onClicked: hotkeyDialog.openDialog() }
                        FButton { text: "退出"; onClicked: Qt.quit() }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            Panel {
                Layout.preferredWidth: 500
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

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
                                    FTextField { text: backend.slideFolderLabel; readOnly: true; Layout.fillWidth: true }
                                    FButton { text: "浏览"; onClicked: folderDialog.open() }
                                    FButton { text: "打开文件夹"; onClicked: backend.openSlideFolder() }
                                }
                                RowLayout {
                                    Repeater {
                                        model: backend.miniPreviews
                                        Rectangle {
                                            width: 86; height: 54; radius: 10; color: surface; border.color: borderSoft; clip: true
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
                                    CheckBox { id: manualToggle; text: "手动档"; onToggled: backend.setBool("manual_mode", checked) }
                                }
                                RowLayout {
                                    CheckBox { id: shuffleToggle; text: "随机顺序"; onToggled: backend.setBool("shuffle", checked) }
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
                                CheckBox { text: "静音播放"; checked: value("video_muted", true) === true; onToggled: backend.setBool("video_muted", checked) }
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

                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: "右键菜单设置"; color: textColor; font.bold: true }
                                CheckBox { text: "添加【Finder右键服务 → 上一张壁纸】"; checked: value("ctx_last_wallpaper", false) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_last_wallpaper", checked) }
                                CheckBox { text: "添加【Finder右键服务 → 下一张壁纸】"; checked: value("ctx_next_wallpaper", true) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_next_wallpaper", checked) }
                                CheckBox { text: "添加【Finder右键服务 → 随机壁纸】"; checked: value("ctx_random_wallpaper", false) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_random_wallpaper", checked) }
                                CheckBox { text: "添加【Finder右键服务 → 跳转到壁纸】"; checked: value("ctx_jump_to_wallpaper", true) === true; enabled: backend.mode === "幻灯片放映"; onToggled: backend.setBool("ctx_jump_to_wallpaper", checked) }
                                CheckBox { text: "添加【Finder文件右键 → 设为壁纸】"; checked: value("ctx_set_wallpaper", false) === true; onToggled: backend.setBool("ctx_set_wallpaper", checked) }
                                CheckBox { text: "添加【Finder右键服务 → 显示主界面】"; checked: value("ctx_personalize", true) === true; onToggled: backend.setBool("ctx_personalize", checked) }
                            }
                        }
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

    Dialog {
        id: hotkeyDialog
        title: "设置快捷键"
        modal: true
        standardButtons: Dialog.Save | Dialog.Cancel
        width: 620
        height: 390
        property var fields: ({})
        function openDialog() {
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
            open()
        }
        onAccepted: saveAdvanced()
        GridLayout {
            anchors.fill: parent
            columns: 2
            rowSpacing: 10
            columnSpacing: 10
            FieldLabel { text: "上一张:" } FTextField { id: previousHotkey; Layout.fillWidth: true; placeholderText: "u / ctrl+alt+u" }
            FieldLabel { text: "下一张:" } FTextField { id: nextHotkey; Layout.fillWidth: true; placeholderText: "n" }
            FieldLabel { text: "随机:" } FTextField { id: randomHotkey; Layout.fillWidth: true; placeholderText: "3" }
            FieldLabel { text: "显示主界面:" } FTextField { id: showHotkey; Layout.fillWidth: true; placeholderText: "x" }
            FieldLabel { text: "跳转壁纸:" } FTextField { id: jumpHotkey; Layout.fillWidth: true; placeholderText: "v" }
        }
    }

    Dialog {
        id: trayDialog
        title: "菜单栏/托盘功能设置"
        modal: true
        standardButtons: Dialog.Save | Dialog.Cancel
        width: 620
        height: 460
        property var enabledItems: []
        function openDialog() {
            enabledItems = backend.trayMenuItems()
            for (var i = 0; i < trayChecks.count; i++) {
                var item = trayChecks.itemAt(i)
                if (item)
                    item.checked = enabledItems.indexOf(item.actionKey) >= 0
            }
            open()
        }
        onAccepted: saveAdvanced()
        ColumnLayout {
            anchors.fill: parent
            Label { text: "勾选要显示在菜单栏/托盘中的功能项"; color: muted }
            Repeater {
                id: trayChecks
                model: backend.trayActionKeys
                CheckBox {
                    property string actionKey: modelData
                    text: backend.trayActionLabels[index]
                }
            }
        }
    }

    Dialog {
        id: transitionDialog
        title: "过渡动画设置"
        modal: true
        standardButtons: Dialog.Save | Dialog.Cancel
        width: 560
        height: 420
        function openDialog() {
            effectCombo.currentIndex = value("transition_effect", "smooth") === "frame" ? 1 : 0
            smoothCombo.currentIndex = ["fade", "slide", "scan", "random"].indexOf(value("smooth_effect", "fade"))
            if (smoothCombo.currentIndex < 0) smoothCombo.currentIndex = 0
            directionCombo.currentIndex = ["left", "right", "up", "down", "random"].indexOf(value("slide_direction", "right"))
            if (directionCombo.currentIndex < 0) directionCombo.currentIndex = 1
            durationField.value = Number(value("transition_duration", 1.0))
            framesField.value = Number(value("transition_frames", 12))
            open()
        }
        onAccepted: saveAdvanced()
        ColumnLayout {
            anchors.fill: parent
            RowLayout { FieldLabel { text: "转场原理:" } FCombo { id: effectCombo; model: ["丝滑转场", "帧动画"]; Layout.preferredWidth: 160 } }
            RowLayout { visible: effectCombo.currentIndex === 0; FieldLabel { text: "转场效果:" } FCombo { id: smoothCombo; model: ["渐显混合", "放映机", "滑入", "随机转场"]; Layout.preferredWidth: 160 } }
            RowLayout { visible: effectCombo.currentIndex === 0 && (smoothCombo.currentIndex === 1 || smoothCombo.currentIndex === 2); FieldLabel { text: "动画方向:" } FCombo { id: directionCombo; model: ["← 向左", "向右 →", "↑ 向上", "向下 ↓", "随机方向"]; Layout.preferredWidth: 160 } }
            RowLayout { FieldLabel { text: "持续时间:" } SpinBox { id: durationField; from: 1; to: 100; editable: true; value: 10; textFromValue: function(v) { return (v / 10).toFixed(1) + " 秒" }; valueFromText: function(t) { return Math.round(parseFloat(t) * 10) } } }
            RowLayout { visible: effectCombo.currentIndex === 1; FieldLabel { text: "帧数:" } SpinBox { id: framesField; from: 4; to: 30; editable: true; value: 12 } }
        }
    }

    function saveAdvanced() {
        var tray = []
        for (var i = 0; i < trayChecks.count; i++) {
            var item = trayChecks.itemAt(i)
            if (item && item.checked)
                tray.push(item.actionKey)
        }
        var hotkeys = [
            "previous=" + previousHotkey.text,
            "next=" + nextHotkey.text,
            "random=" + randomHotkey.text,
            "show=" + showHotkey.text,
            "jump=" + jumpHotkey.text
        ]
        var effect = effectCombo.currentIndex === 1 ? "frame" : "smooth"
        var smooth = ["fade", "slide", "scan", "random"][smoothCombo.currentIndex]
        var direction = ["left", "right", "up", "down", "random"][directionCombo.currentIndex]
        backend.saveAdvancedSettings(tray, hotkeys, [], effect, durationField.value / 10.0, framesField.value, smooth, direction, transitionToggle.checked)
    }

    Component.onCompleted: refreshFields()
}
