import WidgetKit
import SwiftUI

// ─── Shared data model (mirrors widgetService.ts WidgetData) ─────────────────

struct WidgetTaskItem: Codable, Hashable {
  let plantName: String
  let careType:  String
  let emoji:     String
}

struct GamgeeWidgetData: Codable {
  let lastUpdated:   String
  let tasksDueToday: Int
  let tasksOverdue:  Int
  let plantsTotal:   Int
  let topTasks:      [WidgetTaskItem]
}

// ─── Timeline provider ────────────────────────────────────────────────────────

struct Provider: TimelineProvider {

  func loadData() -> GamgeeWidgetData {
    guard
      let defaults = UserDefaults(suiteName: "group.com.gamgee.app"),
      let json     = defaults.string(forKey: "gamgeeWidgetData"),
      let bytes    = json.data(using: .utf8),
      let decoded  = try? JSONDecoder().decode(GamgeeWidgetData.self, from: bytes)
    else {
      return GamgeeWidgetData(
        lastUpdated:   ISO8601DateFormatter().string(from: Date()),
        tasksDueToday: 0,
        tasksOverdue:  0,
        plantsTotal:   0,
        topTasks:      []
      )
    }
    return decoded
  }

  func placeholder(in context: Context) -> GamgeeEntry {
    GamgeeEntry(date: Date(), data: GamgeeWidgetData(
      lastUpdated:   ISO8601DateFormatter().string(from: Date()),
      tasksDueToday: 3,
      tasksOverdue:  1,
      plantsTotal:   8,
      topTasks: [
        WidgetTaskItem(plantName: "Monstera",  careType: "water",     emoji: "💧"),
        WidgetTaskItem(plantName: "Pothos",    careType: "fertilize", emoji: "🌿"),
        WidgetTaskItem(plantName: "Snake Plant",careType: "mist",     emoji: "💨"),
      ]
    ))
  }

  func getSnapshot(in context: Context, completion: @escaping (GamgeeEntry) -> Void) {
    completion(GamgeeEntry(date: Date(), data: loadData()))
  }

  func getTimeline(in context: Context, completion: @escaping (Timeline<GamgeeEntry>) -> Void) {
    let data  = loadData()
    let entry = GamgeeEntry(date: Date(), data: data)
    // Refresh every 30 minutes in case the app hasn't pushed new data
    let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
    completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
  }
}

// ─── Entry ────────────────────────────────────────────────────────────────────

struct GamgeeEntry: TimelineEntry {
  let date: Date
  let data: GamgeeWidgetData
}

// ─── Colour helpers ───────────────────────────────────────────────────────────

extension Color {
  static let gamgeeGreen  = Color(red: 0.11, green: 0.37, blue: 0.28)
  static let gamgeePastel = Color(red: 0.88, green: 0.96, blue: 0.91)
}

// ─── Small widget view ────────────────────────────────────────────────────────

struct SmallWidgetView: View {
  let entry: GamgeeEntry

  var urgency: Color {
    if entry.data.tasksOverdue  > 0 { return .orange }
    if entry.data.tasksDueToday > 0 { return .gamgeeGreen }
    return .secondary
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 4) {
      HStack {
        Text("🌿")
          .font(.title3)
        Spacer()
        Text("Gamgee")
          .font(.caption2)
          .foregroundColor(.secondary)
      }

      Spacer()

      Text("\(entry.data.tasksDueToday)")
        .font(.system(size: 46, weight: .bold, design: .rounded))
        .foregroundColor(urgency)
        .minimumScaleFactor(0.6)

      Text(entry.data.tasksDueToday == 1 ? "task today" : "tasks today")
        .font(.caption)
        .foregroundColor(.secondary)

      if entry.data.tasksOverdue > 0 {
        Text("⚠️ \(entry.data.tasksOverdue) overdue")
          .font(.caption2)
          .foregroundColor(.orange)
          .padding(.top, 2)
      }
    }
    .padding()
    .containerBackground(Color.gamgeePastel, for: .widget)
  }
}

// ─── Medium widget view ───────────────────────────────────────────────────────

struct MediumWidgetView: View {
  let entry: GamgeeEntry

  var body: some View {
    HStack(alignment: .top, spacing: 16) {

      // Left column — summary
      VStack(alignment: .leading, spacing: 6) {
        HStack(spacing: 6) {
          Text("🌿")
          Text("Gamgee")
            .font(.headline)
            .foregroundColor(.gamgeeGreen)
        }

        Spacer()

        Text("\(entry.data.tasksDueToday)")
          .font(.system(size: 38, weight: .bold, design: .rounded))
          .foregroundColor(entry.data.tasksOverdue > 0 ? .orange : .gamgeeGreen)

        Text(entry.data.tasksDueToday == 1 ? "task today" : "tasks today")
          .font(.caption)
          .foregroundColor(.secondary)

        if entry.data.tasksOverdue > 0 {
          Text("⚠️ \(entry.data.tasksOverdue) overdue")
            .font(.caption2)
            .foregroundColor(.orange)
        }

        Spacer()

        Text("\(entry.data.plantsTotal) plant\(entry.data.plantsTotal == 1 ? "" : "s")")
          .font(.caption2)
          .foregroundColor(.secondary)
      }
      .frame(maxWidth: .infinity, alignment: .leading)

      Divider()
        .padding(.vertical, 4)

      // Right column — task list
      VStack(alignment: .leading, spacing: 8) {
        if entry.data.topTasks.isEmpty {
          Spacer()
          Text("✅")
            .font(.title2)
          Text("All caught up!")
            .font(.caption)
            .foregroundColor(.secondary)
          Spacer()
        } else {
          ForEach(entry.data.topTasks, id: \.self) { task in
            HStack(spacing: 6) {
              Text(task.emoji)
                .font(.footnote)
              Text(task.plantName)
                .font(.caption)
                .fontWeight(.medium)
                .lineLimit(1)
            }
          }
          Spacer()
        }
      }
      .frame(maxWidth: .infinity, alignment: .leading)
    }
    .padding()
    .containerBackground(Color.gamgeePastel, for: .widget)
  }
}

// ─── Router view ──────────────────────────────────────────────────────────────

struct GamgeeWidgetEntryView: View {
  @Environment(\.widgetFamily) var family
  let entry: GamgeeEntry

  var body: some View {
    switch family {
    case .systemMedium: MediumWidgetView(entry: entry)
    default:            SmallWidgetView(entry: entry)
    }
  }
}

// ─── Widget definition ────────────────────────────────────────────────────────

struct GamgeeWidget: Widget {
  let kind = "GamgeeWidget"

  var body: some WidgetConfiguration {
    StaticConfiguration(kind: kind, provider: Provider()) { entry in
      GamgeeWidgetEntryView(entry: entry)
    }
    .configurationDisplayName("Gamgee Plant Care")
    .description("See which plants need care today.")
    .supportedFamilies([.systemSmall, .systemMedium])
  }
}

// ─── Entry point ──────────────────────────────────────────────────────────────

@main
struct GamgeeWidgetBundle: WidgetBundle {
  var body: some Widget {
    GamgeeWidget()
  }
}
