import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property string channel: "CH 01"
    property string subtitle: "原始采样"
    property color accent: "#007aff"
    property var samples: []
    property int windowSamples: 2500
    property real latest: 0
    property bool independentAxis: false
    property bool paused: false
    property int cursorA: -1
    property int cursorB: -1
    property int activeCursor: 0
    readonly property real deltaMs: cursorA >= 0 && cursorB >= 0 ? Math.abs(cursorB - cursorA) * 2 : 0

    function placeCursor(x, width) {
        if (!paused || !samples.length || width <= 0) return
        // Snap to real samples; the empty part of a short history is not measurable.
        let offset = windowSamples - Math.min(windowSamples, samples.length)
        let index = Math.max(offset, Math.min((card.windowSamples - 1), Math.round(x / width * (card.windowSamples - 1))))
        if (cursorA < 0) activeCursor = 0
        else if (cursorB < 0) activeCursor = 1
        else activeCursor = Math.abs(index - cursorA) <= Math.abs(index - cursorB) ? 0 : 1
        moveCursor(x, width)
    }

    function moveCursor(x, width) {
        if (!paused || !samples.length || width <= 0) return
        let offset = windowSamples - Math.min(windowSamples, samples.length)
        let index = Math.max(offset, Math.min((card.windowSamples - 1), Math.round(x / width * (card.windowSamples - 1))))
        if (activeCursor === 0) cursorA = index
        else cursorB = index
    }

    onPausedChanged: { cursorA = -1; cursorB = -1 }
    property real lowerLimit: -200000
    property real upperLimit: 200000
    property bool autoFit: true
    radius: 26
    color: "white"
    border.color: "#e5e9f0"
    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumHeight: paused ? 262 : 230
    Layout.preferredHeight: paused ? 262 : 230

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Rectangle { width: 10; height: 10; radius: 5; color: card.accent }
            HdText { renderType: Text.NativeRendering; text: card.channel; color: "#1c2434"; font.pixelSize: 19; font.weight: Font.DemiBold }
            HdText { renderType: Text.NativeRendering; text: card.subtitle; color: "#697589"; font.pixelSize: 13 }
            Item { Layout.fillWidth: true }
            HdText { renderType: Text.NativeRendering; text: card.latest.toLocaleString(Qt.locale(), 'f', 0); color: card.accent; font.pixelSize: 25; font.weight: Font.DemiBold }
            HdText { renderType: Text.NativeRendering; text: "ADC"; color: "#697589"; font.pixelSize: 12 }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                Layout.preferredWidth: 90
                Layout.fillHeight: true
                HdText { renderType: Text.NativeRendering; text: card.upperLimit.toLocaleString(Qt.locale(), 'f', 0); color: "#697589"; font.pixelSize: 11 }
                Item { Layout.fillHeight: true }
                HdText { renderType: Text.NativeRendering; text: ((card.lowerLimit + card.upperLimit) / 2).toLocaleString(Qt.locale(), 'f', 0); color: "#697589"; font.pixelSize: 11 }
                Item { Layout.fillHeight: true }
                HdText { renderType: Text.NativeRendering; text: card.lowerLimit.toLocaleString(Qt.locale(), 'f', 0); color: "#697589"; font.pixelSize: 11 }
            }
            Canvas {
                id: plot
                objectName: card.objectName + "Plot"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Repeater {
                    model: [card.cursorA, card.cursorB]
                    delegate: Rectangle {
                        required property int modelData
                        required property int index
                        visible: card.paused && modelData >= 0
                        x: modelData * (plot.width - 1) / (card.windowSamples - 1)
                        width: 1
                        height: plot.height
                        color: index === 0 ? "#e58a18" : "#d33b72"
                        HdText {
                            x: parent.x > plot.width - 25 ? -18 : 4
                            text: index === 0 ? "A" : "B"
                            color: parent.color
                            font.pixelSize: 12
                        }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: card.paused && card.samples.length > 0
                    preventStealing: true
                    cursorShape: Qt.CrossCursor
                    onPressed: mouse => card.placeCursor(mouse.x, width)
                    onPositionChanged: mouse => { if (pressed) card.moveCursor(mouse.x, width) }
                }
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onPaint: {
                    let ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.strokeStyle = "#edf0f5"
                    ctx.lineWidth = 1
                    ctx.beginPath()
                    for (let i = 0; i <= 10; ++i) {
                        let x = i * width / 10
                        ctx.moveTo(x, 0); ctx.lineTo(x, height)
                    }
                    for (let j = 0; j <= 4; ++j) {
                        let y = j * height / 4
                        ctx.moveTo(0, y); ctx.lineTo(width, y)
                    }
                    ctx.stroke()
                    let values = card.samples.slice(-card.windowSamples)
                    if (values.length < 2) return
                    ctx.strokeStyle = card.accent
                    ctx.lineWidth = 1.6
                    ctx.lineJoin = "round"
                    ctx.beginPath()
                    // Keep the selected time scale fixed while history fills.
                    let offset = card.windowSamples - values.length
                    for (let n = 0; n < values.length; ++n) {
                        let px = (offset + n) * width / (card.windowSamples - 1)
                        let py = (card.upperLimit - values[n]) / (card.upperLimit - card.lowerLimit) * height
                        if (n === 0) ctx.moveTo(px, py)
                        else ctx.lineTo(px, py)
                    }
                    ctx.stroke()
                }
            }
        }
        HdText {
            objectName: card.objectName + "Measurement"
            visible: card.paused
            Layout.fillWidth: true
            color: "#25334c"
            font.pixelSize: 12
            text: card.cursorA < 0 ? "点击波形设置 A，再点击设置 B；拖动光标测量时间"
                  : card.cursorB < 0 ? "A = " + ((card.cursorA - (card.windowSamples - 1)) * 2).toFixed(0) + " ms · 再点击设置 B"
                  : "A = " + ((card.cursorA - (card.windowSamples - 1)) * 2).toFixed(0) + " ms    B = " + ((card.cursorB - (card.windowSamples - 1)) * 2).toFixed(0)
                    + " ms    Δt = " + card.deltaMs.toFixed(0) + " ms（" + (card.deltaMs / 1000).toFixed(3) + " s）· 可拖动光标"
        }
        RowLayout {
            Layout.fillWidth: true
            HdText { renderType: Text.NativeRendering; text: "−" + (card.windowSamples / 500) + " s"; color: "#697589"; font.pixelSize: 11 }
            Item { Layout.fillWidth: true }
            HdText { renderType: Text.NativeRendering; text: card.independentAxis ? "独立纵轴 · 自动 Fit" : (card.autoFit ? "共享纵轴 · 自动 Fit" : "共享纵轴 · 手动范围"); color: "#697589"; font.pixelSize: 11 }
            Item { Layout.fillWidth: true }
            HdText { renderType: Text.NativeRendering; text: "现在"; color: "#697589"; font.pixelSize: 11 }
        }
    }
    onWindowSamplesChanged: { cursorA = -1; cursorB = -1; plot.requestPaint() }
    onSamplesChanged: plot.requestPaint()
    onLowerLimitChanged: plot.requestPaint()
    onUpperLimitChanged: plot.requestPaint()
}
