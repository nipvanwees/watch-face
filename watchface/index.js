import * as hmUI from "@zos/ui";
import { Time, HeartRate, Step } from "@zos/sensor";
import { launchApp } from "@zos/router";
import { openSync, readSync, closeSync, O_RDONLY } from "@zos/fs";
import {
  COLORS,
  BACKGROUND_STYLE,
  DIAL_STYLE,
  TIME_STYLE,
  WEEKDAY_STYLE,
  DAY_STYLE,
  METRICS,
  POINTER_STYLE,
  POINTER_AOD_STYLE,
} from "./index.layout.js";

const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

// The Mobility app (../mobility-app) writes today's finished exercises to its /data/sessions.txt as "<YYYYMMDD> <count>"
const STRETCH_APP_ID = 1132586;
const STRETCH_FILE = "sessions.txt";

// The Water app (../water-app) writes today's total to its /data/water.txt as "<YYYYMMDD> <ml>"
const WATER_APP_ID = 1132590;
const WATER_FILE = "water.txt";

const time = new Time();
const heartRate = new HeartRate();
const step = new Step();
const widgets = {};

const pad = (n) => String(n).padStart(2, "0");
const setText = (widget, text) => widget.setProperty(hmUI.prop.TEXT, text);

function updateTime() {
  const text = `${pad(time.getFormatHour())}:${pad(time.getMinutes())}`;
  const weekday = DAYS[time.getDay() - 1];
  const day = pad(time.getDate());
  setText(widgets.time, text);
  setText(widgets.timeAod, text);
  setText(widgets.weekday, weekday);
  setText(widgets.weekdayAod, weekday);
  setText(widgets.day, day);
  setText(widgets.dayAod, day);
}

function updateHeartRate() {
  const bpm = heartRate.getLast();
  setText(widgets.heartRate, bpm > 0 ? String(bpm) : "--");
}

// Read another app's "<YYYYMMDD> <value>" file; 0 if it's missing or from another day
function readToday(appId, path) {
  const fd = openSync({ path, flag: O_RDONLY, options: { appId } });
  if (fd === undefined || fd < 0) return 0;
  const buffer = new ArrayBuffer(32);
  const length = readSync({ fd, buffer });
  closeSync(fd);
  const text = String.fromCharCode(...new Uint8Array(buffer, 0, Math.max(0, length)));
  const [day, value] = text.split(" ").map(Number);
  const today = time.getFullYear() * 10000 + time.getMonth() * 100 + time.getDate();
  return day === today ? value || 0 : 0;
}

function updateStretch() {
  setText(widgets.stretch, String(readToday(STRETCH_APP_ID, STRETCH_FILE)));
}

// Water in liters with one decimal: 1250 ml -> "1.3L"
function updateWater() {
  setText(widgets.water, `${(readToday(WATER_APP_ID, WATER_FILE) / 1000).toFixed(1)}L`);
}

// Steps rounded to thousands: 6,620 -> "7k"
function updateSteps() {
  setText(widgets.steps, `${Math.round(step.getCurrent() / 1000)}k`);
}

function updateAll() {
  updateTime();
  updateHeartRate();
  updateStretch();
  updateWater();
  updateSteps();
}

const normal = { show_level: hmUI.show_level.ONLY_NORMAL };
const aod = { show_level: hmUI.show_level.ONLY_AOD };
const both = { show_level: hmUI.show_level.ONLY_NORMAL | hmUI.show_level.ONLY_AOD };

// Icon plus value; returns the value widget. Only metrics with a tap area in the layout take onTap.
function createMetric(layout, src, onTap) {
  hmUI.createWidget(hmUI.widget.IMG, { ...layout.icon, ...normal, src });
  const value = hmUI.createWidget(hmUI.widget.TEXT, { ...layout.value, ...normal, text: "--" });
  if (layout.tap) {
    hmUI.createWidget(hmUI.widget.FILL_RECT, { ...layout.tap, ...normal }).addEventListener(hmUI.event.CLICK_UP, onTap);
  }
  return value;
}

WatchFace({
  build() {
    hmUI.createWidget(hmUI.widget.FILL_RECT, { ...BACKGROUND_STYLE, ...both });
    hmUI.createWidget(hmUI.widget.IMG, { ...DIAL_STYLE, ...both });

    widgets.time = hmUI.createWidget(hmUI.widget.TEXT, { ...TIME_STYLE, ...normal });
    widgets.weekday = hmUI.createWidget(hmUI.widget.TEXT, { ...WEEKDAY_STYLE, ...normal });
    widgets.day = hmUI.createWidget(hmUI.widget.TEXT, { ...DAY_STYLE, ...normal });
    widgets.timeAod = hmUI.createWidget(hmUI.widget.TEXT, { ...TIME_STYLE, ...aod, color: COLORS.aod });
    widgets.weekdayAod = hmUI.createWidget(hmUI.widget.TEXT, { ...WEEKDAY_STYLE, ...aod, color: COLORS.aod });
    widgets.dayAod = hmUI.createWidget(hmUI.widget.TEXT, { ...DAY_STYLE, ...aod, color: COLORS.aod });

    widgets.heartRate = createMetric(METRICS.heartRate, "images/icon_heart.png");
    widgets.water = createMetric(METRICS.water, "images/icon_water.png", () =>
      launchApp({ appId: WATER_APP_ID, url: "page/index" })
    );
    widgets.steps = createMetric(METRICS.steps, "images/icon_steps.png");
    widgets.stretch = createMetric(METRICS.stretch, "images/icon_stretch.png", () =>
      launchApp({ appId: STRETCH_APP_ID, url: "page/index" })
    );

    // Hands go last so they sweep over everything else
    hmUI.createWidget(hmUI.widget.TIME_POINTER, { ...POINTER_STYLE, ...normal });
    hmUI.createWidget(hmUI.widget.TIME_POINTER, { ...POINTER_AOD_STYLE, ...aod });

    updateAll();

    time.onPerMinute(updateTime);
    heartRate.onLastChange(updateHeartRate);
    step.onChange(updateSteps);

    // Refresh everything when the face comes back into view
    hmUI.createWidget(hmUI.widget.WIDGET_DELEGATE, { resume_call: updateAll });
  },
  onDestroy() {
    heartRate.offLastChange(updateHeartRate);
    step.offChange(updateSteps);
  },
});
