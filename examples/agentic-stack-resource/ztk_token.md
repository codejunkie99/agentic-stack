## I cut my Claude context by 90% (here's how)
Avid
@Av1dlive
·
16h

Here is the truth nobody tells ai builders.

you do not need a bigger context window.
all you need to fix is

TLDR; if you don't wanna read it, then give this link to your agent and ask it questions ➡️ github.com/codejunkie99/ztk
Every guide tells you context engineering matters. Almost nobody shows you what is actually filling the context.
It is not your prompts. It is your shell.
I spent the last few weeks staring at this. Every time my agent ran git diff HEAD~5, ninety thousand tokens hit the context window. 
Across one normal coding session I measured 5.8 million wasted tokens. Not a theoretical number. A real one. I ran the proxy. I have the cache file. The bill made me build something.
This article is how I built ztk and why every line of it exists.
If you do not want to read all that, you can just install it:
markdown
brew install codejunkie99/ztk/ztk
ztk init -g
That is it. Last chance to bail out 
If you want to understand what you are installing and why each piece exists, keep reading. ⬇️
The shape of the whole thing
Here is the binary. I want you to see the whole thing first because the shape is the entire point.
bash
ztk (260KB single binary)
├── src/
│   ├── main.zig                # argv parsing, subcommand dispatch
│   ├── pipeline/
│   │   ├── detect.zig          # which command is this?
│   │   ├── guard.zig           # short-circuits before any filter runs
│   │   ├── compose.zig         # six-stage orchestrator
│   │   ├── budget.zig          # per-command output budgets
│   │   └── filters/            # one file per command family
│   │       ├── git_diff.zig
│   │       ├── git_status.zig
│   │       ├── git_log.zig
│   │       ├── cargo_test.zig
│   │       ├── pytest.zig
│   │       ├── jest.zig
│   │       ├── ls.zig
│   │       ├── grep.zig
│   │       ├── find.zig
│   │       ├── cat.zig
│   │       ├── docker.zig
│   │       └── ...
│   ├── regex/
│   │   ├── nfa.zig             # Thompson NFA, ~400 lines
│   │   ├── compile.zig         # parse pattern -> NFA
│   │   └── exec.zig            # step states across input
│   ├── simd/
│   │   ├── lines.zig           # @Vector(16,u8) line split
│   │   └── ansi.zig            # SIMD ANSI escape strip
│   ├── cache/
│   │   ├── mmap.zig            # mmap'd session cache
│   │   ├── ttl.zig             # per-command expiry rules
│   │   └── invalidate.zig      # mutation -> family flush
│   ├── hooks/
│   │   ├── claude_code.zig     # PreToolUse adapter
│   │   ├── cursor.zig
│   │   ├── gemini.zig
│   │   └── runner.zig          # the universal `ztk run`
│   └── stats/
│       └── ledger.zig          # rolling counters in ~/.ztk/stats
├── tests/                      # 231 tests, captured outputs
└── build.zig
That is the entire program. No runtime. No Python. No package manager. No shared libraries. Zig stdlib only.
The shape matters because every part of it follows one rule: the proxy must never be slower than the cost of the tokens it saves. A 5MB Node binary that takes 80ms to spin up has already lost. Whatever you saved in tokens, you spent in latency. ztk starts in under a millisecond. The cost of running it is below the cost of one extra token.
The other rule is just as important and easier to forget: the proxy must never lose information the model needs. "I made the output smaller" is not the goal. "I made the output smaller without changing what the model can decide from it" is the goal. Every filter in this repo exists because I caught it not changing the agent's behavior on a real task. The ones that did, I deleted.
The numbers
From a real 256-command development session:
This is my ztk stats
94.3% overall reduction. 13.8 million tokens saved across 256 commands.
I want to be honest about what these numbers do and do not say.
They are not a benchmark in a clean room. They are one developer's session. Your numbers will be different. 
Heavier git history means bigger diff savings. Fewer test runs means smaller test savings. A repo full of generated code means cat savings shrink.
What does hold across every session I have measured: passing tests collapse to almost nothing, ls collapses to almost nothing, git status between two unrelated commands collapses to almost nothing. 
The big diffs and big greps shrink less in percent but more in absolute tokens, which is what actually matters for the bill.
The smallest gain I have ever seen on a working session is 71%. The largest is 94%. I have not seen a session where ztk made things worse, because the one rule the pipeline enforces is that anything ztk does not recognize passes through untouched. The default is identity. Compression is opt-in per command.
The six-stage pipeline
This is the part where most "compression proxies" go wrong. They run a single regex, declare victory, and break on the first edge case. The pipeline I shipped has six stages and every stage has a job.
markdown
raw output
   │
   ▼
[1] detect    → which command is this? (argv-based, never content-based)
   │
   ▼
[2] guard     → small? error? exit-nonzero? bypass entirely
   │
   ▼
[3] tokenize  → SIMD line split, ANSI strip
   │
   ▼
[4] filter    → command-specific transform
   │
   ▼
[5] dedupe    → run-length encode repeats with counts
   │
   ▼
[6] cap       → if still over budget, truncate with marker
   │
   ▼
compressed output
Here is the orchestrator that wires it together. Every command goes through this same path.
go
// src/pipeline/compose.zig
const std = @import("std");
const detect = @import("detect.zig");
const guard = @import("guard.zig");
const lines = @import("../simd/lines.zig");
const ansi = @import("../simd/ansi.zig");
const filters = @import("filters/registry.zig");
const budget = @import("budget.zig");

pub fn run(
    arena: std.mem.Allocator,
    argv: []const []const u8,
    raw: []const u8,
    exit_code: u8,
    stderr: []const u8,
) ![]const u8 {
    // [1] detect
    const cmd = detect.classify(argv) orelse return raw;

    // [2] guard — three short-circuits, all preserve raw
    if (guard.shouldBypass(raw, exit_code, stderr, cmd)) return raw;

    // [3] tokenize
    const stripped = try ansi.stripInPlaceCopy(arena, raw);
    var line_list = std.ArrayList([]const u8).init(arena);
    try lines.splitInto(stripped, &line_list);

    // [4] filter
    var filtered = std.ArrayList(u8).init(arena);
    try filters.dispatch(cmd, line_list.items, &filtered);

    // [5] dedupe
    var deduped = std.ArrayList(u8).init(arena);
    try dedupeRuns(filtered.items, &deduped);

    // [6] cap
    const limit = budget.tokensFor(cmd);
    return budget.capWithMarker(arena, deduped.items, limit, cmd);
}
That is the whole orchestrator. Sixty lines. No control flow surprises. Every stage is a pure function over its input. If you want to add a stage, you add a line. If you want to skip a stage for one command, you check cmd and short-circuit.
I will walk through every stage with the actual code from the repo.
Stage 1 : detect
The detector keys off argv[0] and the first one or two arguments. Never the content. Content-based detection is the trap that kills every naive proxy. 
If you decide a payload is "test output" because it has the word PASS in it, the user pipes a log file through cat once and your filter eats their data. 

argv-only detection means the proxy is deterministic. Same input, same output. Always.
rust
// src/pipeline/detect.zig
pub const Cmd = enum {
    git_diff,
    git_status,
    git_log,
    git_show,
    cargo_test,
    cargo_build,
    cargo_check,
    pytest,
    go_test,
    npm_test,
    jest,
    vitest,
    ls_long,
    ls_short,
    grep,
    rg,
    find,
    cat_code,
    cat_data,
    docker_ps,
    docker_logs,
    kubectl_get,
    kubectl_logs,
    curl_response,
    env_dump,
    unknown,
};

pub fn classify(argv: []const []const u8) ?Cmd {
    if (argv.len == 0) return null;
    const a0 = std.fs.path.basename(argv[0]);

    // git family
    if (std.mem.eql(u8, a0, "git") and argv.len >= 2) {
        const sub = argv[1];
        if (std.mem.eql(u8, sub, "diff")) return .git_diff;
        if (std.mem.eql(u8, sub, "status")) return .git_status;
        if (std.mem.eql(u8, sub, "log")) return .git_log;
        if (std.mem.eql(u8, sub, "show")) return .git_show;
        return null;
    }

    // cargo family
    if (std.mem.eql(u8, a0, "cargo") and argv.len >= 2) {
        const sub = argv[1];
        if (std.mem.eql(u8, sub, "test") or std.mem.eql(u8, sub, "nextest")) return .cargo_test;
        if (std.mem.eql(u8, sub, "build")) return .cargo_build;
        if (std.mem.eql(u8, sub, "check") or std.mem.eql(u8, sub, "clippy")) return .cargo_check;
        return null;
    }

    // ls — long listing only ('-l' present anywhere)
    if (std.mem.eql(u8, a0, "ls")) {
        for (argv[1..]) |arg| {
            if (arg.len > 1 and arg[0] == '-' and std.mem.indexOfScalar(u8, arg, 'l') != null) {
                return .ls_long;
            }
        }
        return .ls_short;
    }

    // cat — split by extension to choose code vs data filter
    if (std.mem.eql(u8, a0, "cat") and argv.len >= 2) {
        const path = argv[argv.len - 1];
        if (isDataFile(path)) return .cat_data; // .json/.yaml/.toml never get touched
        if (isCodeFile(path)) return .cat_code;
        return null;
    }

    // grep / rg / find / pytest / jest / npm / docker / kubectl / curl / env ...
    // (rest of dispatch elided for the article — same shape)
    return null;
}

fn isDataFile(p: []const u8) bool {
    const exts = [_][]const u8{ ".json", ".yaml", ".yml", ".toml", ".ndjson", ".jsonl" };
    for (exts) |e| if (std.mem.endsWith(u8, p, e)) return true;
    return false;
}
fn isCodeFile(p: []const u8) bool {
    const exts = [_][]const u8{ ".zig", ".rs", ".go", ".ts", ".tsx", ".js", ".jsx", ".py", ".c", ".h", ".cpp", ".hpp" };
    for (exts) |e| if (std.mem.endsWith(u8, p, e)) return true;
    return false;
}
4 design notes worth pausing on.
cat splits its destination filter by file extension and deliberately bails on data formats. If you cat foo.json, ztk does nothing. 
The model needs the bytes verbatim because the next thing it does is parse them. Compressing structured data is where this whole genre of tools historically goes wrong.
 ls splits by whether -l appeared. ls src/ is already small and rarely worth touching. ls -la src/ is the one that costs a thousand tokens for thirty filenames. 
The split is at the dispatch layer, not inside one big filter, because the two cases really are different problems.
Stage 2 : guard
Three short-circuits before anything else runs. These three rules are the entire safety.
rust
//src/pipeline/guard.zig

const std = @import("std");
const Cmd = @import("detect.zig").Cmd;

const SMALL_THRESHOLD: usize = 80;

const ERROR_MARKERS = [_][]const u8{
    "error:", "Error:", "ERROR:",
    "panic:", "panicked at",
    "Traceback (most recent call last)",
    "fatal:", "FATAL",
    "Segmentation fault",
    "thread '", // rust panic preamble
};

pub fn shouldBypass(raw: []const u8, exit_code: u8, stderr: []const u8, cmd: Cmd) bool {
    // 1. small outputs — nothing worth compressing, risk of breaking pipes
    if (raw.len < SMALL_THRESHOLD) return true;

    // 2. nonzero exit — failures need full information
    if (exit_code != 0) {
        // exception: known noisy "expected failure" exits we still compress
        if (cmd == .cargo_check or cmd == .grep) return false;
        return true;
    }

    // 3. error markers anywhere in stderr OR stdout
    for (ERROR_MARKERS) |m| {
        if (std.mem.indexOf(u8, stderr, m) != null) return true;
        if (std.mem.indexOf(u8, raw, m) != null) return true;
    }

    return false;
The exemption for cargo check and grep is the kind of detail that costs a day if you get it wrong:
cargo check exits nonzero on warnings
 grep exits nonzero on zero matches, which is the most common case
Treat nonzero as "bail" for these two and the proxy stops doing anything useful for them
So they get whitelisted : every exemption like this lives in one file, auditable in one place
The error marker list took several rounds:
 Early versions had only error: lowercase
Lost a debugging session because pytest writes FAILED and Traceback and I was compressing the traceback away
Added panic: because Zig does that
Added Segmentation fault because it shows up on stderr without an error: prefix
The list grows whenever a real failure slips past it. It does not shrink
Stage 3 : tokenise
This is where Zig pays for itself. Splitting lines and stripping ANSI escapes on a 92KB diff is a measurable fraction of the proxy's wall time. 
Both passes use @Vector(16, u8), which compiles to NEON on ARM and SSE2 on x86. Same source, both targets, no #ifdef.
rust
/ src/simd/lines.zig
const std = @import("std");
const V = @Vector(16, u8);

pub fn splitInto(buf: []const u8, out: *std.ArrayList([]const u8)) !void {
    var start: usize = 0;
    var i: usize = 0;
    const newline: V = @splat('\n');

    while (i + 16 <= buf.len) : (i += 16) {
        const chunk: V = buf[i..][0..16].*;
        const eq = chunk == newline;
        const bits: u16 = @bitCast(eq);
        if (bits == 0) continue;

        var bm = bits;
        while (bm != 0) {
            const off = @ctz(bm);
            const nl_at = i + off;
            try out.append(buf[start..nl_at]);
            start = nl_at + 1;
            bm &= bm - 1; // clear lowest set bit
        }
    }

    // scalar tail for the last <16 bytes
    while (i < buf.len) : (i += 1) {
        if (buf[i] == '\n') {
            try out.append(buf[start..i]);
            start = i + 1;
        }
    }
    if (start < buf.len) try out.append(buf[start..]);
}
If you have never written SIMD before, the mental model:
- Instead of asking "is this byte a newline?" sixteen times, you ask once across sixteen bytes and read off a bitmask
- @ctz (count trailing zeros) gives you the index of the next set bit
- bm &= bm - 1 clears it
- The two-line bit-twiddling at the end of the loop is the standard pattern for iterating set bits in a bitmask
- On a 92KB diff: 92,000 branch-predicted comparisons → ~5,750 vectorized ones
ANSI stripping uses the same shape, with one complication:
- An ANSI escape is variable-length :  \x1b[ followed by parameters, then a terminator in the range @–~
- The SIMD pass identifies escape starts
- A small state machine walks each escape to its end

rust
// src/simd/ansi.zig
pub fn stripInPlaceCopy(arena: std.mem.Allocator, src: []const u8) ![]u8 {
    var out = try arena.alloc(u8, src.len);
    var w: usize = 0;
    var i: usize = 0;
    const esc: V = @splat(0x1b);

    while (i + 16 <= src.len) : (i += 16) {
        const chunk: V = src[i..][0..16].*;
        const eq = chunk == esc;
        const bits: u16 = @bitCast(eq);
        if (bits == 0) {
            @memcpy(out[w..][0..16], src[i..][0..16]);
            w += 16;
            continue;
        }
        // mixed chunk: copy up to first ESC, then walk the escape, then resume
        var local: usize = 0;
        var bm = bits;
        while (bm != 0) {
            const off = @ctz(bm);
            @memcpy(out[w..][0 .. off - local], src[i + local .. i + off]);
            w += off - local;
            // skip ESC + [ + params + terminator
            const end = scanEscapeEnd(src, i + off);
            local = end - i;
            bm &= bm - 1;
        }
        @memcpy(out[w..][0 .. 16 - local], src[i + local .. i + 16]);
        w += 16 - local;
    }
    // scalar tail
    while (i < src.len) : (i += 1) {
        if (src[i] == 0x1b) {
            i = scanEscapeEnd(src, i) - 1; // -1 because loop will i+=1
        } else {
            out[w] = src[i];
            w += 1;
        }
    }
    return out[0..w];
}

fn scanEscapeEnd(src: []const u8, start: usize) usize {
    // ESC '[' params terminator
    var p = start + 1;
    if (p >= src.len) return src.len;
    if (src[p] != '[') return p + 1;
    p += 1;
    while (p < src.len) : (p += 1) {
        const c = src[p];
        if (c >= 0x40 and c <= 0x7e) return p + 1;
    }
    return src.len;
}

I am showing this much code on purpose. People assume "SIMD" means "library." It does not. 
In Zig it means @Vectorand @bitCast and a handful of intrinsics, all in stdlib. You can write the whole thing in two short files and read every line. There is nothing magic happening.
Stage 4 : filter
This is where the actual compression lives. Per command. Independent. Each filter reads the line slice produced by stage 3 and writes to an output buffer. Filters never call each other. 
Filters never reach into the raw bytes. If a filter has a bug, every other command is unaffected.
I will show three filters end to end. Pick whichever is closest to a tool you care about, but all three teach the same lesson: summarize counts, surface anomalies, drop the rest.
rust
git diff

// src/pipeline/filters/git_diff.zig

const std = @import("std");

const State = enum { idle, in_hunk, in_meta };

pub fn filter(lines: []const []const u8, out: *std.ArrayList(u8)) !void {
    var state: State = .idle;
    var current_file: []const u8 = "";
    var added: u32 = 0;
    var removed: u32 = 0;
    var hunk_buf = std.ArrayList(u8).init(out.allocator);
    defer hunk_buf.deinit();

    for (lines) |line| {
        // file header
        if (std.mem.startsWith(u8, line, "diff --git ")) {
            try flushFile(out, current_file, added, removed, hunk_buf.items);
            current_file = parseDiffPath(line);
            added = 0;
            removed = 0;
            hunk_buf.clearRetainingCapacity();
            state = .in_meta;
            continue;
        }

        // skip metadata lines that the model never reads
        if (state == .in_meta) {
            if (std.mem.startsWith(u8, line, "@@")) {
                state = .in_hunk;
                try hunk_buf.appendSlice(line);
                try hunk_buf.append('\n');
                continue;
            }
            // index, mode, +++ ---, similarity, rename — all dropped
            continue;
        }

        if (state == .in_hunk) {
            if (line.len == 0) {
                try hunk_buf.append('\n');
                continue;
            }
            switch (line[0]) {
                '+' => {
                    added += 1;
                    try hunk_buf.appendSlice(line);
                    try hunk_buf.append('\n');
                },
                '-' => {
                    removed += 1;
                    try hunk_buf.appendSlice(line);
                    try hunk_buf.append('\n');
                },
                ' ' => {
                    // context line — keep at most 1 above and 1 below each change
                    try keepTrimmedContext(&hunk_buf, line);
                },
                '@' => {
                    try hunk_buf.appendSlice(line);
                    try hunk_buf.append('\n');
                },
                else => {},
            }
        }
    }
    try flushFile(out, current_file, added, removed, hunk_buf.items);
}

fn flushFile(
    out: *std.ArrayList(u8),
    path: []const u8,
    added: u32,
    removed: u32,
    body: []const u8,
) !void {
    if (path.len == 0) return;
    try out.writer().print(
        "── {s} (+{d} -{d})\n",
        .{ path, added, removed },
    );
    try out.appendSlice(body);
    try out.append('\n');
}

fn parseDiffPath(line: []const u8) []const u8 {
    // diff --git a/path/to/file b/path/to/file
    var it = std.mem.tokenizeScalar(u8, line, ' ');
    _ = it.next();
    _ = it.next();
    _ = it.next();
    if (it.next()) |b_path| {
        if (std.mem.startsWith(u8, b_path, "b/")) return b_path[2..];
        return b_path;
    }
    return "";
}
What it drops:
index abc1234..def5678 100644 : git's internal blob hashes, the model never reads them
--- a/path and +++ b/path : already encoded by the file header
similarity index 96%, rename from, rename to collapsed into the path line
All but one line of context above/below each change
What it keeps:
The file path with +/- line counts
Hunk headers (@@ -10,7 +10,9 @@) so the model knows where in the file
All + and - lines verbatim
One line of context immediately around each change
markdown
A 92KB diff turns into something like:

── src/pipeline/filters/git_diff.zig (+18 -3)
@@ -42,5 +42,9 @@
 fn flushFile(
+    out: *std.ArrayList(u8),
+    path: []const u8,
-    o: *Buf, p: []const u8,
@@ -88,2 +92,4 @@
+        try out.append('\n');
The model can still answer "what changed in this file?" The 92,000 → 18,000 token drop is real but uneven. 
Big diffs of mostly-unchanged files (e.g. a refactor that touches whitespace) compress more. 
Small focused diffs compress less because there is less noise to remove. Either way the model has not lost a single change line.
rust
cargo test

// src/pipeline/filters/cargo_test.zig

const std = @import("std");

pub fn filter(lines: []const []const u8, out: *std.ArrayList(u8)) !void {
    var passed: u32 = 0;
    var failed: u32 = 0;
    var ignored: u32 = 0;
    var failures = std.ArrayList([]const u8).init(out.allocator);
    defer failures.deinit();

    var summary_line: ?[]const u8 = null;
    var in_failure_block = false;
    var failure_buf = std.ArrayList(u8).init(out.allocator);
    defer failure_buf.deinit();

    for (lines) |line| {
        // count test results
        if (std.mem.indexOf(u8, line, " ... ok") != null) {
            passed += 1;
            continue;
        }
        if (std.mem.indexOf(u8, line, " ... FAILED") != null) {
            failed += 1;
            try failures.append(line);
            continue;
        }
        if (std.mem.indexOf(u8, line, " ... ignored") != null) {
            ignored += 1;
            continue;
        }
        if (std.mem.startsWith(u8, line, "test result:")) {
            summary_line = line;
            continue;
        }
        // capture failure detail blocks (---- name stdout ----)
        if (std.mem.startsWith(u8, line, "----") and std.mem.indexOf(u8, line, "stdout") != null) {
            in_failure_block = true;
            try failure_buf.appendSlice(line);
            try failure_buf.append('\n');
            continue;
        }
        if (in_failure_block) {
            if (line.len == 0) {
                in_failure_block = false;
                try failure_buf.append('\n');
            } else {
                try failure_buf.appendSlice(line);
                try failure_buf.append('\n');
            }
        }
    }

    // emit
    if (failed == 0) {
        try out.writer().print("✓ {d} passed", .{passed});
        if (ignored > 0) try out.writer().print(", {d} ignored", .{ignored});
        try out.append('\n');
    } else {
        try out.writer().print("✗ {d} failed, {d} passed", .{ failed, passed });
        if (ignored > 0) try out.writer().print(", {d} ignored", .{ignored});
        try out.append('\n');
        try out.appendSlice("failures:\n");
        for (failures.items) |f| {
            try out.writer().print("  {s}\n", .{f});
        }
        if (failure_buf.items.len > 0) {
            try out.append('\n');
            try out.appendSlice(failure_buf.items);
        }
    }
}

On a failing suite, every passing test still collapses to a count, but every failure line is preserved verbatim and the failure detail block (panic message, expected vs actual, location) flows through whole.
This is the asymmetry that matters. On success, brutal compression. On failure, full fidelity. A test runner output where the model cannot see the failure is worse than no output at all.
rust
ls -la

// src/pipeline/filters/ls.zig

const std = @import("std");

pub fn filterLong(lines: []const []const u8, out: *std.ArrayList(u8)) !void {
    var dirs: u32 = 0;
    var files: u32 = 0;
    var symlinks: u32 = 0;
    var executables: u32 = 0;
    var notable = std.ArrayList([]const u8).init(out.allocator);
    defer notable.deinit();
    var total_size: u64 = 0;

    for (lines) |line| {
        if (line.len < 10) continue;
        if (std.mem.startsWith(u8, line, "total ")) continue;

        const t = line[0];
        switch (t) {
            'd' => dirs += 1,
            '-' => files += 1,
            'l' => symlinks += 1,
            else => continue,
        }

        // executable file? notable.
        if (t == '-' and std.mem.indexOf(u8, line[1..10], "x") != null) {
            executables += 1;
            try notable.append(extractName(line));
            continue;
        }

        // symlink? notable.
        if (t == 'l') {
            try notable.append(line); // keep the -> target
            continue;
        }

        // unusual permissions (group/world write)? notable.
        if (line[5] == 'w' or line[8] == 'w') {
            try notable.append(extractName(line));
        }

        if (parseSize(line)) |sz| total_size += sz;
    }

    try out.writer().print(
        "{d} files, {d} dirs",
        .{ files, dirs },
    );
    if (symlinks > 0) try out.writer().print(", {d} symlinks", .{symlinks});
    if (total_size > 0) try out.writer().print(", {d} bytes total", .{total_size});
    try out.append('\n');

    if (notable.items.len > 0) {
        try out.appendSlice("notable:\n");
        for (notable.items) |n| try out.writer().print("  {s}\n", .{n});
    }
}

fn extractName(line: []const u8) []const u8 {
    // ls -la columns: perms links owner group size mon day time name
    var col: u8 = 0;
    var i: usize = 0;
    while (i < line.len and col < 8) : (i += 1) {
        if (line[i] == ' ' and (i + 1 >= line.len or line[i + 1] != ' ')) col += 1;
    }
    return std.mem.trim(u8, line[i..], " \t");
}

fn parseSize(line: []const u8) ?u64 {
    var it = std.mem.tokenizeScalar(u8, line, ' ');
    var col: u8 = 0;
    while (it.next()) |tok| : (col += 1) {
        if (col == 4) return std.fmt.parseInt(u64, tok, 10) catch null;
    }
    return null;
}

The model can answer "what's in this directory?" without reading every permission bit, group, owner, and timestamp. 
The notable list surfaces three things the model would want to know about executables, symlinks, and unusual permissions. Everything else collapses to a count.
The shape of every other filter in the repo is the same: read once, summarize counts, surface anomalies, emit. 
No filter looks at another filter's output. No filter knows about another command. They are independent and they fail in isolation.
Stage 5 : dedupe
After filtering, repeated lines collapse with a count. This happens after the per-command filter because some filters legitimately emit repeats that should be preserved (e.g. the same line appearing in two diff hunks). Dedupe operates only on adjacent runs.
rust
// src/pipeline/compose.zig (continued)

fn dedupeRuns(input: []const u8, out: *std.ArrayList(u8)) !void {
    var it = std.mem.splitScalar(u8, input, '\n');
    var prev: ?[]const u8 = null;
    var run: u32 = 0;

    while (it.next()) |line| {
        if (prev != null and std.mem.eql(u8, prev.?, line)) {
            run += 1;
            continue;
        }
        try flushPrev(out, prev, run);
        prev = line;
        run = 1;
    }
    try flushPrev(out, prev, run);
}

fn flushPrev(out: *std.ArrayList(u8), prev: ?[]const u8, run: u32) !void {
    if (prev == null) return;
    try out.appendSlice(prev.?);
    if (run > 1) try out.writer().print("  (×{d})", .{run});
    try out.append('\n');
}
(repeated 47 times) is a hundredth the size of the same line written 47 times. Most of the time this stage does nothing. 

When it fires, it is usually on log output "connection refused" 200 times in a row collapses to one line and a count.

Stage 6 : cap
If the result is still bigger than a per-command budget, truncate with a marker that names the command and how much was dropped. The model knows it is not seeing everything. That single fact is more important than any specific filter.
rust
// src/pipeline/budget.zig

const std = @import("std");
const Cmd = @import("detect.zig").Cmd;

pub fn tokensFor(cmd: Cmd) usize {
    return switch (cmd) {
        .git_diff => 8000,
        .git_log => 4000,
        .git_status => 1000,
        .cargo_test, .pytest, .jest, .vitest, .go_test => 2000,
        .grep, .rg => 2000,
        .ls_long, .ls_short, .find => 800,
        .cat_code => 4000,
        .docker_logs, .kubectl_logs => 4000,
        else => 4000,
    };
}

// 1 token ≈ 4 bytes of English / code on average
pub fn capWithMarker(
    arena: std.mem.Allocator,
    body: []const u8,
    token_limit: usize,
    cmd: Cmd,
) ![]const u8 {
    const byte_limit = token_limit * 4;
    if (body.len <= byte_limit) return body;

    var out = try arena.alloc(u8, byte_limit + 256);
    @memcpy(out[0..byte_limit], body[0..byte_limit]);
    const dropped_bytes = body.len - byte_limit;
    const dropped_tokens = dropped_bytes / 4;
    const marker = try std.fmt.bufPrint(
        out[byte_limit..],
        "\n... [ztk: {d} more tokens omitted from {s} output]\n",
        .{ dropped_tokens, @tagName(cmd) },
    );
    return out[0 .. byte_limit + marker.len];
}
The marker matters. When the model sees [ztk: 12000 more tokens omitted from git_log output], it can decide to ask for the rest with a more specific command. 
Silent truncation is the worst possible outcome. The model is making decisions on a partial view and does not know it.
What never gets touched
Half the work in shipping a proxy like this is deciding what NOT to compress. The rules I converged on, listed plainly because they are the part most people get wrong:
Errors. Anything that smells like a stack trace, panic, or compiler error passes through whole. Always.
Exit codes. Always preserved on the wrapper. Compression must never change whether the agent thinks the command succeeded.
Outputs under 80 bytes. Below this threshold there is nothing to compress and a non-zero chance of breaking pipes.
Structured data formats. JSON, YAML, TOML. Even if a filter could trim them, the model relies on the structure being intact for jq, yq, and friends. Out of scope.
Anything ztk does not recognize. Pass-through is the default. The proxy is opt-in per command, not opt-out.
The rule that took me three iterations to get right: never decide whether something is safe to compress based on the content of the output. Decide based on the command that produced it. 
If argv[0] says it is cargo test, treat it as test output, regardless of whether it looks like one. If argv[0] is cat, do not compress, no matter how much it looks like a log file. 
Content-based dispatch is where every previous attempt at this kind of tool died.
The Thompson NFA regex engine
Several filters need regex : for example, the runtime extension system that lets users add their own command-specific patterns. I needed a regex engine I trusted not to backtrack catastrophically on adversarial output. Tool output is the worst case for regex: long, repetitive, occasionally pathological.
I tried Zig's stdlib. There is no general-purpose regex engine in stdlib at the time I shipped this. I tried embedding PCRE. The binary jumped past 2MB. I wrote a Thompson NFA in an afternoon and regretted not starting there.
The whole engine is around 400 lines. Here is the core. Ken Thompson's 1968 algorithm; nothing about it is novel.
rust
// src/regex/nfa.zig

const std = @import("std");

pub const Op = enum { char, class, any, split, jump, match };

pub const Inst = struct {
    op: Op,
    // for .char
    ch: u8 = 0,
    // for .class
    class_lo: u8 = 0,
    class_hi: u8 = 0,
    negate: bool = false,
    // for .split / .jump
    a: i32 = 0,
    b: i32 = 0,
};

pub const Program = struct {
    insts: []const Inst,
};

/// state set is a bitset over instruction indices.
/// for typical patterns under a few hundred instructions this is 32-64 bytes.
pub fn match(prog: Program, input: []const u8, arena: std.mem.Allocator) !bool {
    var current = try BitSet.init(arena, prog.insts.len);
    var next = try BitSet.init(arena, prog.insts.len);
    try addState(prog, &current, 0);

    for (input) |c| {
        next.clearAll();
        var it = current.iterator();
        while (it.next()) |i| {
            const inst = prog.insts[i];
            switch (inst.op) {
                .char => if (inst.ch == c) try addState(prog, &next, @intCast(i + 1)),
                .class => {
                    const in_range = c >= inst.class_lo and c <= inst.class_hi;
                    if (in_range != inst.negate) try addState(prog, &next, @intCast(i + 1));
                },
                .any => try addState(prog, &next, @intCast(i + 1)),
                .match => return true, // can match early on partial
                else => {},
            }
        }
        std.mem.swap(BitSet, &current, &next);
        if (current.isEmpty()) return false;
    }

    var it = current.iterator();
    while (it.next()) |i| {
        if (prog.insts[i].op == .match) return true;
    }
    return false;
}

fn addState(prog: Program, set: *BitSet, idx: i32) !void {
    if (idx < 0 or idx >= prog.insts.len) return;
    if (set.isSet(@intCast(idx))) return;
    set.set(@intCast(idx));
    const inst = prog.insts[@intCast(idx)];
    switch (inst.op) {
        .split => {
            try addState(prog, set, idx + inst.a);
            try addState(prog, set, idx + inst.b);
        },
        .jump => try addState(prog, set, idx + inst.a),
        else => {},
    }
}
The thing that makes this engine immune to catastrophic backtracking is that the state set has bounded size  bounded by the number of instructions in the program, not by the input. 
PCRE-style backtracking engines can explode to exponential time on patterns like (a+)+b against aaaaaaaaaa...c. 
A Thompson NFA processes that input in linear time because at every byte the state set has at most a few entries.
The regex engine has its own test suite 11 tests, every one a known-bad pattern that destroys naive regex implementations. If you ever build something like this, write the adversarial tests first. Patterns like (a+)+$, a?a?a?...aaaa, and similar are the tests that catch a real engine vs. a toy.
Session memory: the mmap'd cache
ztk remembers what it already showed you.
If your agent runs git status three times in a minute and nothing changed, the second and third responses say (unchanged since 14:22:06) instead of repeating the full output. 
Powered by an mmap'd cache file with per-command TTLs.
rust
// src/cache/mmap.zig

const std = @import("std");

const SLOT_COUNT: usize = 4096;
const MAGIC: u32 = 0x5a544b01; // 'ZTK\x01'

const Header = extern struct {
    magic: u32,
    version: u32,
    created_at: i64,
    _pad: [16]u8,
};

const Slot = extern struct {
    key_hash: u64,        // hash of cmd_kind + argv tail + cwd
    digest: [32]u8,       // blake3 of last output
    ts_unix: i64,
    age_seconds: u32,
    cmd_kind: u32,
    last_size: u32,
    _pad: [12]u8,
};

const FILE_BYTES = @sizeOf(Header) + @sizeOf(Slot) * SLOT_COUNT;

pub const Cache = struct {
    file: std.fs.File,
    map: []align(std.mem.page_size) u8,
    header: *Header,
    slots: [*]Slot,

    pub fn open(path: []const u8) !Cache {
        const f = try std.fs.cwd().createFile(path, .{ .read = true, .truncate = false });
        try f.setEndPos(FILE_BYTES);
        const m = try std.posix.mmap(
            null,
            FILE_BYTES,
            std.posix.PROT.READ | std.posix.PROT.WRITE,
            .{ .TYPE = .SHARED },
            f.handle,
            0,
        );
        const hdr: *Header = @alignCast(@ptrCast(m.ptr));
        if (hdr.magic != MAGIC) {
            hdr.* = .{
                .magic = MAGIC,
                .version = 1,
                .created_at = std.time.timestamp(),
                ._pad = .{0} ** 16,
            };
        }
        return .{
            .file = f,
            .map = m,
            .header = hdr,
            .slots = @alignCast(@ptrCast(m.ptr + @sizeOf(Header))),
        };
    }

    pub fn close(self: *Cache) void {
        std.posix.munmap(self.map);
        self.file.close();
    }

    pub fn lookup(self: *Cache, key: u64, cmd: u32) ?CacheHit {
        const idx = key % SLOT_COUNT;
        const s = &self.slots[idx];
        if (s.key_hash != key) return null;
        const now = std.time.timestamp();
        const age = now - s.ts_unix;
        if (age > ttlForCmd(cmd)) return null;
        return .{ .digest = s.digest, .age_seconds = @intCast(age), .last_size = s.last_size };
    }

    pub fn store(self: *Cache, key: u64, cmd: u32, digest: [32]u8, size: u32) void {
        const idx = key % SLOT_COUNT;
        self.slots[idx] = .{
            .key_hash = key,
            .digest = digest,
            .ts_unix = std.time.timestamp(),
            .age_seconds = 0,
            .cmd_kind = cmd,
            .last_size = size,
            ._pad = .{0} ** 12,
        };
    }
};

pub const CacheHit = struct {
    digest: [32]u8,
    age_seconds: u32,
    last_size: u32,
};
Per-command TTL rules:
// src/cache/ttl.zig
const Cmd = @import("../pipeline/detect.zig").Cmd;

pub fn ttlForCmd(cmd: u32) i64 {
    const c: Cmd = @enumFromInt(cmd);
    return switch (c) {
        .git_status, .ls_long, .ls_short => 30,
        .cargo_test, .pytest, .jest, .vitest, .go_test => 120,
        .git_log, .git_show, .find => 300,
        .grep, .rg => 60,
        else => 60,
    };
}
And the invalidation rules:
// src/cache/invalidate.zig
const std = @import("std");
const Cmd = @import("../pipeline/detect.zig").Cmd;

/// returns the cmd kinds whose cache entries should be flushed
/// after `mutator` runs successfully.
pub fn flushedBy(mutator: Cmd) []const Cmd {
    return switch (mutator) {
        .git_diff, .git_status => &.{}, // pure reads
        // mutating git ops invalidate status + diff + log
        // (we identify these by argv at the dispatch site, not here)
        else => &.{},
    };
}

pub const MUTATOR_ARGV = struct {
    pub const git_writes = [_][]const u8{ "add", "commit", "rm", "mv", "checkout", "reset", "stash", "merge", "rebase", "pull", "fetch" };
    pub const npm_writes = [_][]const u8{ "install", "ci", "update", "uninstall" };
    pub const cargo_writes = [_][]const u8{ "add", "remove", "update", "fetch" };
};

- Cache is a single mmap'd file. 
- Open, hash the command key, read or write the slot, close
- Survives across processes (it's a file) and reboots (it's on disk)
- TTL check fires on every lookup so that means auto-cleanup
- 4096 fixed slots, ~80 bytes each + header → ~320KB file
- Collisions resolved by overwrite :newer wins
- Cache is a hint, not a source of truth. Miss falls back to running the command
- Collision cost: one wasted execution. Hit cost: microseconds
The compounding insight:
- Most agent loops are repetitive : ls, edit, ls again, test, edit, test
- Per-command savings are not the win
- The win is recognizing the agent already saw this two messages ago
Why Zig
I want to say upfront: you do not need Zig to build this. You could build the same proxy in Go, in Rust, in C. The reason Zig won for me is narrow and concrete.
Binary size. 260KB. 
Startup time. 
Cross-compile from anything. 
No allocator surprises. 
Custom regex was achievable. 
I want to say this part carefully: the language is not the point. The constraints are. If your proxy ships at 5MB, takes 80ms to start, and uses a regex engine that backtracks on adversarial test output, you have built a slower agent and called it a faster one. 
Zig made it easy to hit those constraints. 
Hooks: how it actually plugs in
- ztk is useless unless the agent calls through it
- Claude Code: PreToolUse hook intercepts bash calls, rewrites them through ztk run
- Adapter: ~80 lines. JSON in on stdin, rewritten JSON out on stdout
- ztk run: spawns the command, captures output, runs the pipeline, preserves exit code
Design point:
- ztk owns one thing : the bytes between the shell and the LLM
- Not the agent loop, not the model, not the context window
- New agent (Cursor, Gemini CLI, Copilot) = one adapter file in src/hooks/
What I learned shipping this
Days 1–2, scoped wrong. Built a daemon-backed LSP-like server. Deleted it. The proxy must be a one-shot binary, invisible, no process to manage.
Days 3–4, filter explosion. One giant state machine for all commands worked for 80% and broke unfixably on the rest. Rewrote as one filter per command family. More code, fewer bugs.
Days 5–6, regex. Zig stdlib lacked it. PCRE pushed the binary past 2MB. Wrote the Thompson NFA in an afternoon. If the library is heavier than your whole binary, write the small thing.
Day 7, cache. 40 lines for the cache, 20 per filter for invalidation. Savings went 67% to 90% the day it shipped, because agents re-run git status and ls constantly.
Day 8/10, stats and test corpus. Build the dashboard for yourself, not the user. It is the only way you trust the tool. Test against captured outputs in-repo, not live tools, or your suite goes flaky.
What to watch out for
Output corruption. A miscount or dropped brace silently poisons model input. Mitigation: 231 tests, 5+ captured-output tests per filter.
Tool version drift. cargo test and git diff formats change. Pin captured samples. Warn on unfamiliar tool versions.
The "just turn it off" trap. Once you corrupt output, the user is gone forever. Under-compress before you ever change semantics.
Caching mutations. git add, npm install, cargo update, terraform apply look like reads but mutate. Maintain an explicit mutation list and flush on hit.
Redaction and cache key. Mask TOKEN/SECRET/KEY/PASSWORD in env output (hygiene, not a security boundary). Key the cache by command and cwd from day one. Retrofitting invalidates everything.
Things I would do differently
Build ztk stats on day one, not day eight. 
Write argv-based detection from the start. 
Ship one filter and the harness before adding more. .
Skip Cursor/Gemini support until somebody asks. 
Cache invalidation deserves its own test suite.
Capture tool output into tests/captured/ from day one. 
Conclusion
Right now this proxy compresses one shell at a time. But the same shape works for every tool boundary an agent crosses. 
Every place where the model talks to a real system through a thin pipe is a place where you can compress without losing meaning, as long as the compression is deterministic, errors pass through whole, and the rule is never to lie about what happened.
The model you can swap whenever something better ships. The context window will keep growing, slowly, on someone else's release schedule. 
What you control is what you put in it. And most of what is in it right now is metadata you never asked for.
Own your context. Stop paying the token tax. Keep the proxy thin and the safety rules thick.
I built the first working version in a weekend. The full thing took eight days. It has been getting smaller and faster every week since.