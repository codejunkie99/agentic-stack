import AppKit
import SwiftUI

/// Focus only when the picker mounts or explicitly asks; result refreshes never reclaim it.
struct NativeSpotlightField: NSViewRepresentable {
    @Binding var text: String
    let placeholder: String
    let accessibilityName: String
    let focusRequest: Int
    let onSubmit: () -> Void
    let onMove: (Int) -> Void
    let onEscape: () -> Void
    var canFocus: () -> Bool = { true }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> SpotlightNativeTextField {
        let field = SpotlightNativeTextField()
        field.isEditable = true
        field.isSelectable = true
        field.isBezeled = false
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = .default
        field.font = .systemFont(ofSize: 18)
        field.textColor = .labelColor
        field.cell?.usesSingleLineMode = true
        field.lineBreakMode = .byTruncatingTail
        field.setContentHuggingPriority(.defaultLow, for: .horizontal)
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        field.delegate = context.coordinator
        updateNSView(field, context: context)
        return field
    }

    func updateNSView(_ field: SpotlightNativeTextField, context: Context) {
        context.coordinator.parent = self
        field.canFocus = canFocus
        field.placeholderAttributedString = NSAttributedString(string: placeholder, attributes: [
            .foregroundColor: NSColor(Palette.secondary), .font: NSFont.systemFont(ofSize: 18)
        ])
        field.setAccessibilityLabel(accessibilityName)
        if field.stringValue != text {
            field.stringValue = text
            if let editor = field.currentEditor() as? NSTextView {
                editor.string = text
                editor.setSelectedRange(NSRange(location: text.utf16.count, length: 0))
            }
        }
        field.requestFocus(focusRequest)
    }

    static func dismantleNSView(_ field: SpotlightNativeTextField, coordinator: Coordinator) {
        field.cancelFocusRequest()
    }

    final class Coordinator: NSObject, NSTextFieldDelegate {
        var parent: NativeSpotlightField
        init(_ parent: NativeSpotlightField) { self.parent = parent }
        func controlTextDidChange(_ notification: Notification) {
            guard let field = notification.object as? NSTextField else { return }
            parent.text = field.stringValue
        }
        func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
            switch selector {
            case #selector(NSResponder.insertNewline(_:)): parent.onSubmit()
            case #selector(NSResponder.moveDown(_:)): parent.onMove(1)
            case #selector(NSResponder.moveUp(_:)): parent.onMove(-1)
            case #selector(NSResponder.cancelOperation(_:)): parent.onEscape()
            default: return false
            }
            return true
        }
    }
}

final class SpotlightNativeTextField: NSTextField {
    var canFocus: () -> Bool = { true }
    private var focusToken: Int?
    private var pendingFocus = false
    private var scheduledFocus = false

    func requestFocus(_ token: Int) {
        guard token != focusToken else { return }
        focusToken = token
        pendingFocus = true
        scheduleFocus()
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        scheduleFocus()
    }

    func cancelFocusRequest() {
        pendingFocus = false
    }

    private func takeFocus() -> Bool {
        guard pendingFocus, canFocus(), let window else { return false }
        guard window.makeFirstResponder(self) else { return false }
        pendingFocus = false
        (currentEditor() as? NSTextView)?.setSelectedRange(NSRange(location: stringValue.utf16.count, length: 0))
        return true
    }

    private func scheduleFocus() {
        guard pendingFocus, canFocus(), window != nil else { return }
        // Once attached, accept the next key event without another main-queue turn.
        if takeFocus() { return }
        guard !scheduledFocus else { return }
        scheduledFocus = true
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.scheduledFocus = false
            _ = self.takeFocus()
        }
    }
}
