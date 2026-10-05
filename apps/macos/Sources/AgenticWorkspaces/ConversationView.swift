import AppKit
import SwiftUI

enum ConversationPresentation { case full, messages, composer }

struct ConversationView: View {
    @Bindable var model: AppModel
    var presentation = ConversationPresentation.full
    @State private var mode = "read-only"
    @State private var follow = true
    @State private var showingOptions = false
    @State private var attachmentDraftKey = ""
    @State private var filterDraftKey = ""
    @State private var filterTargetKey = ""
    @FocusState private var inputFocused: Bool

    private var agentName: String { model.conversationAgentName }
    private var access: String { model.conversation?.mode ?? model.selectedProfile?.mode ?? mode }
    private var chosenModel: String { model.conversationModelSelection.model }
    private var chosenEffort: String { model.conversationModelSelection.effort }
    private var messages: [AgentRun] { model.conversationRuns }
    private var active: AgentRun? { messages.last(where: \.isActive) }
    private var referenceMention: (range: Range<String.Index>, agent: String, query: String)? {
        let text = draft.wrappedValue
        guard let at = text.lastIndex(of: "@"),
              at == text.startIndex || text[text.index(before: at)].isWhitespace else { return nil }
        let tail = String(text[text.index(after: at)...])
        guard !tail.contains("\n"), tail.count <= 300 else { return nil }
        let value = tail.trimmingCharacters(in: .whitespaces)
        let normalized = value.lowercased()
        let aliases = [("claude code", "claude-code"), ("open code", "opencode"), ("opencode", "opencode"),
                       ("claude", "claude-code"), ("codex", "codex"), ("cursor", "cursor")]
        for (label, agent) in aliases where normalized == label || normalized.hasPrefix(label + " ") {
            let query = value.count == label.count ? "" : String(value.dropFirst(label.count)).trimmingCharacters(in: .whitespaces)
            return (at..<text.endIndex, agent, query)
        }
        return (at..<text.endIndex, "", value)
    }
    private var referenceTrigger: String { model.conversationDraftKey + "|" + draft.wrappedValue }
    private var referenceOccurrence: String? {
        referenceMention.map { String(draft.wrappedValue[...$0.range.lowerBound]) }
    }
    private var referenceContext: String {
        guard let mention = referenceMention else { return String(draft.wrappedValue.suffix(600)) }
        let value = String(draft.wrappedValue[..<mention.range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        return String(value.suffix(600))
    }
    private var draft: Binding<String> {
        Binding(get: { model.conversationDrafts[model.conversationDraftKey] ?? "" },
                set: { model.conversationDrafts[model.conversationDraftKey] = $0 })
    }

    var body: some View {
        VStack(spacing: 0) {
            if presentation != .composer {
            HStack(spacing: 12) {
                agentIcon
                VStack(alignment: .leading, spacing: 3) {
                    Text(agentName).font(.system(size: 14, weight: .semibold))
                    Text(model.conversation?.title ?? model.selectedProfile?.role ?? "New conversation").font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(1)
                }
                Spacer()
                if model.accounts.contains(where: { $0.id == model.selectedAgent && $0.signedIn }) {
                    Label("Connected", systemImage: "circle.fill").font(.system(size: 12)).foregroundStyle(Palette.secondary)
                }
                if let profile = model.selectedProfile {
                    Button("Edit agent", systemImage: "pencil") { model.editAgent(profile) }.labelStyle(.iconOnly).buttonStyle(.plain).help("Edit agent")
                }
                Toggle("Follow output", isOn: $follow).toggleStyle(.checkbox).font(StackType.caption)
                Button("New work", systemImage: "square.and.pencil") { model.newConversation() }
                    .labelStyle(.iconOnly).buttonStyle(.plain).help("New work · ⌘N")
            }.padding(.horizontal, 24).frame(height: 54)
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 28) {
                        if messages.isEmpty { welcome }
                        ForEach(messages) { run in exchange(run) }
                        Color.clear.frame(height: 1).id("conversation-end")
                    }.padding(.horizontal, 24).padding(.vertical, 28)
                        .frame(maxWidth: 840).frame(maxWidth: .infinity)
                }
                .onChange(of: messages.last?.liveOutput) { _, _ in if follow { proxy.scrollTo("conversation-end", anchor: .bottom) } }
                .onChange(of: messages.last?.status) { _, _ in if follow { proxy.scrollTo("conversation-end", anchor: .bottom) } }
                .onChange(of: messages.count, initial: true) { _, _ in if follow { proxy.scrollTo("conversation-end", anchor: .bottom) } }
                .onChange(of: model.selectedConversationID) { _, _ in
                    follow = true; proxy.scrollTo("conversation-end", anchor: .bottom)
                }
            }
            }
            if presentation != .messages {
            composer.padding(.horizontal, 20).padding(.bottom, 18).padding(.top, 8)
                .frame(maxWidth: 960).frame(maxWidth: .infinity)
            }
        }.onChange(of: model.conversationDraftKey) { _, _ in mode = "read-only" }
        .onChange(of: referenceTrigger, initial: true) { _, _ in
            guard presentation != .messages else { return }
            guard let occurrence = referenceOccurrence else {
                model.dismissedConversationAttachments[model.conversationDraftKey] = nil
                return
            }
            guard !model.isSearchPresented,
                  model.dismissedConversationAttachments[model.conversationDraftKey] != occurrence else { return }
            openAttachmentPicker()
        }
        .onChange(of: model.conversationAttachmentRequest?.id) { old, new in
            guard presentation != .messages, old != nil, new == nil, attachmentDraftKey == model.conversationDraftKey else { return }
            let generation = model.searchFocusGeneration
            Task { @MainActor in
                await Task.yield()
                guard generation == model.searchFocusGeneration, !model.isSearchPresented,
                      attachmentDraftKey == model.conversationDraftKey else { return }
                inputFocused = true
            }
        }
        .onChange(of: model.searchFocusGeneration) { _, _ in
            if model.isSearchPresented { inputFocused = false }
        }
        .onChange(of: model.knowledgeFilterRequest?.id) { old, new in
            guard presentation != .messages else { return }
            if new != nil {
                filterDraftKey = model.conversationDraftKey; filterTargetKey = model.handoverPreviewKey
                return
            }
            guard old != nil, !model.graphFullPage, [.graph, .chat].contains(model.section) else { return }
            let generation = model.searchFocusGeneration, draftKey = filterDraftKey, targetKey = filterTargetKey
            Task { @MainActor in
                await Task.yield()
                guard generation == model.searchFocusGeneration, !model.isSearchPresented,
                      draftKey == model.conversationDraftKey, targetKey == model.handoverPreviewKey,
                      !model.graphFullPage, [.graph, .chat].contains(model.section) else { return }
                inputFocused = true
            }
        }

    }

    private var agentIcon: some View {
        Image(systemName: model.selectedProfileID != nil ? "person.crop.square" : model.selectedAgent == "codex" ? "terminal" : "sparkle")
            .font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.link)
            .frame(width: 30, height: 30).background(Palette.accent.opacity(0.1), in: RoundedRectangle(cornerRadius: 9))
    }

    private var welcome: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(model.currentWork.map { "Continue \($0.title)" } ?? "What would you like to work on?").font(.system(size: 23, weight: .medium))
            Text(model.currentWork?.objective ?? "Talk to \(agentName) about \(model.selected?.name ?? "this project"). Continue here as the work develops.")
                .font(StackType.detail).foregroundStyle(Palette.secondary)
            HStack(spacing: 16) {
                Button("Explore this project") { draft.wrappedValue = "Explain how this project is organized and suggest a useful next step."; inputFocused = true }
                Button("Review changes") { draft.wrappedValue = "Review the current changes for bugs and missing checks. Explain your findings before changing files."; inputFocused = true }
            }.buttonStyle(.bordered).font(StackType.detail)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(.top, 32).padding(.bottom, 24)
    }

    private func exchange(_ run: AgentRun) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            HStack {
                Spacer(minLength: 40)
                Text(run.task).font(.system(size: 13)).lineSpacing(4).textSelection(.enabled)
                    .padding(.horizontal, 14).padding(.vertical, 11)
                    .background(Palette.accent.opacity(0.16), in: RoundedRectangle(cornerRadius: 12))
                    .frame(maxWidth: 570, alignment: .trailing)
            }
            HStack(alignment: .top, spacing: 12) {
                agentIcon
                VStack(alignment: .leading, spacing: 11) {
                    HStack {
                        Text(agentName).font(StackType.caption.weight(.medium)).foregroundStyle(Palette.secondary)
                        if run.isActive {
                            Text(run.statusLabel).font(StackType.caption).foregroundStyle(Palette.secondary)
                            if let start = run.startedDate { Text(start, style: .timer).font(StackType.caption).monospacedDigit().foregroundStyle(.tertiary) }
                        }
                    }
                    let text = run.isActive ? (run.liveOutput ?? "") : (run.output.isEmpty ? run.liveOutput ?? "" : run.output)
                    if !text.isEmpty {
                        Text((try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(text))
                            .font(.system(size: 13)).lineSpacing(5).textSelection(.enabled)
                    } else if run.isActive {
                        ProgressView("Waiting for \(agentName)…").controlSize(.small)
                    }
                    if let activity = run.activity, !activity.isEmpty {
                        if run.isActive, let item = activity.last {
                            Label(item.title + " · " + item.status, systemImage: item.status == "running" ? "circle.dotted" : "checkmark.circle")
                                .font(StackType.caption).foregroundStyle(Palette.secondary)
                        } else {
                            DisclosureGroup("\(activity.count) activity updates") {
                                ForEach(activity) { item in
                                    HStack { Text(item.title); Spacer(); Text(item.status.capitalized).foregroundStyle(Palette.secondary) }
                                        .font(StackType.caption).padding(.vertical, 3)
                                }
                            }.font(StackType.caption).foregroundStyle(Palette.secondary)
                        }
                    }
                    if !run.error.isEmpty { Text(run.error).font(StackType.detail).foregroundStyle(.red).textSelection(.enabled) }
                    if !run.isActive && !["completed", "needs_review"].contains(run.status) {
                        Text(run.statusLabel + " · any text above is partial output").font(StackType.caption).foregroundStyle(Palette.secondary)
                        Button("Edit and retry") { draft.wrappedValue = run.task; inputFocused = true }
                            .buttonStyle(.plain).font(StackType.caption).foregroundStyle(Palette.link)
                            .disabled(active != nil || !draft.wrappedValue.isEmpty)
                            .help(draft.wrappedValue.isEmpty ? "Restore this message to the composer" : "Keep or clear your current draft first")
                    }
                    Text(run.modelSummary)
                        .font(StackType.caption).foregroundStyle(.tertiary).textSelection(.enabled)
                    if let refs = run.memoryRefs, !refs.isEmpty {
                        DisclosureGroup("\(refs.count) memory references") {
                            ForEach(refs) { ref in
                                Text(ref.title).font(StackType.caption.weight(.medium))
                                Text(ref.origins.map { "\(userFacingPath($0.path)):\($0.line)" }.joined(separator: "\n")).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                            }
                        }.font(StackType.caption)
                    }
                    if let refs = run.conversationRefs, !refs.isEmpty {
                        DisclosureGroup("\(refs.count) attached conversation\(refs.count == 1 ? "" : "s")") {
                            ForEach(refs) { ref in
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(ref.agentName + " · " + ref.title).font(StackType.caption.weight(.medium))
                                    Text(userFacingPath(ref.origin)).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                                }.padding(.vertical, 2)
                            }
                        }.font(StackType.caption)
                    }
                    if let attachments = run.attachments, !attachments.isEmpty {
                        DisclosureGroup("\(attachments.count) attached file\(attachments.count == 1 ? "" : "s")") {
                            ForEach(attachments) { attachment in
                                HStack(spacing: 7) {
                                    Image(systemName: attachmentIcon(attachment.kind)).foregroundStyle(Palette.secondary)
                                    Text(attachment.name).font(StackType.caption.weight(.medium)).lineLimit(1)
                                    Spacer()
                                    Text(ByteCountFormatter.string(fromByteCount: Int64(attachment.size), countStyle: .file))
                                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                                }.padding(.vertical, 2)
                            }
                        }.font(StackType.caption)
                    }
                    if !run.isActive && !run.output.isEmpty {
                        HStack(spacing: 16) {
                            Button("View task") { model.focusedRunID = run.id; model.section = .runs }
                            Button("Save reference") {
                                Task { if await model.perform("run.saveSource", ["id": run.id]) { model.section = .references } }
                            }.disabled(model.busy || !["completed", "needs_review"].contains(run.status))
                        }.buttonStyle(.plain).font(StackType.caption).foregroundStyle(Palette.secondary)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 9) {
            if model.busy || model.preparingContext {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.mini)
                    Text(model.preparingContext ? "Finding relevant context…" : "Preparing your request…").font(StackType.caption).foregroundStyle(Palette.secondary)
                }
            }
            if model.runs.contains(where: \.isActive) && active == nil {
                HStack {
                    Text("Another task is running in this project.").font(StackType.caption).foregroundStyle(Palette.secondary)
                    Button("View task") { model.section = .runs }.buttonStyle(.plain).font(StackType.caption)
                }
            }
            if model.selected?.provider == "box" {
                Text("For Box Cloud, start a bounded run from Tasks. Conversations use agents on this Mac or your connected server.").font(StackType.caption).foregroundStyle(Palette.secondary)
            }
            VStack(alignment: .leading, spacing: 10) {
                if !model.selectedConversationReferences.isEmpty || !model.selectedConversationFiles.isEmpty {
                    ScrollView(.horizontal) {
                        HStack(spacing: 7) {
                            ForEach(model.selectedConversationReferences) { reference in
                                attachedReferenceChip(reference)
                            }
                            ForEach(model.selectedConversationFiles) { attachment in
                                attachedFileChip(attachment)
                            }
                        }
                    }.scrollIndicators(.hidden)
                }
                ZStack(alignment: .topLeading) {
                    if draft.wrappedValue.isEmpty { Text(model.conversation == nil ? "Describe what you want to work on…" : "Continue with \(agentName)…").foregroundStyle(Palette.secondary).padding(.horizontal, 5).padding(.top, 8).allowsHitTesting(false) }
                    TextEditor(text: draft).scrollContentBackground(.hidden).scrollIndicators(.hidden).frame(minHeight: 72, maxHeight: 120).focused($inputFocused)
                        .disabled(model.isSearchPresented)
                        .accessibilityLabel("Message " + agentName)

                }.font(StackType.body)
                HStack(spacing: 12) {
                    Button { openAttachmentPicker() } label: { Image(systemName: "at").frame(width: 28, height: 28) }
                        .buttonStyle(.plain).help("Attach a conversation · type @")
                        .accessibilityLabel("Attach conversation")
                        .disabled(model.busy || model.selectedConversationReferences.count >= 5)
                    Button { openFilePicker() } label: { Image(systemName: "paperclip").frame(width: 28, height: 28) }
                        .buttonStyle(.plain).help("Attach images, PDFs, audio, video, text, or code")
                        .accessibilityLabel("Attach files")
                        .disabled(model.busy || model.selectedConversationFiles.count >= 8)
                    Button { showingOptions.toggle() } label: { Image(systemName: "slider.horizontal.3").frame(width: 28, height: 28) }
                        .buttonStyle(.borderless).help("Conversation options").accessibilityLabel("Conversation options")
                        .popover(isPresented: $showingOptions) {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("Conversation options").font(StackType.heading)
                                Picker("Access", selection: Binding(get: { access }, set: { mode = $0 })) {
                                    Text("Read only").tag("read-only")
                                    Text("Edit project files").tag("workspace-write")
                                }.disabled(model.conversation != nil || model.selectedProfile != nil)
                                Text("Agent instructions and file access stay fixed for this conversation. Change the next message’s model using the model button beside the composer.").font(StackType.caption).foregroundStyle(Palette.secondary)
                                ContextOptionsView(model: model)
                            }.padding(20).frame(width: 330)
                        }
                    Menu {
                        if model.conversation == nil {
                            Button("Codex") { model.selectedAgent = "codex"; model.selectedProfileID = nil }
                            Button("Claude Code") { model.selectedAgent = "claude-code"; model.selectedProfileID = nil }
                            if !model.profiles.isEmpty { Divider() }
                            ForEach(model.profiles) { profile in
                                Button(profile.name) { model.selectedAgent = profile.runner; model.selectedProfileID = profile.id }
                            }
                        } else if let work = model.currentWork {
                            Button("Continue with Codex") { Task { await model.continueWork(work, agent: "codex") } }
                            Button("Continue with Claude Code") { Task { await model.continueWork(work, agent: "claude-code") } }
                        }
                        Divider()
                        Button("Create custom agent…") { model.editAgent() }
                    } label: { Text(agentName).lineLimit(1) }
                        .menuStyle(.borderlessButton).frame(maxWidth: 130, alignment: .leading).font(StackType.caption)
                        .disabled(model.busy).help("Choose an agent or continue this work in a fresh session")
                    let modelKey = model.conversationDraftKey
                    InlineModelPicker(runner: model.selectedAgent, choices: model.availableModels,
                        selection: model.conversationModelSelection, task: draft.wrappedValue,
                        attachmentKinds: model.selectedConversationFiles.map(\.kind), onSelect: { selection in
                            try await model.configureConversationModel(selection, key: modelKey)
                        }, recommend: { task, routing, attachmentKinds in
                            try await model.recommendModel(runner: model.selectedAgent, task: task, routing: routing,
                                                           attachmentKinds: attachmentKinds)
                        }, refresh: { await model.loadModels() },
                        catalogWarning: model.modelsError ?? model.modelCatalogWarning)
                        .id(modelKey)
                        .disabled(model.busy)
                    Button {
                        model.focusedMemory = nil; model.focusedContextReference = nil; model.contextInspectorVisible.toggle()
                    } label: {
                        Label(model.contextOptions.mode == "off" ? "Context off" : "Context", systemImage: "brain")
                    }.buttonStyle(.plain).font(StackType.caption).foregroundStyle(Palette.secondary)
                        .help("Inspect selected context and sources")
                    Spacer(minLength: 6)
                    if let active {
                        Button("Stop", systemImage: "stop.fill") { Task { await model.cancel(active) } }.disabled(model.busy)
                    } else {
                        Button { Task { await model.sendMessage(draft.wrappedValue, mode: access, modelID: chosenModel, effort: chosenEffort, useMemory: model.contextOptions.mode != "off") } } label: {
                            Image(systemName: "arrow.up").font(.system(size: 14, weight: .semibold)).frame(width: 21, height: 24)
                        }.buttonStyle(.borderedProminent).tint(Palette.accent).clipShape(Circle()).keyboardShortcut(.return, modifiers: .command)
                            .help("Send message · ⌘Return").accessibilityLabel("Send message")
                            .disabled(model.conversationAttachmentRequest != nil || model.showingCommandPalette || model.preparingContext || (draft.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && model.selectedConversationFiles.isEmpty) || model.busy || model.runs.contains(where: \.isActive) || model.selected?.provider == "box")
                    }
                }
            }.padding(12).background(Palette.surface, in: RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Palette.line))
        }
    }

    private func attachedReferenceChip(_ reference: ConversationReference) -> some View {
        let label = reference.agentName + " · " + reference.title
        return HStack(spacing: 6) {
            Image(systemName: "bubble.left.fill").font(.system(size: 12))
            Text(label).lineLimit(1)
            Button {
                model.removeConversationReference(reference)
            } label: { Image(systemName: "xmark").font(.system(size: 8, weight: .bold)) }
                .buttonStyle(.plain).accessibilityLabel("Remove " + reference.title)
        }
        .font(StackType.caption).padding(.horizontal, 9).padding(.vertical, 6)
        .background(Palette.accent.opacity(0.11), in: Capsule())
    }

    private func attachedFileChip(_ attachment: ConversationFileAttachment) -> some View {
        HStack(spacing: 6) {
            Image(systemName: attachmentIcon(attachment.kind)).font(.system(size: 12))
            VStack(alignment: .leading, spacing: 1) {
                Text(attachment.name).lineLimit(1)
                Text(ByteCountFormatter.string(fromByteCount: Int64(attachment.size), countStyle: .file))
                    .font(.system(size: 12)).foregroundStyle(Palette.secondary)
            }
            Button {
                model.removeConversationFile(attachment)
            } label: { Image(systemName: "xmark").font(.system(size: 8, weight: .bold)) }
                .buttonStyle(.plain).accessibilityLabel("Remove " + attachment.name)
        }
        .font(StackType.caption).padding(.horizontal, 9).padding(.vertical, 5)
        .background(Palette.line.opacity(0.55), in: Capsule())
    }

    private func attachmentIcon(_ kind: String) -> String {
        switch kind {
        case "image": return "photo"
        case "audio": return "waveform"
        case "video": return "film"
        case "pdf": return "doc.richtext"
        default: return "doc.text"
        }
    }

    private func openFilePicker() {
        let panel = NSOpenPanel()
        panel.title = "Attach files for the agent"
        panel.prompt = "Attach"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = true
        panel.begin { response in
            guard response == .OK else { return }
            Task { @MainActor in model.attachConversationFiles(panel.urls) }
        }
    }

    private func openAttachmentPicker() {
        attachmentDraftKey = model.conversationDraftKey
        let mention = referenceMention
        model.openConversationAttachment(query: mention?.query ?? "", agent: mention?.agent ?? "",
            context: referenceContext,
            mentionOffset: mention.map { draft.wrappedValue.distance(from: draft.wrappedValue.startIndex, to: $0.range.lowerBound) })
        if model.conversationAttachmentRequest != nil { inputFocused = false }
    }
}
