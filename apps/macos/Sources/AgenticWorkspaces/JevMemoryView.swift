import AppKit
import SwiftUI

private struct JevClaim: Decodable, Identifiable {
    let id: String
    let body: String
    let kind: String
    let status: String
    let revision: Int
    let evidenceIds: [String]
}
private struct JevProposal: Decodable, Identifiable {
    let id: String
    let action: String
    let subjectId: String
    let targetId: String?
    let model: String
    let revision: Int
}
private struct JevSnapshot: Decodable {
    let claims: [JevClaim]
    let proposals: [JevProposal]
    let providerAvailable: Bool
}
private struct JevEvidence: Decodable {
    let sourceKey: String
    let body: String
    let digest: String
}
private struct JevCursor: Decodable {
    let offset: Int
    let snapshot: String
}
private struct JevReconciliation: Decodable {
    let nextCursor: JevCursor?
    let status: String
    let warning: String
}
private struct JevHistory: Decodable {
    let events: [Event]
    struct Event: Decodable {
        let operation: String
        let createdAt: String
        let payload: Payload
    }
    struct Payload: Decodable {
        let rationale: String?
        let status: String?
        let model: String?
    }
}

private struct JevReview: Identifiable {
    let id: String
    let revision: Int
    let title: String
    let body: String
    let status: String?
    let accept: Bool?
}

struct JevLedgerView: View {
    @Bindable var model: AppModel
    var onForget: ((String, String) -> Void)? = nil
    @State private var reconciliationCursors: [String: JevCursor] = [:]
    @State private var showingImport = false
    @State private var showingSetup = false
    @State private var showingDemo = false
    @State private var snapshot: JevSnapshot?
    @State private var message = ""
    @State private var busy = false
    @State private var generation = 0
    @State private var category = "proposed"
    @State private var search = ""
    @State private var review: JevReview?
    @State private var rationale = ""
    @State private var evidenceText = ""
    @State private var evidenceTitle = "Original evidence"
    @State private var showingEvidence = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Project memory").font(StackType.title)
                    Text("Evidence, decisions, and what changed.").foregroundStyle(Palette.secondary)
                }
                Spacer()
                if busy { ProgressView().controlSize(.small) }
                Button("Memory workspace") { showingDemo = true }.disabled(!model.hostReady)
                Button("Import memories") { showingImport = true }.disabled(busy || !model.hostReady)
                Button("Refresh", systemImage: "arrow.clockwise") { Task { await reload() } }
                    .disabled(busy || !model.hostReady)
            }
            if let snapshot {
                HStack {
                    Label(snapshot.providerAvailable ? "Jev enabled" : "Jev is not configured", systemImage: snapshot.providerAvailable ? "checkmark.circle" : "circle.dashed")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                    Spacer()
                    Button("Provider settings") { showingSetup = true }
                        .disabled(busy || !model.hostReady)
                }
                StackSearchField(title: "Filter decisions, facts, and preferences", text: $search)
                Picker("Project memory status", selection: $category) {
                    Text("Review").tag("proposed")
                    Text("Accepted").tag("accepted")
                    Text("Disputed").tag("disputed")
                    Text("History").tag("history")
                }.pickerStyle(.segmented)
                let claims = snapshot.claims.filter { (category == "history" || $0.status == category) && (search.isEmpty || $0.body.localizedCaseInsensitiveContains(search)) }
                if claims.isEmpty {
                    Text("No memories in this view yet.").foregroundStyle(Palette.secondary).padding(.vertical, 16)
                }
                StackSectionHeading(number: "01", title: "Memories", detail: "\(claims.count) shown")
                ForEach(claims) { claim in claimRow(claim, available: snapshot.providerAvailable) }
                if !snapshot.proposals.isEmpty {
                    Divider()
                    StackSectionHeading(number: "02", title: "Suggestions", detail: "\(snapshot.proposals.count) to review")
                    Text("Review the evidence and the effect of each proposed change.").font(StackType.caption).foregroundStyle(Palette.secondary)
                    ForEach(snapshot.proposals) { proposal in proposalRow(proposal, claims: snapshot.claims) }
                }
            }
            if !message.isEmpty { Text(message).font(StackType.detail).textSelection(.enabled) }
        }
        .task(id: model.handoverPreviewKey) {
            snapshot = nil; review = nil; reconciliationCursors = [:]; showingImport = false; showingSetup = false; showingEvidence = false; evidenceText = ""; message = ""
            await reload()
            if model.jevProviderSetupRequested { model.jevProviderSetupRequested = false; showingSetup = true }
        }
        .onChange(of: model.jevProviderSetupRequested) { _, requested in
            if requested { model.jevProviderSetupRequested = false; showingSetup = true }
        }
        .sheet(isPresented: $showingImport, onDismiss: { Task { await reload() } }) {
            JevImportView(model: model, providerAvailable: snapshot?.providerAvailable == true)
        }
        .sheet(isPresented: $showingDemo) { MemoryDemoView(model: model) }
        .sheet(isPresented: $showingSetup, onDismiss: { Task { await reload() } }) {
            JevProviderSettingsView(model: model)
        }
        .sheet(item: $review) { item in
            VStack(alignment: .leading, spacing: 16) {
                Text(item.title).font(StackType.title)
                ScrollView { Text(item.body).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(maxHeight: 240)
                TextField("Reason for this decision", text: $rationale, axis: .vertical).lineLimit(3...5).textFieldStyle(.roundedBorder)
                if !message.isEmpty { Text(message).font(StackType.detail) }
                HStack {
                    Button("Cancel") { review = nil }.disabled(busy)
                    Spacer()
                    Button(item.title) { Task { await apply(item) } }.buttonStyle(.borderedProminent)
                        .disabled(busy || rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !model.hostReady)
                }
            }.padding(24).frame(width: 560).interactiveDismissDisabled(busy)
        }
        .sheet(isPresented: $showingEvidence) {
            VStack(alignment: .leading, spacing: 16) {
                Text(evidenceTitle).font(StackType.title)
                ScrollView { Text(evidenceText).font(.system(.callout, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }
                Button("Done") { showingEvidence = false }
            }.padding(24).frame(width: 640, height: 460)
        }
    }

    private func claimRow(_ claim: JevClaim, available: Bool) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(claim.kind.capitalized).font(StackType.caption).foregroundStyle(Palette.secondary)
                Spacer()
                StatusLabel(title: claim.status.capitalized)
            }
            Text(claim.body).textSelection(.enabled)
            HStack {
                Button("Evidence") { Task { await showEvidence(claim) } }
                Button("Decision history") { Task { await showHistory(claim) } }
                if claim.status == "accepted", let onForget {
                    Button("Forget with Jev…") { onForget(claim.id, claim.body) }
                }
                if !["superseded", "retracted"].contains(claim.status) {
                    if claim.status != "accepted" {
                        Button("Accept…") { choose(JevReview(id: claim.id, revision: claim.revision, title: "Accept memory", body: claim.body, status: "accepted", accept: nil)) }
                    }
                    Button("Retract…") { choose(JevReview(id: claim.id, revision: claim.revision, title: "Retract memory", body: claim.body + "\n\nThe original evidence and history will remain available.", status: "retracted", accept: nil)) }
                    Spacer()
                    Menu("Review with Jev") {
                        Button(reconciliationCursors[claim.id] == nil ? "Find relationships" : "Continue finding relationships") { Task { await evaluate(claim, operation: "reconcile") } }
                        Button("Check continued relevance") { Task { await evaluate(claim, operation: "maintain") } }
                    }.disabled(!available)
                }
            }.disabled(busy || !model.hostReady)
        }.padding(.vertical, 16)
            .overlay(alignment: .bottom) { Divider() }
    }

    private func proposalRow(_ proposal: JevProposal, claims: [JevClaim]) -> some View {
        let subject = claims.first { $0.id == proposal.subjectId }?.body ?? "Memory unavailable"
        let target = claims.first { $0.id == proposal.targetId }?.body ?? ""
        let explanation: String = switch proposal.action {
        case "supersedes": "Applying accepts the first memory and replaces the second. Both sources remain in history."
        case "archive": "Applying retracts this memory from future context. Its evidence and history remain available."
        case "revalidate": "Applying marks this memory disputed and excludes it from automatic context until it is reviewed again."
        default: "Applying records this relationship. It does not accept or merge either memory."
        }
        let body = subject + "\n\n" + proposal.action.uppercased() + "\n\n" + target + "\n\n" + explanation
        return VStack(alignment: .leading, spacing: 12) {
            Text(proposal.action.capitalized).font(StackType.heading)
            Text(subject).textSelection(.enabled)
            if !target.isEmpty { Text(target).foregroundStyle(Palette.secondary).textSelection(.enabled) }
            Text("Suggested by " + proposal.model).font(StackType.caption).foregroundStyle(Palette.secondary)
            HStack {
                Button("Review…") { choose(JevReview(id: proposal.id, revision: proposal.revision, title: "Apply suggestion", body: body, status: nil, accept: true)) }
                Button("Dismiss…") { choose(JevReview(id: proposal.id, revision: proposal.revision, title: "Dismiss suggestion", body: body, status: nil, accept: false)) }
            }.disabled(busy || !model.hostReady)
        }.padding(.vertical, 16)
            .overlay(alignment: .bottom) { Divider() }
    }

    private func choose(_ item: JevReview) { rationale = ""; message = ""; review = item }

    private func reload() async {
        generation += 1
        let request = generation, key = model.handoverPreviewKey
        guard let wid = model.selectedID, model.hostReady else { busy = false; return }
        let host = model.terminalHost
        busy = true
        defer { if generation == request { busy = false } }
        do {
            let result = try await model.terminalCall("memory.ledger.snapshot", ["workspaceId": wid], host: host, as: JevSnapshot.self)
            guard !Task.isCancelled, request == generation, key == model.handoverPreviewKey else { return }
            snapshot = result
        } catch {
            guard request == generation, key == model.handoverPreviewKey else { return }
            message = error.localizedDescription
        }
    }

    private func apply(_ item: JevReview) async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true
        do {
            var params: [String: Any] = ["workspaceId": wid, "id": item.id, "expectedRevision": item.revision, "rationale": rationale]
            if let status = item.status {
                params["status"] = status
                let _ = try await model.terminalCall("memory.ledger.review", params, host: host, as: JevClaim.self)
            } else {
                params["accept"] = item.accept ?? false
                let _ = try await model.terminalCall("memory.proposals.review", params, host: host, as: JevProposal.self)
            }
            guard key == model.handoverPreviewKey else { return }
            review = nil; message = ""; await reload()
        } catch {
            guard key == model.handoverPreviewKey else { return }
            message = error.localizedDescription; busy = false
        }
    }

    private func evaluate(_ claim: JevClaim, operation: String) async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true
        do {
            var params: [String: Any] = ["workspaceId": wid, "claimId": claim.id]
            if operation == "reconcile", let cursor = reconciliationCursors[claim.id] {
                params["cursor"] = ["offset": cursor.offset, "snapshot": cursor.snapshot]
            }
            let result = try await model.terminalCall("memory." + operation, params, host: host, as: JevReconciliation.self)
            guard key == model.handoverPreviewKey else { return }
            if operation == "reconcile" { reconciliationCursors[claim.id] = result.nextCursor }
            message = result.warning.isEmpty ? "Memory review: " + result.status : result.warning
            await reload()
        } catch {
            guard key == model.handoverPreviewKey else { return }
            reconciliationCursors.removeValue(forKey: claim.id)
            message = error.localizedDescription; busy = false
        }
    }

    private func showHistory(_ claim: JevClaim) async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true
        do {
            let history = try await model.terminalCall("memory.ledger.history", ["workspaceId": wid, "id": claim.id], host: host, as: JevHistory.self)
            guard !Task.isCancelled, key == model.handoverPreviewKey else { return }
            evidenceTitle = "Decision history"
            evidenceText = history.events.map { event in
                [event.createdAt, event.operation.replacingOccurrences(of: "_", with: " ").capitalized,
                 event.payload.status, event.payload.rationale, event.payload.model.map { "Model: " + $0 }]
                    .compactMap { $0 }.joined(separator: "\n")
            }.joined(separator: "\n\n——\n\n")
            showingEvidence = true; busy = false
        } catch {
            guard key == model.handoverPreviewKey else { return }
            message = error.localizedDescription; busy = false
        }
    }

    private func showEvidence(_ claim: JevClaim) async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true
        do {
            var passages: [String] = []
            for id in claim.evidenceIds {
                let evidence = try await model.terminalCall("memory.ledger.evidence", ["workspaceId": wid, "id": id], host: host, as: JevEvidence.self)
                guard !Task.isCancelled, key == model.handoverPreviewKey else { return }
                passages.append(evidence.sourceKey + "\n" + evidence.digest + "\n\n" + evidence.body)
            }
            evidenceTitle = "Original evidence"
            evidenceText = passages.joined(separator: "\n\n——\n\n"); showingEvidence = true; busy = false
        } catch {
            guard key == model.handoverPreviewKey else { return }
            message = error.localizedDescription; busy = false
        }
    }
}

struct JevContextDecision: Decodable, Identifiable, Sendable {
    let id: String
    let title: String?
    let body: String
    let source: String?
    let score: Double?
    let confidence: Double?
    let contextAction: String
    let memoryAction: String
    let reason: String?
}
struct JevContextCoverage: Decodable, Sendable {
    let candidateCount: Int?
    let evaluatedCount: Int?
    let omittedCount: Int?
    let exhaustive: Bool?
    let hasMore: Bool?
}
struct JevContextToolDecision: Decodable, Sendable {
    let tool: String
    let action: String
    let confidence: Double?
}
struct JevContextPlan: Decodable, Sendable {
    let planId: String?
    let status: String
    let warning: String?
    let summary: String?
    let model: String?
    let tokenBudget: Int?
    let usedTokens: Int?
    let decisions: [JevContextDecision]?
    let contextText: String?
    let selectedIds: [String]?
    let evictedIds: [String]?
    let applyAvailable: Bool?
    var coverage: JevContextCoverage? = nil
    var toolDecisions: [JevContextToolDecision]? = nil
    var providerCalls: Int? = nil
}
private struct JevContextApplied: Decodable, Sendable {
    let status: String
    let rememberedIds: [String]?
    let forgottenIds: [String]?
}

/// Project-scoped drafts and stable row selection survive leaving this page.
@MainActor @Observable
final class JevMemoryWorkspace {
    var task = ""
    var incoming = ""
    var activeContext = ""
    var intent = "recall"
    var targetIDs: [String] = []
    var targetTitles: [String: String] = [:]
    var sourcesMemory = true
    var sourcesConversations = true
    var budget = 2048
    var page = "recall"
    var focusQuery = false
    var plan: JevContextPlan?
    var selectedID: String?
    var scrollID: String?
    var message = ""
    var busy = false
    var applied = false
    var generation = 0
    var requestSignature = ""
    @ObservationIgnored var request: Task<Void, Never>?

    var signature: String { [task, incoming, activeContext, intent, String(budget), String(sourcesMemory), String(sourcesConversations), targetIDs.sorted().joined(separator: ",")].joined(separator: "\u{1f}") }
    var planIsCurrent: Bool { requestSignature == signature }
    func cancel() {
        generation += 1
        request?.cancel(); request = nil; busy = false
    }
}

struct JevMemoryPage: View {
    @Bindable var model: AppModel
    var fixture: String? = nil
    @State private var workspace: JevMemoryWorkspace?
    private var storageKey: String { model.terminalHost + ":" + (model.selectedID ?? "") }
    var body: some View {
        Group {
            if let workspace { JevMemoryView(model: model, state: workspace, fixture: fixture) }
            else { ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity) }
        }
        .task(id: storageKey) {
            if let existing = model.jevMemoryWorkspaces[storageKey] {
                if model.jevProviderSetupRequested { existing.page = "ledger" }
                workspace = existing
            }
            else {
                let state = JevMemoryWorkspace()
                if model.jevProviderSetupRequested { state.page = "ledger" }
                if let fixture { state.loadFixture(fixture) }
                model.jevMemoryWorkspaces[storageKey] = state; workspace = state
            }
        }
    }
}

struct JevMemoryView: View {
    @Bindable var model: AppModel
    @Bindable var state: JevMemoryWorkspace
    var fixture: String? = nil
    @State private var showingContext = false
    @State private var showingInputs = false
    @State private var showingSource = false
    @State private var narrow = false
    @State private var showingApply = false
    @State private var showingLegacy = false
    @FocusState private var queryFocused: Bool
    @FocusState private var listFocused: Bool
    private var ready: Bool { fixture != nil || model.hostReady }
    private var decisions: [JevContextDecision] { state.plan?.decisions ?? [] }
    private var selected: JevContextDecision? { decisions.first { $0.id == state.selectedID } }

    var body: some View {
        GeometryReader { area in
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    Text("Jev memory").font(StackType.detail.weight(.semibold)).fixedSize()
                    Picker("Memory workspace", selection: $state.page) {
                        Text("Recall & context").tag("recall")
                        Text("Memory ledger").tag("ledger")
                    }.labelsHidden().pickerStyle(.segmented).frame(width: 264)
                    Spacer(minLength: 8)
                    Button("Context", systemImage: "doc.text") { showingInputs.toggle() }.font(StackType.caption)
                        .popover(isPresented: $showingInputs) {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("Context to review").font(StackType.heading)
                                contextInput("Active context", prompt: "Passages already in your context", text: $state.activeContext)
                                contextInput("Incoming passage", prompt: "New evidence to consider or remember", text: $state.incoming)
                            }.padding(16).frame(width: 460)
                        }
                    Menu {
                        Toggle("Project memories", isOn: $state.sourcesMemory)
                        Toggle("Conversation sources", isOn: $state.sourcesConversations)
                        Picker("Token budget", selection: $state.budget) {
                            Text("1,024 tokens").tag(1024); Text("2,048 tokens").tag(2048); Text("4,096 tokens").tag(4096)
                        }
                        Divider()
                        Button("Previous lessons…") { showingLegacy = true }.disabled(fixture != nil)
                    } label: { Label("Sources", systemImage: "slider.horizontal.3").font(StackType.caption) }.fixedSize()
                }.padding(.horizontal, 16).frame(height: 44)
                Divider()
                if state.page == "ledger" && fixture == nil {
                    ScrollView {
                        JevLedgerView(model: model, onForget: { id, body in
                            selectForgetTarget("claim:" + id, title: body)
                            state.task = "Review whether this memory should be forgotten: " + body
                            state.page = "recall"
                        }).padding(16).frame(maxWidth: 800, alignment: .leading).frame(maxWidth: .infinity, alignment: .center)
                    }
                } else {
                    VStack(alignment: .leading, spacing: 0) {
                        input
                        statusStrip
                    }.padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 4)
                    Divider()
                    if area.size.width >= 820 {
                        HStack(spacing: 0) {
                            results.frame(maxWidth: .infinity, maxHeight: .infinity)
                            Divider()
                            inspector.frame(width: min(320, area.size.width * 0.36))
                        }
                    } else {
                        results.frame(maxWidth: .infinity, maxHeight: .infinity)

                    }
                    Divider()
                    footer
                }
            }.background(Palette.canvas)
                .onChange(of: area.size.width < 820, initial: true) { _, compact in
                    narrow = compact
                    if !compact { showingSource = false }
                }
        }
        .onAppear {
            queryFocused = state.focusQuery
            if model.jevProviderSetupRequested { state.page = "ledger" }
        }
        .onChange(of: model.jevProviderSetupRequested) { _, requested in
            if requested { state.page = "ledger" }
        }
        .onDisappear {
            state.focusQuery = queryFocused
            if state.busy { state.message = "Request cancelled when leaving this view. Your draft is preserved." }
            state.cancel()
        }
        .onChange(of: state.signature) { _, _ in
            state.message = ""
            if state.busy { state.cancel(); state.message = "Inputs changed. Run Jev again to review the updated context." }
        }
        .sheet(isPresented: $showingSource) {
            VStack(spacing: 0) {
                HStack { Text("Source details").font(StackType.detail.weight(.semibold)); Spacer(); Button("Done") { showingSource = false }.keyboardShortcut(.cancelAction) }.padding(16)
                Divider()
                inspector
            }.frame(width: DesktopSizing.sheetWidth(460), height: DesktopSizing.sheetHeight(620))
        }
        .sheet(isPresented: $showingContext) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Selected context").font(StackType.heading)
                Text("Exact source passages selected for this request.").font(StackType.detail).foregroundStyle(Palette.secondary)
                ScrollView { Text(state.plan?.contextText ?? "").font(StackType.body).lineSpacing(6).textSelection(.enabled).frame(maxWidth: 736, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading) }
                HStack { Button("Done") { showingContext = false }.keyboardShortcut(.cancelAction); Spacer(); Button("Copy context", systemImage: "doc.on.doc") { copyContext() }.disabled(!state.planIsCurrent) }
            }.padding(24).frame(width: DesktopSizing.sheetWidth(760), height: DesktopSizing.sheetHeight(560))
        }
        .sheet(isPresented: $showingApply) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Apply memory decisions").font(StackType.heading)
                Text("Review each durable change. Context selection alone does not change saved memory.").font(StackType.detail).foregroundStyle(Palette.secondary)
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        ForEach(decisions.filter { $0.memoryAction != "none" }) { decision in
                            VStack(alignment: .leading, spacing: 8) {
                                Label(decision.memoryAction == "forget" ? "Forget memory" : "Remember passage", systemImage: decision.memoryAction == "forget" ? "archivebox" : "tray.and.arrow.down")
                                    .font(StackType.detail.weight(.semibold))
                                Text(decision.body).font(StackType.body).textSelection(.enabled)
                                if let reason = decision.reason { Text(reason).font(StackType.detail).foregroundStyle(Palette.secondary) }
                            }
                            Divider()
                        }
                    }
                }.frame(maxHeight: 320)
                if !state.message.isEmpty { Text(state.message).font(StackType.detail).foregroundStyle(Palette.warning) }
                HStack {
                    Button("Cancel") { showingApply = false }.keyboardShortcut(.cancelAction).disabled(state.busy)
                    Spacer()
                    Button("Apply reviewed decisions") { applyPlan() }.buttonStyle(.borderedProminent)
                        .disabled(state.busy || !state.planIsCurrent || state.applied || !ready)
                }
            }.padding(24).frame(width: DesktopSizing.sheetWidth(600)).interactiveDismissDisabled(state.busy)
        }
        .sheet(isPresented: $showingLegacy) {
            VStack(spacing: 0) {
                HStack { Text("Previous lessons").font(StackType.heading); Spacer(); Button("Done") { showingLegacy = false } }.padding(16)
                Divider(); MemoryManagementView(model: model)
            }.frame(width: DesktopSizing.sheetWidth(860), height: DesktopSizing.sheetHeight(700))
        }
    }

    private var input: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Picker("Memory operation", selection: $state.intent) {
                    Text("Recall").tag("recall"); Text("Add memory").tag("add"); Text("Forget").tag("forget")
                }.labelsHidden().frame(width: 108)
                Divider().frame(height: 20)
                TextField(state.intent == "forget" ? "Which saved memory should be forgotten?" : "What are you working on?", text: $state.task)
                    .textFieldStyle(.plain).font(StackType.body).focused($queryFocused)
                    .accessibilityLabel("Task or memory request").onSubmit { runPlan() }
                Button(state.busy ? "Cancel" : "Ask Jev", systemImage: state.busy ? "xmark" : "arrow.up") {
                    if state.busy { state.cancel(); state.message = "Request cancelled." } else { runPlan() }
                }.buttonStyle(.borderedProminent).fixedSize()
                    .disabled(!state.busy && (!ready || state.task.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (!state.sourcesMemory && !state.sourcesConversations && state.incoming.isEmpty && state.activeContext.isEmpty) || (state.intent == "forget" && state.targetIDs.isEmpty)))
            }.padding(.horizontal, 12).frame(height: 48).background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(queryFocused ? Palette.link : Palette.line, lineWidth: queryFocused ? 2 : 1))
            HStack(spacing: 8) {
                if state.intent == "forget" {
                    Text(state.targetIDs.isEmpty ? "Select an accepted memory as the forget target." : "\(state.targetIDs.count) saved memory target(s)").lineLimit(1)
                    if !state.targetIDs.isEmpty {
                        Menu("Targets") {
                            ForEach(state.targetIDs, id: \.self) { id in
                                Button("Remove: " + (state.targetTitles[id] ?? id)) { state.targetIDs.removeAll { $0 == id }; state.targetTitles.removeValue(forKey: id) }
                            }
                        }.fixedSize()
                    }
                } else {
                    Text([state.sourcesMemory ? "Project memory" : nil, state.sourcesConversations ? "Conversations" : nil].compactMap { $0 }.joined(separator: " · ")).lineLimit(1)
                    if !state.incoming.isEmpty { Text("· Incoming passage").lineLimit(1) }
                }
                Spacer(minLength: 0)
            }.font(StackType.caption).foregroundStyle(Palette.secondary).frame(height: 24)
        }
    }

    private func contextInput(_ title: String, prompt: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(StackType.caption.weight(.medium))
            TextField(prompt, text: text, axis: .vertical).lineLimit(3...5).textFieldStyle(.plain)
                .font(StackType.body).foregroundStyle(Palette.text).padding(8)
                .background(Palette.surface, in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Palette.line, lineWidth: 1))
                .accessibilityLabel(title)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private var statusStrip: some View {
        HStack(spacing: 8) {
            ZStack {
                if state.busy { ProgressView().controlSize(.small) }
                else { Image(systemName: statusSymbol).foregroundStyle(Palette.secondary) }
            }.frame(width: 16, height: 16).accessibilityHidden(true)
            Text(statusText).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(2)
            Spacer(minLength: 8)
            if let used = state.plan?.usedTokens {
                Text("\(used) / \(state.plan?.tokenBudget ?? state.budget) est. tokens").font(.system(size: 11, design: .monospaced)).foregroundStyle(Palette.secondary).fixedSize()
            }
        }.frame(minHeight: 24, maxHeight: 24, alignment: .leading)
    }
    private var statusSymbol: String {
        switch state.plan?.status { case "unavailable": "exclamationmark.circle"; case "abstained": "circle.dashed"; case "partial": "exclamationmark.triangle"; default: "sparkle" }
    }
    private var statusText: String {
        if state.busy { return "Jev is reviewing relevance and context decisions…" }
        if !ready { return "Connect the selected host to use Jev memory." }
        if !state.message.isEmpty { return state.message }
        if state.plan != nil && !state.planIsCurrent { return "Inputs changed · Run Jev again before using this plan." }
        if let plan = state.plan {
            if let warning = plan.warning, !warning.isEmpty { return warning }
            switch plan.status {
            case "unavailable": return "Jev is unavailable. Connect a provider in Memory ledger."
            case "abstained": return "Jev abstained · No context or memory changes selected."
            case "partial": return "Partial review · Inspect coverage before using this context."
            default: return "Reviewed by \(plan.model ?? "Jev") · Memory changes require your review."
            }
        }
        return "Jev selects relevant evidence. Every source and decision stays inspectable."
    }

    private var results: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Relevance & decisions").font(StackType.detail.weight(.semibold)).accessibilityAddTraits(.isHeader)
                Spacer()
                Text("\(decisions.count) sources").font(StackType.caption).foregroundStyle(Palette.secondary)
            }.padding(.horizontal, 16).frame(height: 44)
            if decisions.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Image(systemName: state.plan?.status == "unavailable" ? "network.slash" : "text.magnifyingglass").font(.system(size: 24)).foregroundStyle(Palette.secondary)
                        Text(emptyTitle).font(StackType.heading)
                        Text(emptyDetail).font(StackType.body).lineSpacing(6).foregroundStyle(Palette.secondary)
                    }.frame(maxWidth: 460, alignment: .leading).padding(24).frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(decisions) { decision in decisionRow(decision).id(decision.id) }
                    }.scrollTargetLayout()
                }.scrollPosition(id: $state.scrollID, anchor: .top)
            }
        }.frame(maxHeight: .infinity, alignment: .top)
            .focusable().focused($listFocused).focusEffectDisabled()
            .onKeyPress(.downArrow) { moveSelection(1); return .handled }
            .onKeyPress(.upArrow) { moveSelection(-1); return .handled }
    }
    private func moveSelection(_ offset: Int) {
        guard !decisions.isEmpty else { return }
        let index = decisions.firstIndex { $0.id == state.selectedID } ?? (offset > 0 ? -1 : decisions.count)
        let target = decisions[min(decisions.count - 1, max(0, index + offset))].id
        state.selectedID = target; state.scrollID = target
    }
    private var emptyTitle: String {
        switch state.plan?.status { case "unavailable": "Provider unavailable"; case "abstained": "No change recommended"; default: state.plan == nil ? "Start with the task" : "No relevant sources" }
    }
    private var emptyDetail: String {
        switch state.plan?.status {
        case "unavailable": "Enable Jev in Memory ledger → Provider settings, then retry. Your draft stays here."
        case "abstained": "Jev did not select evidence with enough confidence. Refine the task or supply an exact passage to review."
        default: "Describe the task to recall relevant memories, inspect what stays in context, and review what should be remembered or forgotten."
        }
    }

    private func decisionRow(_ decision: JevContextDecision) -> some View {
        Button { state.selectedID = decision.id; if narrow { showingSource = true } } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: actionSymbol(decision.contextAction)).font(.system(size: 15)).foregroundStyle(Palette.secondary).frame(width: 20, height: 20).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 6) {
                    Text(decision.title?.isEmpty == false ? decision.title! : "Source passage").font(StackType.detail.weight(.medium)).lineLimit(1)
                    HStack(spacing: 8) {
                        Text(actionTitle(decision.contextAction, memory: false)).font(StackType.caption.weight(.medium))
                        if decision.memoryAction != "none" { Text("· " + actionTitle(decision.memoryAction, memory: true)).font(StackType.caption) }
                        if let source = decision.source { Text("· " + source).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(1).truncationMode(.middle) }
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: decision.memoryAction == "forget" ? "archivebox" : "tray.and.arrow.down").font(.system(size: 12)).foregroundStyle(Palette.secondary).frame(width: 16, height: 20).opacity(decision.memoryAction == "none" ? 0 : 1).accessibilityHidden(true)
            }.padding(.horizontal, 16).padding(.vertical, 12).foregroundStyle(Palette.text)
                .background(state.selectedID == decision.id ? Palette.text.opacity(0.06) : Color.clear)
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityAddTraits(state.selectedID == decision.id ? .isSelected : [])
            .accessibilityLabel("\(decision.title ?? "Source passage"). \(actionTitle(decision.contextAction, memory: false)). \(actionTitle(decision.memoryAction, memory: true))")
            .overlay(alignment: .bottom) { Divider().padding(.leading, 48) }
            .overlay(alignment: .leading) { if state.selectedID == decision.id { Rectangle().fill(Palette.link.opacity(0.7)).frame(width: 2) } }
    }

    private var inspector: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("SOURCE INSPECTOR").font(.system(size: 11, weight: .medium)).foregroundStyle(Palette.secondary).accessibilityAddTraits(.isHeader)
                if let selected {
                    Text(selected.title ?? "Source passage").font(StackType.heading).fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 8) {
                        Label(actionTitle(selected.contextAction, memory: false), systemImage: actionSymbol(selected.contextAction)).font(StackType.caption)
                        if let confidence = selected.confidence { Text("\(Int(min(1, max(0, confidence)) * 100))% confidence").font(StackType.caption).foregroundStyle(Palette.secondary) }
                    }
                    if selected.memoryAction != "none" {
                        Label(actionTitle(selected.memoryAction, memory: true), systemImage: selected.memoryAction == "forget" ? "archivebox" : "tray.and.arrow.down").font(StackType.detail)
                    }
                    if let reason = selected.reason, !reason.isEmpty { Text(reason).font(StackType.detail).lineSpacing(4).foregroundStyle(Palette.secondary).textSelection(.enabled) }
                    if selected.id.hasPrefix("claim:") {
                        Button(state.targetIDs.contains(selected.id) ? "Selected as forget target" : "Use as forget target", systemImage: "archivebox") {
                            selectForgetTarget(selected.id, title: selected.title ?? selected.body)
                        }.disabled(state.targetIDs.contains(selected.id) || state.busy)
                    }
                    Divider()
                    Text(selected.body).font(StackType.body).lineSpacing(6).textSelection(.enabled)
                    Divider()
                    if let source = selected.source { Text(source).font(.system(size: 11, design: .monospaced)).foregroundStyle(Palette.secondary).textSelection(.enabled).fixedSize(horizontal: false, vertical: true) }
                    Text("Context decisions affect this request. Remember and forget decisions change saved memory only after review.").font(StackType.caption).lineSpacing(4).foregroundStyle(Palette.secondary)
                } else {
                    Text("Select a source to inspect its evidence and the reason for each decision.").font(StackType.body).lineSpacing(6).foregroundStyle(Palette.secondary)
                }
                if let coverage = state.plan?.coverage {
                    Divider()
                    Text("Bounded source review").font(StackType.caption.weight(.medium)).foregroundStyle(Palette.secondary)
                    Text("\(coverage.evaluatedCount ?? 0) of \(coverage.candidateCount ?? 0) candidates reviewed · \(coverage.omittedCount ?? 0) omitted")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                    Text(coverage.hasMore == true ? "More sources remain beyond this review." : "This review covers a bounded set of source candidates.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                }
                if let tools = state.plan?.toolDecisions, !tools.isEmpty {
                    DisclosureGroup("Tool guidance") {
                        ForEach(tools, id: \.tool) { tool in
                            HStack { Text(tool.tool); Spacer(); Text(tool.action == "inject" ? "Add guidance" : "No change").foregroundStyle(Palette.secondary) }.font(StackType.caption).padding(.top, 8)
                        }
                    }.font(StackType.caption).foregroundStyle(Palette.secondary)
                }
                if let summary = state.plan?.summary, !summary.isEmpty {
                    Divider()
                    DisclosureGroup("Selected evidence summary") {
                        Text(summary).font(StackType.body).lineSpacing(6).textSelection(.enabled).padding(.top, 8)
                    }.font(StackType.caption).foregroundStyle(Palette.secondary)
                }
            }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
        }.frame(maxHeight: .infinity).background(Palette.surface.opacity(0.55))
    }

    private var footer: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { footerStatus; Spacer(); footerActions }
            VStack(alignment: .leading, spacing: 8) { footerStatus; footerActions }
        }.padding(.horizontal, 16).padding(.vertical, 12)
    }
    private var footerStatus: some View {
        Text(state.applied ? "Memory decisions applied" : "\(state.plan?.selectedIds?.count ?? 0) selected · \(state.plan?.evictedIds?.count ?? 0) evicted")
            .font(StackType.caption).foregroundStyle(Palette.secondary)
    }
    private var footerActions: some View {
        HStack(spacing: 12) {
            if narrow { Button("View source") { showingSource = true }.disabled(selected == nil) }
            Button("View context") { showingContext = true }.disabled(state.plan?.contextText?.isEmpty != false || !state.planIsCurrent || state.busy)
            Button("Copy", systemImage: "doc.on.doc") { copyContext() }.disabled(state.plan?.contextText?.isEmpty != false || !state.planIsCurrent || state.busy)
            Button("Review changes…") { showingApply = true }.buttonStyle(.borderedProminent)
                .disabled(state.plan?.applyAvailable != true || !state.planIsCurrent || state.applied || state.busy || !ready)
        }
    }
    private func actionTitle(_ action: String, memory: Bool) -> String {
        switch action { case "keep": "Keep in context"; case "inject": "Add to context"; case "evict": "Remove from context"; case "remember": "Remember"; case "forget": "Forget saved claim"; default: memory ? "No memory change" : "No context change" }
    }
    private func actionSymbol(_ action: String) -> String {
        switch action { case "keep": "checkmark.circle"; case "inject": "arrow.down.to.line"; case "evict": "arrow.up.right.square"; default: "minus.circle" }
    }
    private func copyContext() {
        guard state.planIsCurrent, let text = state.plan?.contextText else { return }
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text, forType: .string)
        state.message = "Selected context copied."
    }
    private func selectForgetTarget(_ id: String, title: String) {
        if !state.targetIDs.contains(id) { state.targetIDs.append(id) }
        state.targetTitles[id] = title; state.intent = "forget"
    }
    private func runPlan() {
        guard ready, !state.task.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, state.intent != "forget" || !state.targetIDs.isEmpty else { return }
        state.cancel()
        state.busy = true; state.message = ""; state.applied = false
        let request = state.generation, key = model.handoverPreviewKey, host = model.terminalHost, signature = state.signature
        state.requestSignature = signature
        let params: [String: Any] = ["workspaceId": model.selectedID ?? "", "task": state.task, "tokenBudget": state.budget,
            "intent": state.intent, "targetIds": state.intent == "forget" ? state.targetIDs : [],
            "sources": [state.sourcesMemory ? "memory" : nil, state.sourcesConversations ? "conversations" : nil].compactMap { $0 },
            "activeContext": state.activeContext.isEmpty ? [] : [["id": "active-draft", "title": "Active context", "body": state.activeContext, "source": "User supplied context"]],
            "incoming": state.incoming.isEmpty ? [] : [["id": "incoming-draft", "title": "Incoming passage", "body": state.incoming, "source": "User supplied passage"]]]
        state.request = Task { @MainActor in
            defer { if request == state.generation { state.busy = false; state.request = nil } }
            do {
                let result: JevContextPlan
                if fixture != nil { try await Task.sleep(for: .milliseconds(900)); result = JevMemoryWorkspace.fixturePlan(state.intent == "forget" ? "forget" : "results") }
                else { result = try await model.terminalCall("memory.context.plan", params, host: host, as: JevContextPlan.self) }
                guard !Task.isCancelled, request == state.generation, key == model.handoverPreviewKey, signature == state.signature else { return }
                state.plan = result
                if !decisions.contains(where: { $0.id == state.selectedID }) { state.selectedID = result.decisions?.first?.id }
            } catch {
                guard !Task.isCancelled, request == state.generation, key == model.handoverPreviewKey else { return }
                state.message = error.localizedDescription
            }
        }
    }
    private func applyPlan() {
        guard ready, state.planIsCurrent, let id = state.plan?.planId, !state.busy else { return }
        state.cancel(); state.busy = true; state.message = ""
        let request = state.generation, key = model.handoverPreviewKey, host = model.terminalHost
        state.request = Task { @MainActor in
            defer { if request == state.generation { state.busy = false; state.request = nil } }
            do {
                let result: JevContextApplied
                if fixture != nil { result = JevContextApplied(status: "applied", rememberedIds: ["fixture"], forgottenIds: []) }
                else { result = try await model.terminalCall("memory.context.apply", ["workspaceId": model.selectedID ?? "", "planId": id], host: host, as: JevContextApplied.self) }
                guard !Task.isCancelled, request == state.generation, key == model.handoverPreviewKey else { return }
                state.applied = result.status == "applied" || result.status == "completed"
                state.message = state.applied ? "Memory decisions applied." : "Memory apply: " + result.status
                if state.applied { showingApply = false }
            } catch {
                guard !Task.isCancelled, request == state.generation, key == model.handoverPreviewKey else { return }
                state.message = error.localizedDescription
            }
        }
    }
}

extension JevMemoryWorkspace {
    func loadFixture(_ state: String) {
        task = "Prepare the desktop memory release with exact evidence and cancellation checks"
        plan = state == "empty" ? nil : Self.fixturePlan(state)
        if state == "forget" { intent = "forget"; targetIDs = ["claim:memory-1"]; targetTitles = ["claim:memory-1": "Preserve reviewed source evidence"] }
        selectedID = plan?.decisions?.first?.id
        requestSignature = signature
        busy = state == "loading"
        if state == "failure" { message = "The selected host could not be reached. Retry when it is connected." }
    }
    static func fixturePlan(_ state: String) -> JevContextPlan {
        let decisions = [
            JevContextDecision(id: "claim:memory-1", title: "Preserve reviewed source evidence", body: "Every accepted memory keeps its original evidence and revision history. Retrieval includes only reviewed project claims.", source: "Project memory · release requirements", score: 0.97, confidence: 0.96, contextAction: state == "forget" ? "evict" : "inject", memoryAction: state == "forget" ? "forget" : "none", reason: "Directly supports the release task and its evidence requirement."),
            JevContextDecision(id: "active-1", title: "Native cancellation and stable input", body: "A cancelled or stale request must not replace newer results. Keep the draft, selection and reader position when navigating between views.", source: "Active context · desktop interaction contract", score: 0.94, confidence: 0.93, contextAction: "keep", memoryAction: "none", reason: "The existing context remains relevant to native verification."),
            JevContextDecision(id: "incoming-1", title: "New release verification evidence", body: "The isolated native fixture exercises empty, result, abstained and unavailable states without opening real project memories.", source: "Incoming passage · synthetic test record", score: 0.92, confidence: 0.91, contextAction: "inject", memoryAction: state == "forget" ? "none" : "remember", reason: "Useful verification evidence for future release decisions. Requires review before saving."),
            JevContextDecision(id: "active-2", title: "Old packaging experiment", body: "An unrelated packaging experiment used a temporary archive folder.", source: "Active context · earlier experiment", score: 0.08, confidence: 0.92, contextAction: "evict", memoryAction: "none", reason: "This unrelated passage consumes context without supporting the current task."),
            JevContextDecision(id: "claim:memory-2", title: "Optional source with a deliberately long label to verify wrapping and reserved row actions", body: "A future visual experiment may use a different navigation treatment once the current release is complete.", source: "Conversation source · design exploration", score: 0.12, confidence: 0.86, contextAction: "none", memoryAction: "none", reason: "No change: this source does not help the current task.")
        ]
        let noResults = ["unavailable", "abstained", "empty"].contains(state)
        return JevContextPlan(planId: "synthetic-plan", status: state == "unavailable" || state == "abstained" ? state : "completed", warning: nil,
            summary: noResults ? nil : "Every accepted memory keeps its original evidence and revision history. A cancelled or stale request must not replace newer results.", model: "Jev · synthetic fixture", tokenBudget: 2048, usedTokens: noResults ? 0 : 236,
            decisions: noResults ? [] : decisions, contextText: noResults ? "" : decisions.filter { ["keep", "inject"].contains($0.contextAction) }.map(\.body).joined(separator: "\n\n"),
            selectedIds: noResults ? [] : decisions.filter { ["keep", "inject"].contains($0.contextAction) }.map(\.id), evictedIds: noResults ? [] : decisions.filter { $0.contextAction == "evict" }.map(\.id), applyAvailable: !noResults,
            coverage: JevContextCoverage(candidateCount: noResults ? 0 : 5, evaluatedCount: noResults ? 0 : 5, omittedCount: 0, exhaustive: false, hasMore: false),
            toolDecisions: noResults ? [] : [JevContextToolDecision(tool: "Read source evidence", action: "inject", confidence: 0.94)], providerCalls: noResults ? 0 : 1)
    }
}
