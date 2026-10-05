// elephant-mode gauge: a transparent floating panel with 4 dials (context, 5-hour limit,
// weekly limit, tokens). Drag it anywhere; it remembers its position. Red at 85 %.
// Launched by scripts/setup.py with the plugin data dir; reads <data>/latest.json written by statusline.py.
// Exits by itself when the plugin is updated or uninstalled (its own binary disappears).
// Build: widget/build.sh
import AppKit

let datos = CommandLine.arguments.dropFirst().first { !$0.hasPrefix("-") } ?? NSHomeDirectory() + "/.claude/elephant-mode"
let ruta = datos + "/latest.json"
let binario = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath().path
let es = Locale.preferredLanguages.first?.hasPrefix("es") ?? false
func t(_ en: String, _ sp: String) -> String { es ? sp : en }
let ALERTA = 85.0  // % usado a partir del cual se pone rojo (= queda 15 %)

struct Lectura {
    var ctx = 0.0, ctxTok = 0, ctxMax = 0
    var h5 = 0.0, h5Reset = 0.0
    var d7 = 0.0, d7Reset = 0.0
    var tokens = 0, duracionMs = 0.0
    var edad = Double.infinity  // segundos desde la última actualización
}

func leer() -> Lectura {
    var l = Lectura()
    guard let data = FileManager.default.contents(atPath: ruta),
          let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return l }
    if let m = try? FileManager.default.attributesOfItem(atPath: ruta)[.modificationDate] as? Date {
        l.edad = -m.timeIntervalSinceNow
    }
    let ahora = Date().timeIntervalSince1970
    if let cw = j["context_window"] as? [String: Any] {
        l.ctx = (cw["used_percentage"] as? Double) ?? 0
        l.ctxMax = (cw["context_window_size"] as? Int) ?? 0
        if let u = cw["current_usage"] as? [String: Any] {
            l.ctxTok = ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"]
                .reduce(0) { $0 + ((u[$1] as? Int) ?? 0) }
        }
        l.tokens = ((cw["total_input_tokens"] as? Int) ?? 0) + ((cw["total_output_tokens"] as? Int) ?? 0)
    }
    if let rl = j["rate_limits"] as? [String: Any] {
        func lim(_ k: String) -> (Double, Double) {
            guard let x = rl[k] as? [String: Any] else { return (0, 0) }
            let reset = (x["resets_at"] as? Double) ?? 0
            // si la ventana ya se reinició, el % guardado es viejo
            return (reset > 0 && reset < ahora ? 0 : (x["used_percentage"] as? Double) ?? 0, reset)
        }
        (l.h5, l.h5Reset) = lim("five_hour")
        (l.d7, l.d7Reset) = lim("seven_day")
    }
    if let c = j["cost"] as? [String: Any] { l.duracionMs = (c["total_duration_ms"] as? Double) ?? 0 }
    return l
}

func faltan(_ reset: Double) -> String {
    if reset == 0 { return "—" }
    let s = Int(reset - Date().timeIntervalSince1970)
    if s <= 0 { return t("reset", "reiniciado") }
    let d = s / 86400, h = (s % 86400) / 3600, m = (s % 3600) / 60
    return d > 0 ? t("resets \(d)d \(h)h", "reinicia \(d)d \(h)h") : t("resets \(h)h \(m)m", "reinicia \(h)h \(m)m")
}

func k(_ n: Int) -> String {
    n >= 1_000_000 ? String(format: "%.1fM", Double(n) / 1e6) : n >= 1000 ? "\(n / 1000)K" : "\(n)"
}

func color(_ pct: Double) -> NSColor {
    pct >= ALERTA ? .systemRed : pct >= 60 ? .systemYellow : .systemGreen
}

final class Vista: NSView {
    var l = Lectura()

    // Velocímetro: arco de 240° con aguja y número digital debajo.
    func gauge(_ c: NSPoint, _ pct: Double, _ titulo: String, _ sub: String, digital: String? = nil) {
        let r: CGFloat = 30, ini: CGFloat = 210
        let fondo = NSBezierPath()
        fondo.appendArc(withCenter: c, radius: r, startAngle: ini, endAngle: -30, clockwise: true)
        fondo.lineWidth = 7; fondo.lineCapStyle = .round
        NSColor.white.withAlphaComponent(0.12).setStroke(); fondo.stroke()

        let p = CGFloat(min(max(pct, 0), 100) / 100)
        let fin = ini - 240 * p
        if p > 0 {
            let arco = NSBezierPath()
            arco.appendArc(withCenter: c, radius: r, startAngle: ini, endAngle: fin, clockwise: true)
            arco.lineWidth = 7; arco.lineCapStyle = .round
            color(pct).setStroke(); arco.stroke()
        }
        let a = fin * .pi / 180
        let aguja = NSBezierPath()
        aguja.move(to: c); aguja.line(to: NSPoint(x: c.x + cos(a) * (r - 9), y: c.y + sin(a) * (r - 9)))
        aguja.lineWidth = 2; NSColor.white.withAlphaComponent(0.85).setStroke(); aguja.stroke()

        texto(digital ?? "\(Int(pct))%", NSPoint(x: c.x, y: c.y - 30), 14, .white, bold: true)
        texto(titulo, NSPoint(x: c.x, y: c.y - 44), 9, .white.withAlphaComponent(0.75), bold: true)
        texto(sub, NSPoint(x: c.x, y: c.y - 56), 9, .white.withAlphaComponent(0.55))
    }

    func texto(_ s: String, _ centro: NSPoint, _ size: CGFloat, _ col: NSColor, bold: Bool = false) {
        let t = NSAttributedString(string: s, attributes: [
            .font: NSFont.monospacedDigitSystemFont(ofSize: size, weight: bold ? .bold : .regular),
            .foregroundColor: col])
        t.draw(at: NSPoint(x: centro.x - t.size().width / 2, y: centro.y))
    }

    override func draw(_ dirty: NSRect) {
        let alerta = max(l.ctx, l.h5, l.d7) >= ALERTA
        let marco = NSBezierPath(roundedRect: bounds.insetBy(dx: 1, dy: 1), xRadius: 14, yRadius: 14)
        (alerta ? NSColor(red: 0.35, green: 0.04, blue: 0.04, alpha: 0.93) : NSColor(white: 0.08, alpha: 0.88)).setFill()
        marco.fill()
        marco.lineWidth = alerta ? 2.5 : 1
        (alerta ? NSColor.systemRed : NSColor.white.withAlphaComponent(0.15)).setStroke(); marco.stroke()

        let w = bounds.width / 4, y: CGFloat = 84
        gauge(NSPoint(x: w * 0.5, y: y), l.ctx, t("CONTEXT", "CONTEXTO"), "\(k(l.ctxTok)) / \(k(l.ctxMax))")
        gauge(NSPoint(x: w * 1.5, y: y), l.h5, t("5-HOUR", "SESIÓN 5h"), faltan(l.h5Reset))
        gauge(NSPoint(x: w * 2.5, y: y), l.d7, t("WEEK", "SEMANA"), faltan(l.d7Reset))
        let mins = Int(l.duracionMs / 60000)
        gauge(NSPoint(x: w * 3.5, y: y), l.ctx, "TOKENS", "chat \(mins / 60)h \(mins % 60)m", digital: k(l.tokens))

        let pie: String, col: NSColor
        if l.ctx >= ALERTA { pie = t("⚠ SAVING MEMORY · COMPACTING SOON", "⚠ GUARDANDO MEMORIA · COMPACTA PRONTO"); col = .white }
        else if alerta { pie = t("⚠ USAGE LIMIT NEAR · MEMORY SAVED", "⚠ LÍMITE CERCA · MEMORIA GUARDADA"); col = .white }
        else if l.edad > 600 { pie = l.edad.isInfinite ? t("waiting for Claude Code…", "esperando a Claude Code…") : t("no data for \(Int(l.edad / 60)) min", "sin datos hace \(Int(l.edad / 60)) min"); col = .white.withAlphaComponent(0.45) }
        else { pie = t("🐘 elephant mode · all good", "🐘 modo elefante · todo en orden"); col = .white.withAlphaComponent(0.45) }
        texto(pie, NSPoint(x: bounds.midX, y: 7), 10, col, bold: alerta)
    }
}

final class App: NSObject, NSApplicationDelegate {
    var win: NSPanel!, vista = Vista()

    func applicationDidFinishLaunching(_ n: Notification) {
        let tam = NSSize(width: 360, height: 132)
        let pant = NSScreen.main!.visibleFrame
        win = NSPanel(contentRect: NSRect(x: pant.maxX - tam.width - 12, y: pant.minY + 12, width: tam.width, height: tam.height),
                      styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        win.level = .floating
        win.collectionBehavior = [.canJoinAllSpaces, .stationary]
        win.isOpaque = false; win.backgroundColor = .clear; win.hasShadow = true
        win.isMovableByWindowBackground = true  // arrástralo a la esquina que quieras
        win.setFrameAutosaveName("ElephantModeGauge")  // recuerda la posición
        win.contentView = vista
        win.orderFrontRegardless()
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in self.tick() }
        tick()
    }

    func tick() {
        // plugin updated or uninstalled: the binary is gone, so close (the next session opens the new one)
        if !FileManager.default.fileExists(atPath: binario) { NSApp.terminate(nil) }
        vista.l = leer(); vista.needsDisplay = true
    }
}

// Test: Gauge <data-dir> --png out.png  renders the current state to a file and exits (used for README screenshots)
if let i = CommandLine.arguments.firstIndex(of: "--png"), i + 1 < CommandLine.arguments.count {
    let v = Vista(frame: NSRect(x: 0, y: 0, width: 360, height: 132)); v.l = leer()
    let rep = v.bitmapImageRepForCachingDisplay(in: v.bounds)!
    v.cacheDisplay(in: v.bounds, to: rep)
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[i + 1]))
    exit(0)
}

// Single instance: setup.py tracks the pid in <data>/gauge.pid
try? String(ProcessInfo.processInfo.processIdentifier).write(toFile: datos + "/gauge.pid", atomically: true, encoding: .utf8)

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // sin ícono en el Dock
let delegado = App(); app.delegate = delegado
app.run()
