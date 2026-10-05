import AppKit
import SwiftUI

/// Shared desktop roles. Keep action fills separate from text links for contrast.
enum Palette {
    static let accent = Color(red: 0.30, green: 0.32, blue: 0.76)
    static let link = adaptive(0x474CB6, 0xB8BAFF)
    static let canvas = adaptive(0xF8F8FA, 0x14151A)
    static let surface = adaptive(0xFFFFFF, 0x191A1C)
    static let sidebar = adaptive(0xF0F1F5, 0x191A20)
    static let text = adaptive(0x24272D, 0xF0F1F4)
    static let secondary = adaptive(0x595E69, 0xB3B9C5)
    static let line = adaptive(0xDDDFE2, 0x303237)
    static let selection = adaptive(0xE5E6F8, 0x30314B)
    static let warning = adaptive(0x805200, 0xF2C570)

    private static func adaptive(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let value = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            return NSColor(srgbRed: CGFloat((value >> 16) & 255) / 255,
                           green: CGFloat((value >> 8) & 255) / 255,
                           blue: CGFloat(value & 255) / 255, alpha: 1)
        })
    }
}

enum StackType {
    static let title = Font.system(size: 24, weight: .semibold)
    static let heading = Font.system(size: 16, weight: .semibold)
    static let body = Font.system(size: 14)
    static let detail = Font.system(size: 13)
    static let caption = Font.system(size: 12)
}

struct StackPageHeading: View {
    let title: String
    let detail: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(StackType.title).foregroundStyle(Palette.text)
                .accessibilityAddTraits(.isHeader)
            if !detail.isEmpty {
                Text(detail).font(StackType.body).foregroundStyle(Palette.secondary)
                    .lineSpacing(4).fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: 640, alignment: .leading)
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct StackSearchField: View {
    let title: String
    @Binding var text: String
    @FocusState private var focused: Bool
    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass").foregroundStyle(Palette.secondary).accessibilityHidden(true)
            TextField(title, text: $text).textFieldStyle(.plain).focused($focused)
                .accessibilityLabel(title)
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill").frame(width: 24, height: 24)
                }.buttonStyle(.borderless).help("Clear search").accessibilityLabel("Clear search")
            }
        }
        .font(StackType.body).padding(.horizontal, 12).frame(minHeight: 38)
        .background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(focused ? Palette.link : Palette.line, lineWidth: focused ? 2 : 1))
    }
}

struct StackField: View {
    let title: String
    var prompt = ""
    @Binding var text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(StackType.detail.weight(.medium))
            TextField(title, text: $text, prompt: Text(prompt)).textFieldStyle(.roundedBorder)
                .accessibilityLabel(title)
        }
    }
}

struct StackIconButton: View {
    let title: String
    let symbol: String
    var action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 14, weight: .medium))
                .frame(width: 32, height: 32).contentShape(Rectangle())
        }.buttonStyle(.borderless).foregroundStyle(Palette.secondary)
            .help(title).accessibilityLabel(title)
    }
}


/// Keel-style floating glass: backdrop first, then tint, then sharp content.
/// AppKit owns the blur kernel; no private filter APIs or content snapshots.
struct StackFrostedSurface: View {
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency

    var body: some View {
        Group {
            if reduceTransparency {
                Palette.surface
            } else {
                StackBackdropBlur()
                    .overlay {
                        if colorScheme == .dark {
                            Color(white: 0.21).opacity(0.34)
                        } else {
                            Palette.surface.opacity(0.85)
                        }
                    }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

private struct StackBackdropBlur: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.blendingMode = .withinWindow
        view.material = .hudWindow
        view.state = .active
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {}
}

/// Compact section hierarchy inspired by Designeer's indexed catalogue.
struct StackSectionHeading: View {
    let number: String
    let title: String
    let detail: String
    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(number).font(.system(size: 11, design: .monospaced)).foregroundStyle(Palette.secondary)
                .accessibilityHidden(true)
            Text(title).font(StackType.heading).accessibilityAddTraits(.isHeader)
            if !detail.isEmpty {
                Text(detail).font(StackType.detail).foregroundStyle(Palette.secondary)
            }
        }.padding(.top, 8)
    }
}

/// Quiet, consistent shortcut metadata without competing with the action label.
struct StackKeyboardBadge: View {
    let keys: String
    var body: some View {
        Text(keys).font(.system(size: 11, weight: .medium, design: .monospaced))
            .foregroundStyle(Palette.secondary).padding(.horizontal, 5).padding(.vertical, 2)
            .background(Palette.surface, in: RoundedRectangle(cornerRadius: 4))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Palette.line, lineWidth: 1))
            .accessibilityHidden(true)
    }
}
