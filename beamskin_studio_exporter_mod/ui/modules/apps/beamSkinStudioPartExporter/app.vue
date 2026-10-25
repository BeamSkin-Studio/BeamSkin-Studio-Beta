<template>
  <section class="exporter">
    <h3>BeamSkin Studio Parts Exporter</h3>
    <p>Export the current vehicle's active parts and DAE mesh names.</p>
    <label>Export preset</label>
    <button
      class="preset-toggle"
      type="button"
      :disabled="busy"
      :aria-expanded="presetListOpen"
      @click="presetListOpen = !presetListOpen"
    >
      <span>{{ selectedPreset.label }}</span>
      <span class="chevron">{{ presetListOpen ? "▲" : "▼" }}</span>
    </button>
    <div v-if="presetListOpen" class="preset-list">
      <button
        v-for="preset in presets"
        :key="preset.value"
        class="preset-option"
        :class="{ selected: selectedPreset.value === preset.value }"
        type="button"
        :disabled="busy"
        @click="selectPreset(preset)"
      >
        {{ preset.label }}
      </button>
    </div>
    <small class="hint">Saved as {{ selectedPreset.value }}.json in the vehicle's export folder.</small>
    <button :disabled="busy" @click="exportParts">
      {{ busy ? "Exporting…" : "Export current vehicle parts" }}
    </button>
    <small :class="{ error }">{{ status }}</small>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue"
import { useEvents } from "@/services/events"

const events = useEvents()
const busy = ref(false)
const error = ref(false)
const presets = [
  { label: "Basic", value: "basic" },
  { label: "Sport", value: "sport" },
  { label: "Super", value: "super" },
  { label: "Police", value: "police" },
  { label: "Taxi", value: "taxi" },
  { label: "Ambulance", value: "ambulance" },
  { label: "Firetruck", value: "firetruck" },
  { label: "Station Wagon", value: "station_wagon" },
  { label: "Sedan", value: "sedan" },
  { label: "Offroad", value: "offroad" },
  { label: "Rally", value: "rally" },
  { label: "Race", value: "race" },
  { label: "Drift", value: "drift" },
  { label: "Drag", value: "drag" },
  { label: "Hypercar", value: "hypercar" },
  { label: "Track", value: "track" },
  { label: "Time Attack", value: "time_attack" },
  { label: "Endurance", value: "endurance" },
  { label: "Street", value: "street" },
  { label: "Tuner", value: "tuner" },
  { label: "Sleeper", value: "sleeper" },
  { label: "Lowrider", value: "lowrider" },
  { label: "Classic", value: "classic" },
  { label: "Retro", value: "retro" },
  { label: "Convertible", value: "convertible" },
  { label: "Coupe", value: "coupe" },
  { label: "Hatchback", value: "hatchback" },
  { label: "Pickup", value: "pickup" },
  { label: "Van", value: "van" },
  { label: "Minivan", value: "minivan" },
  { label: "Bus", value: "bus" },
  { label: "School Bus", value: "school_bus" },
  { label: "Utility", value: "utility" },
  { label: "Work Truck", value: "work_truck" },
  { label: "Tow Truck", value: "tow_truck" },
  { label: "Delivery", value: "delivery" },
  { label: "Cargo", value: "cargo" },
  { label: "Service", value: "service" },
  { label: "Highway Patrol", value: "highway_patrol" },
  { label: "Sheriff", value: "sheriff" },
  { label: "Rescue", value: "rescue" },
  { label: "Military", value: "military" },
  { label: "Rock Crawler", value: "rock_crawler" },
  { label: "Baja", value: "baja" },
  { label: "Trophy Truck", value: "trophy_truck" },
  { label: "Overland", value: "overland" },
  { label: "Safari", value: "safari" },
  { label: "Desert", value: "desert" },
  { label: "Winter", value: "winter" },
  { label: "Snow", value: "snow" },
  { label: "Family", value: "family" },
  { label: "Executive", value: "executive" },
  { label: "Custom", value: "custom" },
]
const selectedPreset = ref({ label: "Basic", value: "basic" })
const presetListOpen = ref(false)
const status = ref("Exports to settings/beamskin_studio/<carid>/<preset>.json")

function selectPreset(preset) {
  selectedPreset.value = preset
  presetListOpen.value = false
}

function onExportStatus(result) {
  busy.value = false
  error.value = !result?.ok
  status.value = result?.message || "The game returned no export status."
}

function exportParts() {
  if (busy.value) return
  busy.value = true
  error.value = false
  status.value = "Reading the active vehicle…"
  bngApi.engineLua(
    `extensions.load('beamSkinStudioPartExporter'); extensions.beamSkinStudioPartExporter.exportCurrentVehicle('${selectedPreset.value.value}')`
  )
}

onMounted(() => events.on("BeamSkinStudioPartsExported", onExportStatus))
onUnmounted(() => events.off("BeamSkinStudioPartsExported", onExportStatus))
</script>

<style scoped>
.exporter {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 7px;
  width: 100%;
  height: 100%;
  padding: 12px;
  overflow: auto;
  color: #f5f5f5;
  background: rgba(20, 20, 20, 0.96);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  font: 13px/1.35 "Segoe UI", sans-serif;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.3);
}

p {
  margin: 0;
}

h3 {
  margin: 0;
  padding-left: 8px;
  border-left: 3px solid #ff6600;
  color: #f5f5f5;
  font-size: 15px;
  font-weight: 700;
}

p,
.hint {
  color: #999999;
}

label {
  margin-top: 3px;
  color: #f5f5f5;
  font-size: 12px;
  font-weight: 600;
}

.preset-toggle {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 7px 9px;
  color: #f5f5f5 !important;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  font: inherit;
  cursor: pointer;
}

.preset-toggle:focus {
  border-color: #ff6600;
  outline: 2px solid rgba(255, 102, 0, 0.28);
  outline-offset: 1px;
}

.chevron {
  margin-left: 8px;
  color: #999999;
  font-size: 10px;
}

.preset-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  height: 180px;
  max-height: 180px;
  flex: 0 0 180px;
  padding: 6px;
  overflow-y: auto;
  background: #0a0a0a;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
}

.preset-option {
  padding: 6px 8px;
  color: #f5f5f5 !important;
  background: #1e1e1e;
  border: 1px solid #2a2a2a;
  border-radius: 3px;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.preset-option:hover:not(:disabled) {
  background: #282828;
  border-color: #ff6600;
}

.preset-option.selected {
  color: #0a0a0a !important;
  background: #ff6600;
  border-color: #ff6600;
}

.preset-option:disabled {
  opacity: 0.65;
  cursor: wait;
}

button {
  margin-top: 3px;
  padding: 9px 10px;
  color: #0a0a0a;
  background: #ff6600;
  border: 0;
  border-radius: 4px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 120ms ease, transform 120ms ease;
}

button:hover:not(:disabled) {
  background: #e55b00;
}

button:active:not(:disabled) {
  transform: translateY(1px);
}

button:disabled {
  opacity: 0.65;
  cursor: wait;
}

small {
  overflow-wrap: anywhere;
  font-size: 11px;
}

.error {
  color: #ff6666;
}
</style>
